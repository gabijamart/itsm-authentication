def normalized_email_key(group, request):
    return request.POST.get(
        'email', ''
    ).strip().casefold()


def backup_login_key(group, request):
    username = request.POST.get(
        'username', ''
    ).strip().casefold()

    ip_address = request.META.get(
        'REMOTE_ADDR', ''
    )

    return f'{ip_address}:{username}'
