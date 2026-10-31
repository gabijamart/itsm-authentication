from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

class AuthenticationTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='TestPassword123!'
        )

    def test_login_success(self):
        response = self.client.post(
            reverse('login'),
            {
                'username': 'testuser',
                'password': 'TestPassword123!'
            }
        )

        self.assertRedirects(response, reverse('dashboard'))
        self.assertIn('_auth_user_id', self.client.session)

    def test_login_invalid_password(self):
        response = self.client.post(
            reverse('login'),
            {
                'username': 'testuser',
                'password': 'WrongPassword'
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))

        self.assertRedirects(
            response,
            '/login/?next=/dashboard/'
        )

    def test_logout_invalidates_session(self):
        self.client.login(
            username='testuser',
            password='TestPassword123!'
        )

        self.assertIn('_auth_user_id', self.client.session)

        response = self.client.post(reverse('logout'))

        self.assertRedirects(response, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_password_uses_argon2id(self):
        self.assertTrue(
            self.user.password.startswith('argon2$argon2id$')
        )
