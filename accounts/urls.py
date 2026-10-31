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
]
