def backup_code_user_key(group, request):
    return str(
        request.session.get('pending_user_id', 'anonymous')
    )


def normalized_email_key(group, request):
    return request.POST.get(
        'email', ''
    ).strip().casefold()
