from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User

from .models import CredentialRevocationLog
from .services.credential_revocation import (
    revoke_group_credentials,
    revoke_user_credentials,
)


admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class SecureUserAdmin(UserAdmin):
    actions = ['revoke_selected_users']

    def has_revoke_permission(self, request):
        return (
            request.user.is_active
            and request.user.is_superuser
        )

    @admin.action(
        description='Revoke selected users credentials',
        permissions=['revoke'],
    )
    def revoke_selected_users(self, request, queryset):
        count = 0

        users = queryset.filter(
            is_superuser=False,
        ).exclude(
            pk=request.user.pk,
        )

        for user in users:
            revoke_user_credentials(
                user=user,
                actor=request.user,
            )
            count += 1

        self.message_user(
            request,
            f'Credentials revoked for {count} users.',
            messages.SUCCESS,
        )


@admin.register(Group)
class SecureGroupAdmin(GroupAdmin):
    actions = ['revoke_selected_groups']

    def has_revoke_permission(self, request):
        return (
            request.user.is_active
            and request.user.is_superuser
        )

    @admin.action(
        description='Revoke credentials for selected group members',
        permissions=['revoke'],
    )
    def revoke_selected_groups(self, request, queryset):
        count = 0

        for group in queryset:
            count += revoke_group_credentials(
                group=group,
                actor=request.user,
            )

        self.message_user(
            request,
            f'Credentials revoked for {count} group members.',
            messages.SUCCESS,
        )


@admin.register(CredentialRevocationLog)
class CredentialRevocationLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'actor',
        'target_username',
        'action',
        'source',
    )
    list_filter = ('action', 'created_at')
    search_fields = ('target_username', 'source')
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser
    