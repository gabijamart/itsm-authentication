from django_ratelimit.decorators import ratelimit

from .security import normalized_email_key
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


urlpatterns = [
    path('register/', views.register, name='register'),
    path(
        'registration-success/',
        views.registration_success,
        name='registration_success',
    ),
    path(
        'login/',
        ratelimit(
            key='ip',
            rate='30/15m',
            method='POST',
            block=True,
        )(
            views.SecureLoginView.as_view()
        ),
        name='login',
    ),
    path(
        'logout/',
        auth_views.LogoutView.as_view(next_page='login'),
        name='logout',
    ),
    path('dashboard/', views.dashboard, name='dashboard'),
    path(
        'backup-codes/',
        views.backup_codes_setup,
        name='backup_codes_setup',
    ),
    path(
        'password-reset/',
        ratelimit(
            key='ip',
            rate='10/15m',
            method='POST',
            block=True,
        )(
            ratelimit(
                key=normalized_email_key,
                rate='3/15m',
                method='POST',
                block=True,
            )(
                auth_views.PasswordResetView.as_view(
                    template_name='accounts/password_reset.html',
                    email_template_name='accounts/password_reset_email.txt',
                    subject_template_name='accounts/password_reset_subject.txt',
                    success_url='/password-reset/done/',
                )
            )
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'password-reset/confirm/<uidb64>/<token>/',
        views.SecurePasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
    path(
        'password-reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
    path(
    'login/backup/',
    views.backup_recovery_view,
    name='backup_recovery',
    ),
    path(
        'login/backup/set-password/',
        views.recovery_set_password_view,
        name='recovery_set_password',
    ),
]
