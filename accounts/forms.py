from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class RegistrationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username',)

class BackupCodeForm(forms.Form):
    code = forms.CharField(
        label='Backup code',
        max_length=32,
        min_length=32,
        strip=True,
    )

class GenerateBackupCodesForm(forms.Form):
    password = forms.CharField(
        label='Confirm password',
        widget=forms.PasswordInput,
    )
