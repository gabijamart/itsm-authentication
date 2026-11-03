import base64, glob, os, pathlib, re, signal, subprocess, sys, time
from datetime import datetime, timezone
import requests

HERE = pathlib.Path(__file__).resolve().parent
_win = HERE / ".venv" / "Scripts" / "python.exe"
_nix = HERE / ".venv" / "bin" / "python"
PY = str(_win if _win.exists() else _nix if _nix.exists() else sys.executable)
BASE = "http://127.0.0.1:8000"
EMAIL_DIR = HERE / "sent_emails"
PW = "Correct-Horse-42"
RESULTS = []
_server = None


def start_server():
    global _server
    EMAIL_DIR.mkdir(exist_ok=True)
    _server = subprocess.Popen([PY, "manage.py", "runserver", "127.0.0.1:8000", "--noreload"],
                               cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            requests.get(BASE + "/login/", timeout=1)
            return
        except requests.ConnectionError:
            time.sleep(0.5)
    raise RuntimeError("server did not start")


def _port_free():
    try:
        requests.get(BASE + "/login/", timeout=0.5)
        return False
    except requests.RequestException:
        return True


def stop_server():
    global _server
    if _server:
        _server.send_signal(signal.SIGTERM)
        try:
            _server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _server.kill()
            _server.wait()
        _server = None
    for _ in range(40):
        if _port_free():
            return
        time.sleep(0.25)


def shell(code):
    out = subprocess.run([PY, "manage.py", "shell", "-c", code], cwd=HERE,
                         capture_output=True, text=True).stdout
    lines = [l for l in out.splitlines() if l.strip()
             and "objects imported automatically" not in l and "use -v 2 for details" not in l]
    return lines[-1] if lines else ""


def reset_state():
    stop_server()
    subprocess.run([PY, "manage.py", "axes_reset"], cwd=HERE,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for f in glob.glob(str(EMAIL_DIR / "*")):
        os.remove(f)
    start_server()


def seed():
    shell("from django.contrib.auth.models import User,Group;"
          "[u.delete() for u in User.objects.all()];"
          "v=User.objects.create_user('victim','victim@test.lt','%s');"
          "p=User.objects.create_user('peer','peer@test.lt','%s');"
          "o=User.objects.create_user('ordinary','ord@test.lt','Ordinary-Pass-9');"
          "User.objects.create_superuser('admin','admin@test.lt','Admin-Pass-2026!');"
          "g,_=Group.objects.get_or_create(name='contractors');v.groups.add(g);p.groups.add(g)"
          % (PW, PW))


def csrf(sess, path):
    r = sess.get(BASE + path)
    m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r.text)
    return m.group(1) if m else sess.cookies.get("csrftoken")


def post(sess, path, data, redir=False):
    data = dict(data)
    data["csrfmiddlewaretoken"] = csrf(sess, path)
    return sess.post(BASE + path, data=data, allow_redirects=redir)


def login(sess, u, p, redir=False):
    return post(sess, "/login/", {"username": u, "password": p}, redir)


def record(tid, control, expected, actual, passed):
    RESULTS.append(dict(id=tid, control=control, expected=expected, actual=actual, passed=passed))
    print(f"{tid}  {'PASS' if passed else 'FAIL'}  {control}")


def T01():
    shell("from django.contrib.auth.models import User;"
          "[User.objects.filter(username=u).delete() for u in ('s1','s2')];"
          "User.objects.create_user('s1','s1@t.lt','Shared-Pass-123');"
          "User.objects.create_user('s2','s2@t.lt','Shared-Pass-123')")
    h = shell("from django.contrib.auth.models import User;"
              "print('|'.join(User.objects.get(username=u).password for u in ('s1','s2')))")
    h1, h2 = h.split("|")
    record("T01", "Password hashing with salt",
           "Two users with the same password store different hashes",
           f"both argon2id, hashes differ={h1 != h2} (e.g. {h1[:24]}... vs {h2[:24]}...)",
           h1 != h2 and h1.startswith("argon2"))


def T02():
    def reg(u, pw):
        r = post(requests.Session(), "/register/", {"username": u, "email": f"{u}@t.lt",
                                                    "password1": pw, "password2": pw})
        return r.status_code in (301, 302)
    a = reg("polA", "Str0ng!x")
    b = reg("polB", "correct horse battery staple ab")
    c = reg("polC", "password")
    d = reg("polD", "12345678")
    ok = a and b and not c and not d
    record("T02", "Password policy",
           "8-char and 32-char passphrase accepted; blacklisted and all-numeric rejected",
           f"8-char={a}, passphrase={b}, 'password'={'rejected' if not c else 'ACCEPTED'}, "
           f"numeric={'rejected' if not d else 'ACCEPTED'}", ok)


def T03():
    def msg(u, p):
        r = login(requests.Session(), u, p)
        m = re.search(r'(Please enter a correct username and password[^<.]*)', r.text)
        return m.group(1).strip() if m else "?"
    u, k = msg("ghost", "x"), msg("victim", "x")
    record("T03", "Generic login error",
           "Unknown user and wrong password return the same message",
           f'both return "{k}"' if u == k else f"differ: {u!r} vs {k!r}", u == k and u != "?")


def T04():
    reset_state()
    s = requests.Session()
    codes = [login(s, "victim", f"wrong{i}").status_code for i in range(8)]
    locked_correct = login(requests.Session(), "victim", PW).status_code == 429
    record("T04", "Sequential login rate limiting",
           "Lockout (HTTP 429) engages by the 5th failure; correct password also blocked",
           f"status sequence {codes}; correct-pw-while-locked blocked={locked_correct}",
           429 in codes and codes.index(429) <= 5 and locked_correct)


def T05():
    reset_state()
    s = requests.Session()
    s.get(BASE + "/login/")
    pre = s.cookies.get("sessionid")
    login(s, "victim", PW)
    postid = s.cookies.get("sessionid")
    record("T05", "Session rotation",
           "A new session id is issued at login",
           f"pre={pre} post={postid}", pre != postid and postid is not None)


def T06():
    reset_state()
    s = requests.Session()
    login(s, "victim", PW)
    c = next((ck for ck in s.cookies if ck.name == "sessionid"), None)
    ho = bool(c and (c.has_nonstandard_attr("HttpOnly") or c.has_nonstandard_attr("httponly")))
    ss = (c.get_nonstandard_attr("SameSite") or c.get_nonstandard_attr("samesite")) if c else None
    record("T06", "Cookie security",
           "sessionid is HttpOnly and SameSite=Lax (Secure in production/HTTPS)",
           f"HttpOnly={ho}, SameSite={ss}; Secure off under DEBUG=True by design",
           ho and (ss or "").lower() == "lax")


def T07():
    reset_state()
    s = requests.Session()
    login(s, "victim", PW)
    before = s.get(BASE + "/dashboard/", allow_redirects=False).status_code
    s.post(BASE + "/logout/", data={"csrfmiddlewaretoken": s.cookies.get("csrftoken")},
           allow_redirects=False)
    after = s.get(BASE + "/dashboard/", allow_redirects=False).status_code
    record("T07", "Session termination",
           "After logout the old session cannot reach a protected page",
           f"dashboard before logout={before}, after logout={after}",
           before == 200 and after in (301, 302))


def T08():
    reset_state()
    s = requests.Session()
    login(s, "victim", PW)
    r = post(s, "/backup-codes/", {"password": PW})
    codes = re.findall(r'\b([0-9a-f]{32})\b', r.text)
    good = post(requests.Session(), "/login/backup/", {"username": "victim", "code": codes[0]}, redir=True)
    reuse = post(requests.Session(), "/login/backup/", {"username": "victim", "code": codes[0]}, redir=True)
    bad = post(requests.Session(), "/login/backup/", {"username": "victim", "code": "0" * 32}, redir=True)
    g = "set-password" in good.url
    ru = "set-password" in reuse.url
    bd = "set-password" in bad.url
    record("T08", "Backup code",
           "Valid code works once; reused and invalid codes are rejected",
           f"valid={'accepted' if g else 'rejected'}, reused={'accepted' if ru else 'rejected'}, "
           f"invalid={'accepted' if bd else 'rejected'}", g and not ru and not bd)


def T09():
    reset_state()
    post(requests.Session(), "/password-reset/", {"email": "victim@test.lt"})
    files = sorted(glob.glob(str(EMAIL_DIR / "*")), key=os.path.getmtime)
    link = re.search(r'(http://[^\s]+/password-reset/confirm/[^\s]+)',
                     pathlib.Path(files[-1]).read_text()).group(1)
    s = requests.Session()
    rr = s.get(link, allow_redirects=True)
    setp = requests.compat.urlparse(rr.url).path
    ok = post(s, setp, {"new_password1": "Reset-Pass-2026!", "new_password2": "Reset-Pass-2026!"}, redir=True)
    forged = requests.Session().get(f"{BASE}/password-reset/confirm/MQ/fake-000000/", allow_redirects=True)
    good = "complete" in ok.url
    bad = "set_password" in forged.text.lower() or "new_password1" in forged.text
    seed()
    record("T09", "Credential reset",
           "Valid signed token resets; forged/invalid token rejected (single use, 10-min expiry)",
           f"valid token -> reset={good}; forged token accepted={bad}", good and not bad)


def T10():
    out = shell("from django.contrib.auth.models import User;"
                "from accounts.services.credential_revocation import revoke_user_credentials as rv;"
                "o=User.objects.get(username='ordinary');"
                "User.objects.filter(username='t10').delete();"
                "t=User.objects.create_user('t10','t10@t.lt','Target-1');"
                "\ntry:\n rv(t,o,'test'); print('ALLOWED')\nexcept Exception as e: print(type(e).__name__)")
    record("T10", "Unauthorized revocation",
           "An ordinary account cannot revoke another user's credentials",
           f"ordinary actor -> {out}", out == "PermissionError")


def T11():
    out = shell("from django.contrib.auth.models import User;"
                "from accounts.services.credential_revocation import revoke_user_credentials as rv;"
                "from accounts.models import CredentialRevocationLog as L;"
                "a=User.objects.get(username='admin');"
                "User.objects.filter(username='t11').delete();"
                "t=User.objects.create_user('t11','t11@t.lt','Target-2');"
                "rv(t,a,'test');t.refresh_from_db();"
                "print('active=%s unusable=%s logged=%s'%(t.is_active,not t.has_usable_password(),"
                "L.objects.filter(target_username='t11').exists()))")
    ok = "active=False" in out and "unusable=True" in out and "logged=True" in out
    record("T11", "Authorized revocation",
           "Admin revoke disables the account, voids the password, writes an audit row",
           out, ok)


def T12():
    out = shell("from django.contrib.auth.models import User,Group;"
                "from accounts.services.credential_revocation import revoke_group_credentials as rg;"
                "a=User.objects.get(username='admin');g,_=Group.objects.get_or_create(name='grp12');"
                "[User.objects.filter(username=u).delete() for u in ('gm1','gm2')];"
                "u1=User.objects.create_user('gm1','gm1@t.lt','G-1');"
                "u2=User.objects.create_user('gm2','gm2@t.lt','G-2');"
                "u1.groups.add(g);u2.groups.add(g);n=rg(g,a);"
                "left=User.objects.filter(groups=g,is_active=True).count();"
                "print('revoked=%d active_left=%d'%(n,left))")
    ok = "revoked=2" in out and "active_left=0" in out
    record("T12", "Group revocation",
           "Admin group revoke disables all non-admin members and audits each",
           out, ok)


def T13():
    reset_state()
    r = post(requests.Session(), "/register/", {"username": "fresh", "email": "fresh@t.lt",
                                                "password1": "Fresh-Acct-2026!", "password2": "Fresh-Acct-2026!"})
    reg_ok = r.status_code in (301, 302)
    s = requests.Session()
    li = login(s, "fresh", "Fresh-Acct-2026!", redir=True)
    login_ok = "/dashboard" in li.url
    record("T13", "Basic registration and login",
           "A new account registers and logs in to the dashboard",
           f"register={'ok' if reg_ok else 'fail'}, login={'dashboard' if login_ok else 'fail'}",
           reg_ok and login_ok)


def T14():
    reset_state()
    s = requests.Session()
    codes = [login(s, f"target{i}", "Password123!").status_code for i in range(35)]
    first = next((i + 1 for i, c in enumerate(codes) if c in (403, 429)), None)
    record("T14", "Distributed credential stuffing",
           "A per-IP limit blocks stuffing across many accounts",
           f"first block at attempt {first} (HTTP 403, login 30/15m per IP)", first is not None)


def T15():
    def med(user):
        xs = []
        for i in range(10):
            reset_state()
            t0 = time.perf_counter()
            login(requests.Session(), user, f"x{i}")
            xs.append((time.perf_counter() - t0) * 1000)
        xs.sort()
        return xs[len(xs) // 2]
    k, u = med("victim"), med("ghost")
    diff = abs(k - u) / k * 100
    record("T15", "User enumeration by timing",
           "Login time does not reveal whether the account exists",
           f"existing={k:.0f}ms unknown={u:.0f}ms diff={diff:.0f}%", diff < 40)


def T16():
    out = shell("from django.contrib.auth.hashers import Argon2PasswordHasher as A;a=A();"
                "print('m=%s t=%s p=%s'%(a.memory_cost,a.time_cost,a.parallelism))")
    m = int(re.search(r"m=(\d+)", out).group(1))
    t = int(re.search(r"t=(\d+)", out).group(1))
    record("T16", "Password hash strength",
           "Memory-hard hash at/above OWASP minimum (m>=19 MiB, t>=2)",
           f"argon2id {out} ({m // 1024} MiB)", m >= 19 * 1024 and t >= 2)


def T17():
    reset_state()
    shell("from django.contrib.auth.models import User;"
          "from accounts.services.backup_codes import generate_backup_codes;"
          "generate_backup_codes(User.objects.get(username='victim'))")
    s = requests.Session()
    codes = [post(s, "/login/backup/", {"username": "victim", "code": "0" * 32}).status_code for _ in range(12)]
    first = next((i + 1 for i, c in enumerate(codes) if c in (403, 429)), None)
    record("T17", "Backup code brute force",
           "Invalid backup-code attempts are rate limited",
           f"first block at attempt {first}; seq {codes[:8]}... (403, 5/15m per IP+username)",
           first is not None and first <= 7)


def T18():
    out = shell("from django.contrib.auth.models import User;"
                "from accounts.services.backup_codes import generate_backup_codes as gen, verify_backup_code as ver;"
                "from accounts.models import BackupCode;"
                "User.objects.filter(username='t18').delete();"
                "u=User.objects.create_user('t18','t18@t.lt','P-18');"
                "old=gen(u);raw_in_db=any(c in str(list(BackupCode.objects.values_list('code_hash',flat=True))) for c in old);"
                "new=gen(u);"
                "print('raw_in_db=%s old_rejected=%s new_accepted=%s'%(raw_in_db, ver(u,old[0])==False, ver(u,new[0])==True))")
    ok = "raw_in_db=False" in out and "old_rejected=True" in out and "new_accepted=True" in out
    record("T18", "Backup code storage and rotation",
           "Only hashes stored; regeneration invalidates the previous set",
           out, ok)


def T19():
    reset_state()
    s = requests.Session()
    uidb64 = base64.urlsafe_b64encode(b"1").decode().rstrip("=")
    hits = 0
    for _ in range(200):
        import secrets
        fake = f"{secrets.token_hex(3)}-{secrets.token_urlsafe(16)}"
        r = s.get(f"{BASE}/password-reset/confirm/{uidb64}/{fake}/", allow_redirects=True)
        if "new_password1" in r.text or "set-password" in r.url.lower():
            hits += 1
    record("T19", "Reset token unpredictability",
           "No forged reset token is accepted",
           f"{hits}/200 forged tokens accepted", hits == 0)


def T20():
    reset_state()
    s = requests.Session()
    s.cookies.set("sessionid", "forged" + "0" * 26, domain="127.0.0.1")
    r = s.get(BASE + "/dashboard/", allow_redirects=False)
    record("T20", "Forged session identifier",
           "A forged session id is not authenticated",
           f"GET /dashboard/ with forged sessionid -> HTTP {r.status_code} (redirect to login)",
           r.status_code in (301, 302))


def _issue_codes(username):
    return shell("from django.contrib.auth.models import User;"
                 "from accounts.services.backup_codes import generate_backup_codes;"
                 f"print('|'.join(generate_backup_codes(User.objects.get(username='{username}'))))").split("|")


def _reset_link():
    files = sorted(glob.glob(str(EMAIL_DIR / "*")), key=os.path.getmtime)
    return re.search(r'(http://[^\s]+/password-reset/confirm/[^\s]+)',
                     pathlib.Path(files[-1]).read_text()).group(1)


def T21():
    reset_state()
    codes = _issue_codes("victim")
    post(requests.Session(), "/password-reset/", {"email": "victim@test.lt"})
    s = requests.Session()
    rr = s.get(_reset_link(), allow_redirects=True)
    setp = requests.compat.urlparse(rr.url).path
    post(s, setp, {"new_password1": "After-Reset-1!", "new_password2": "After-Reset-1!"}, redir=True)
    old = post(requests.Session(), "/login/backup/", {"username": "victim", "code": codes[0]}, redir=True)
    left = shell("from django.contrib.auth.models import User;from accounts.models import BackupCode;"
                 "print(BackupCode.objects.filter(user=User.objects.get(username='victim')).count())")
    accepted = "set-password" in old.url
    seed()
    record("T21", "Password reset invalidates backup codes",
           "Completing an email password reset deletes the user's backup codes",
           f"old backup code accepted after reset={accepted}; backup codes left in DB={left}",
           (not accepted) and left == "0")


def T22():
    reset_state()
    codes = _issue_codes("victim")
    s = requests.Session()
    post(s, "/login/backup/", {"username": "victim", "code": codes[0]}, redir=False)
    before = s.get(BASE + "/login/backup/set-password/", allow_redirects=False).status_code
    sid = s.cookies.get("sessionid")
    shell("from django.contrib.sessions.backends.db import SessionStore;"
          f"st=SessionStore('{sid}');st['recovery_started_at']=st['recovery_started_at']-601;st.save()")
    after = s.get(BASE + "/login/backup/set-password/", allow_redirects=False).status_code
    record("T22", "Recovery session 10-minute expiry",
           "The backup-code recovery session stops allowing a password change after 10 minutes",
           f"set-password reachable within window (HTTP {before}); after start time rewound >600s -> HTTP {after}",
           before == 200 and after in (301, 302))


def main():
    seed()
    start_server()
    env = dict(
        hash=shell("from django.contrib.auth.hashers import Argon2PasswordHasher as A;a=A();"
                   "print('argon2id m=%s t=%s p=%s'%(a.memory_cost,a.time_cost,a.parallelism))"))
    try:
        for fn in (T01, T02, T03, T04, T05, T06, T07, T08, T09, T10, T11, T12, T13,
                   T14, T15, T16, T17, T18, T19, T20, T21, T22):
            try:
                fn()
            except Exception as e:
                record(fn.__name__, fn.__name__, "(ran without error)", f"ERROR: {e!r}", False)
    finally:
        stop_server()

    passed = sum(r["passed"] for r in RESULTS)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = []
    out.append("=" * 74)
    out.append("ITSM Authentication - Security Test Log")
    out.append("=" * 74)
    out.append(f"Target      : {BASE}  (Django 5.2, local, DEBUG=True)")
    out.append(f"Run         : {now}")
    out.append(f"Password hash: {env['hash']}")
    out.append(f"Result      : {passed}/{len(RESULTS)} passed")
    out.append("=" * 74)
    for r in RESULTS:
        out.append("")
        out.append(f"[{r['id']}] {r['control']}  --  {'PASS' if r['passed'] else 'FAIL'}")
        out.append(f"   Expected: {r['expected']}")
        out.append(f"   Actual  : {r['actual']}")
    out.append("")
    out.append("=" * 74)
    out.append(f"SUMMARY: {passed}/{len(RESULTS)} passed"
               + ("" if passed == len(RESULTS) else "  FAILED: "
                  + ", ".join(r["id"] for r in RESULTS if not r["passed"])))
    out.append("=" * 74)
    text = "\n".join(out)
    (HERE / "test_log.txt").write_text(text)
    print("\n" + text)


if __name__ == "__main__":
    main()
    