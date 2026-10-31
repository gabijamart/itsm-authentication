from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import transaction

from accounts.models import (
    BackupCode,
    CredentialRevocationLog,
)


def invalidate_user_sessions(user_ids):
    user_ids = {str(user_id) for user_id in user_ids}
    session_keys = []

    for session in Session.objects.all().iterator():
        data = session.get_decoded()

        authenticated_user = str(
            data.get('_auth_user_id', '')
        )
        pending_user = str(
            data.get('pending_user_id', '')
        )

        if (
            authenticated_user in user_ids
            or pending_user in user_ids
        ):
            session_keys.append(session.session_key)

    if session_keys:
        Session.objects.filter(
            session_key__in=session_keys,
        ).delete()

    return len(session_keys)


@transaction.atomic
def revoke_user_credentials(user, actor, source='user'):
    if not actor.is_active or not actor.is_superuser:
        raise PermissionError(
            'Only an active superuser can revoke credentials.'
        )

    if user.is_superuser:
        raise ValueError(
            'Superuser credentials cannot be revoked here.'
        )

    if user.pk == actor.pk:
        raise ValueError(
            'Administrator cannot revoke their own credentials.'
        )

    User = get_user_model()

    user = User.objects.select_for_update().get(pk=user.pk)

    user.is_active = False
    user.set_unusable_password()
    user.save(update_fields=['is_active', 'password'])

    invalidate_user_sessions([user.pk])

    BackupCode.objects.filter(user=user).delete()

    CredentialRevocationLog.objects.create(
        actor=actor,
        target_user=user,
        target_username=user.username,
        action='credentials_revoked',
        source=source,
    )

    return user


@transaction.atomic
def revoke_group_credentials(group, actor):
    if not actor.is_active or not actor.is_superuser:
        raise PermissionError(
            'Only an active superuser can revoke credentials.'
        )

    User = get_user_model()

    users = User.objects.filter(
        groups=group,
        is_superuser=False,
    ).exclude(
        pk=actor.pk,
    )

    user_ids = list(users.values_list('pk', flat=True))

    for user in users:
        revoke_user_credentials(
            user=user,
            actor=actor,
            source=f'group:{group.name}',
        )

    return len(user_ids)
