from django.urls import path

from . import views


urlpatterns = [
    path('register/', views.register, name='register'),
    path(
        'registration-success/',
        views.registration_success,
        name='registration_success',
    ),
]
