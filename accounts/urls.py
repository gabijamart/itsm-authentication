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
        views.SecureLoginView.as_view(),
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
        'verify-backup-code/',
        views.verify_backup_code_view,
        name='verify_backup_code',
    ),
    path(
    'password-reset/',
    auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset.html',
        email_template_name='accounts/password_reset_email.txt',
        subject_template_name='accounts/password_reset_subject.txt',
        success_url='/password-reset/done/',
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
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            success_url='/password-reset/complete/',
        ),
        name='password_reset_confirm',
    ),
    path(
        'password-reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
]
