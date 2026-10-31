from django.conf import settings
from django.db import models


class BackupCode(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='backup_codes',
    )
    code_hash = models.CharField(
        max_length=255,
        unique=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Backup code for user {self.user_id}'


class BackupCodeEnrollment(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='backup_code_enrollment',
    )
    enabled = models.BooleanField(default=True)
    