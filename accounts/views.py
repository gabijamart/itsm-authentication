import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.db import transaction
from django.contrib.auth.views import LoginView, PasswordResetConfirmView
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from .forms import (
    BackupRecoveryForm,
    GenerateBackupCodesForm,
    RegistrationForm,
)
from .models import BackupCode
from .security import backup_login_key
from .services.backup_codes import (
    generate_backup_codes,
    verify_backup_code,
)

logger = logging.getLogger(__name__)

RECOVERY_TTL = 600


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect('registration_success')
    else:
        form = RegistrationForm()

    return render(
        request,
        'accounts/register.html',
        {'form': form},
    )


def registration_success(request):
    return render(
        request,
        'accounts/registration_success.html',
    )


class SecureLoginView(LoginView):
    template_name = 'accounts/login.html'



@login_required
def dashboard(request):
    remaining = BackupCode.objects.filter(
        user=request.user,
    ).count()

    return render(
        request,
        'accounts/dashboard.html',
        {'remaining': remaining},
    )


@login_required
@require_http_methods(['GET', 'POST'])
@ratelimit(
    key='user',
    rate='5/15m',
    method='POST',
    block=True,
)
def backup_codes_setup(request):
    if request.method == 'POST':
        form = GenerateBackupCodesForm(request.POST)

        if form.is_valid():
            password = form.cleaned_data['password']

            if not request.user.check_password(password):
                form.add_error(
                    'password',
                    'Incorrect password.',
                )
            else:
                codes = generate_backup_codes(
                    request.user,
                )

                response = render(
                    request,
                    'accounts/backup_codes_generated.html',
                    {'codes': codes},
                )
                response['Cache-Control'] = 'no-store'
                return response

    else:
        form = GenerateBackupCodesForm()

    return render(
        request,
        'accounts/backup_codes_setup.html',
        {'form': form},
    )

@never_cache
@require_http_methods(['GET', 'POST'])
@ratelimit(
    key='ip',
    rate='20/15m',
    method='POST',
    block=True,
)
@ratelimit(
    key=backup_login_key,
    rate='5/15m',
    method='POST',
    block=True,
)
def backup_recovery_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = BackupRecoveryForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data['username']
            code = form.cleaned_data['code']

            User = get_user_model()

            user = User.objects.filter(
                username__iexact=username,
                is_active=True,
            ).first()

            if (
                user is not None
                and not user.is_superuser
                and verify_backup_code(user, code)
            ):
                request.session.flush()

                request.session['recovery_user_id'] = user.pk
                request.session['recovery_started_at'] = (
                    timezone.now().timestamp()
                )
                request.session.set_expiry(RECOVERY_TTL)

                logger.info(
                    'Backup recovery started for user_id=%s',
                    user.pk,
                )

                return redirect('recovery_set_password')

            logger.warning(
                'Failed backup recovery attempt'
            )

            form.add_error(
                None,
                'Invalid username or backup code.',
            )
    else:
        form = BackupRecoveryForm()

    return render(
        request,
        'accounts/backup_recovery.html',
        {'form': form},
    )


class SecurePasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = '/password-reset/complete/'

    def form_valid(self, form):
        response = super().form_valid(form)

        BackupCode.objects.filter(
            user=self.user,
        ).delete()

        logger.info(
            'Password reset completed for user_id=%s',
            self.user.pk,
        )

        return response

@never_cache
@require_http_methods(['GET', 'POST'])
def recovery_set_password_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    user_id = request.session.get('recovery_user_id')
    started_at = request.session.get('recovery_started_at')

    if not user_id or not started_at:
        return redirect('login')

    elapsed = timezone.now().timestamp() - started_at

    if elapsed < 0 or elapsed >= 600:
        request.session.flush()
        return redirect('login')

    User = get_user_model()

    user = User.objects.filter(
        pk=user_id,
        is_active=True,
        is_superuser=False,
    ).first()

    if user is None:
        request.session.flush()
        return redirect('login')

    if request.method == 'POST':
        form = SetPasswordForm(user, request.POST)

        if form.is_valid():
            with transaction.atomic():
                locked_user = User.objects.select_for_update().get(
                    pk=user.pk,
                )

                if not locked_user.is_active or locked_user.is_superuser:
                    request.session.flush()
                    return redirect('login')

                locked_user.set_password(
                    form.cleaned_data['new_password1']
                )
                locked_user.save(update_fields=['password'])

                BackupCode.objects.filter(
                    user=locked_user,
                ).delete()

            logger.info(
                'Password recovered using backup code for user_id=%s',
                user.pk,
            )

            request.session.flush()

            messages.success(
                request,
                'Password updated. Please log in.',
            )

            return redirect('login')
    else:
        form = SetPasswordForm(user)

    return render(
        request,
        'accounts/recovery_set_password.html',
        {'form': form},
    )
