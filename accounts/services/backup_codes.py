import hmac
import secrets
from hashlib import sha256

from django.conf import settings
from django.db import transaction

from accounts.models import BackupCode, BackupCodeEnrollment


def _hash_code(user_id, code):
    message = f'{user_id}:{code}'.encode('utf-8')

    return hmac.new(
        settings.SECRET_KEY.encode('utf-8'),
        message,
        sha256,
    ).hexdigest()


@transaction.atomic
def generate_backup_codes(user, count=10):
    codes = [
        secrets.token_hex(16)
        for _ in range(count)
    ]

    BackupCode.objects.filter(user=user).delete()

    BackupCode.objects.bulk_create([
        BackupCode(
            user=user,
            code_hash=_hash_code(user.pk, code),
        )
        for code in codes
    ])

    BackupCodeEnrollment.objects.update_or_create(
        user=user,
        defaults={'enabled': True},
    )

    return codes


def verify_backup_code(user, code):
    code_hash = _hash_code(
        user.pk,
        code.strip().lower(),
    )

    deleted_count, _ = BackupCode.objects.filter(
        user=user,
        code_hash=code_hash,
    ).delete()

    return deleted_count == 1
