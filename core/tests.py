from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import OTP, ProviderProfile, User


class ProviderApprovalTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com", password="StrongPass123!", role=User.Role.ADMIN
        )
        self.provider = User.objects.create_user(
            email="provider@example.com", password="StrongPass123!", role=User.Role.PROVIDER
        )
        self.profile = self.provider.provider_profile

    def test_approval_requires_post_and_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("core:approve_provider", args=[self.profile.pk])
        )
        self.assertEqual(response.status_code, 405)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_approved)

    def test_admin_can_approve_provider_with_post(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("core:approve_provider", args=[self.profile.pk])
        )
        self.assertRedirects(response, reverse("core:dashboard"))
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_approved)

    def test_non_admin_cannot_approve_provider(self):
        self.client.force_login(self.provider)
        response = self.client.post(
            reverse("core:approve_provider", args=[self.profile.pk])
        )
        self.assertRedirects(response, reverse("core:dashboard"))
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_approved)


class StaticPagesTests(TestCase):
    def test_about_contact_terms_privacy_are_live(self):
        for name in ("core:about", "core:contact", "core:terms", "core:privacy"):
            with self.subTest(url=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)

    def test_custom_404_page(self):
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "404", status_code=404)

    def test_contact_form_sends_email(self):
        response = self.client.post(
            reverse("core:contact"),
            {"name": "Casey", "email": "casey@example.com", "message": "Hello!"},
        )
        self.assertRedirects(response, reverse("core:contact"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Casey", mail.outbox[0].body)


class AccountFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="casey@example.com", password="OldStrongPass123!"
        )
        self.user.is_verified = True
        self.user.save(update_fields=["is_verified"])

    def test_login_page_has_eye_toggle_and_no_demo_creds(self):
        html = self.client.get(reverse("accounts:login")).content.decode()
        self.assertIn("data-pw-toggle", html)
        self.assertNotIn("admin@localfix.test", html)

    def test_header_logout_button_for_authenticated_users(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("core:dashboard")).content.decode()
        self.assertIn('action="{}"'.format(reverse("accounts:logout")), html)
        self.assertIn("Log out", html)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_registration_sends_otp_email(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "Priya",
                "last_name": "Nair",
                "email": "priya@example.com",
                "phone": "555-0100",
                "role": "customer",
                "password1": "AnotherStrong456!",
                "password2": "AnotherStrong456!",
            },
        )
        self.assertRedirects(response, reverse("accounts:verify"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Your LocalFix code", mail.outbox[0].subject)
        self.assertIn(mail.outbox[0].to[0], "priya@example.com")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_verification_sends_one_time_welcome_email(self):
        # Go through the real registration path: register -> verify-OTP page.
        response = self.client.post(
            reverse("accounts:register"),
            {
                "first_name": "New",
                "last_name": "Bie",
                "email": "newbie@example.com",
                "phone": "555-0101",
                "role": "customer",
                "password1": "Whatever123!",
                "password2": "Whatever123!",
            },
        )
        self.assertRedirects(response, reverse("accounts:verify"))
        user = User.objects.get(email="newbie@example.com")

        code = OTP.objects.filter(
            user=user, purpose=OTP.Purpose.VERIFY, is_used=False
        ).order_by("-created_at").first().code
        response = self.client.post(reverse("accounts:verify"), {"code": code})
        self.assertRedirects(response, reverse("core:dashboard"))

        subjects = [m.subject for m in mail.outbox]
        # Email 1: registration OTP. Email 2: one-time welcome.
        self.assertEqual(sum("Welcome to LocalFix" in s for s in subjects), 1)
        user.refresh_from_db()
        self.assertIsNotNone(user.welcome_email_sent_at)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_change_requires_current_password_and_emails_notice(self):
        self.client.force_login(self.user)
        url = reverse("accounts:change_password")

        # Wrong current password is rejected.
        response = self.client.post(
            url,
            {
                "current_password": "wrong",
                "new_password1": "NewStrongPass789!",
                "new_password2": "NewStrongPass789!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldStrongPass123!"))
        self.assertEqual(len(mail.outbox), 0)

        # Correct flow updates the password and emails the notice.
        response = self.client.post(
            url,
            {
                "current_password": "OldStrongPass123!",
                "new_password1": "NewStrongPass789!",
                "new_password2": "NewStrongPass789!",
            },
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStrongPass789!"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("password was changed", mail.outbox[0].subject)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_email_change_requires_otp_to_new_address(self):
        self.client.force_login(self.user)
        self.client.post(
            reverse("accounts:change_email"),
            {"new_email": "renamed@example.com", "current_password": "OldStrongPass123!"},
        )
        # Confirmation code went to the NEW address only.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["renamed@example.com"])

        # Email is unchanged until the code is confirmed.
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "casey@example.com")

        code = OTP.objects.filter(
            user=self.user, purpose=OTP.Purpose.EMAIL_CHANGE, is_used=False
        ).order_by("-created_at").first().code
        response = self.client.post(reverse("accounts:email_change_verify"), {"code": code})
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "renamed@example.com")

        # Old address receives a change notice (2 emails total now).
        self.assertEqual(len(mail.outbox), 2)
