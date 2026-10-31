from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import (
    BackupCodeForm,
    GenerateBackupCodesForm,
    RegistrationForm,
)
from .models import BackupCode, BackupCodeEnrollment
from .services.backup_codes import (
    generate_backup_codes,
    verify_backup_code,
)


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

    def form_valid(self, form):
        user = form.get_user()

        requires_backup_code = BackupCodeEnrollment.objects.filter(
            user=user,
            enabled=True,
        ).exists()

        if not requires_backup_code:
            return super().form_valid(form)

        request = self.request

        request.session.flush()

        request.session['pending_user_id'] = user.pk
        request.session['pending_started_at'] = (
            timezone.now().timestamp()
        )
        request.session['pending_attempts'] = 0
        request.session.set_expiry(300)

        return redirect('verify_backup_code')


@require_http_methods(['GET', 'POST'])
def verify_backup_code_view(request):
    user_id = request.session.get('pending_user_id')
    started_at = request.session.get('pending_started_at')
    attempts = request.session.get('pending_attempts', 0)

    if not user_id or not started_at:
        return redirect('login')

    elapsed = timezone.now().timestamp() - started_at

    if elapsed > 300 or attempts >= 5:
        request.session.flush()
        messages.error(
            request,
            'Verification expired. Please log in again.',
        )
        return redirect('login')

    user = User.objects.filter(
        pk=user_id,
        is_active=True,
    ).first()

    if user is None:
        request.session.flush()
        return redirect('login')

    if request.method == 'POST':
        form = BackupCodeForm(request.POST)

        if form.is_valid():
            code = form.cleaned_data['code']

            if verify_backup_code(user, code):
                request.session.flush()
                login(
                    request,
                    user,
                    backend='django.contrib.auth.backends.ModelBackend',
                )
                return redirect('dashboard')

            request.session['pending_attempts'] = attempts + 1
            form.add_error(
                'code',
                'Invalid or already used backup code.',
            )

    else:
        form = BackupCodeForm()

    remaining = BackupCode.objects.filter(
        user=user,
    ).count()

    return render(
        request,
        'accounts/verify_backup_code.html',
        {
            'form': form,
            'remaining': remaining,
        },
    )


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
