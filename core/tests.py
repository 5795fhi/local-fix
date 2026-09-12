from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import OTP, ProviderProfile, User
from bookings.models import Booking
from complaints.models import Complaint

import datetime


def _future(days=3, hour=15):
    d = timezone.now() + datetime.timedelta(days=days)
    return d.replace(hour=hour, minute=0, second=0, microsecond=0)


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

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_approval_notifies_provider_once_with_email_and_notification(self):
        from notifications.models import Notification

        self.client.force_login(self.admin)
        url = reverse("core:approve_provider", args=[self.profile.pk])

        response = self.client.post(url)
        self.assertRedirects(response, reverse("core:dashboard"))
        # One approval email, announcing the approval.
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("approved", mail.outbox[0].subject.lower())
        self.assertEqual(mail.outbox[0].to, [self.provider.email])
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.provider, title__icontains="approved"
            ).exists()
        )

        # Approving again does not resend the welcome-to-the-platform email.
        mail.outbox.clear()
        self.client.post(url)
        self.assertEqual(len(mail.outbox), 0)

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


class NegotiationTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email="cust@example.com", password="StrongPass123!", role=User.Role.CUSTOMER
        )
        self.customer.is_verified = True
        self.customer.save(update_fields=["is_verified"])
        self.provider = User.objects.create_user(
            email="pro@example.com", password="StrongPass123!", role=User.Role.PROVIDER
        )
        self.provider.is_verified = True
        self.provider.save(update_fields=["is_verified"])
        self.booking = Booking.objects.create(
            customer=self.customer,
            provider=self.provider,
            description="Leaking tap",
            address="B-702, Andheri West",
            scheduled_for=_future(),
            quoted_price=500,
        )

    def _login(self, user):
        self.client.force_login(user)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_professional_quotes_customer_negotiates_and_accepts(self):
        self._login(self.provider)
        response = self.client.post(
            reverse("bookings:accept", args=[self.booking.pk]),
            {"quoted_price": "650", "provider_note": "Includes new washer"},
        )
        self.assertRedirects(response, reverse("bookings:detail", args=[self.booking.pk]))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.quoted_price, 650)
        self.assertEqual(self.booking.status, Booking.Status.ACCEPTED)
        self.assertEqual(self.booking.last_offer_by, "")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("accepted", mail.outbox[0].subject.lower())

        # Customer makes the first negotiation offer.
        self._login(self.customer)
        response = self.client.post(
            reverse("bookings:offer", args=[self.booking.pk]),
            {"quoted_price": "600", "note": "Budget is 600"},
        )
        self.assertRedirects(response, reverse("bookings:detail", args=[self.booking.pk]))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.quoted_price, 600)
        self.assertEqual(self.booking.last_offer_by, "customer")
        self.assertEqual(len(mail.outbox), 2)  # offer + acceptance

        # Professional accepts the customer's negotiated price.
        self._login(self.provider)
        response = self.client.post(reverse("bookings:accept_offer", args=[self.booking.pk]))
        self.assertRedirects(response, reverse("bookings:detail", args=[self.booking.pk]))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.quoted_price, 600)
        self.assertEqual(self.booking.last_offer_by, "")
        self.assertEqual(self.booking.platform_fee, 60)
        self.assertEqual(self.booking.provider_payout, 540)
        self.assertEqual(len(mail.outbox), 3)

    def test_customer_cannot_negotiate_before_professional_quotes(self):
        self._login(self.customer)
        response = self.client.post(
            reverse("bookings:offer", args=[self.booking.pk]),
            {"quoted_price": "400", "note": "Please reduce this"},
        )
        self.assertRedirects(response, reverse("bookings:detail", args=[self.booking.pk]))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.quoted_price, 500)
        self.assertEqual(self.booking.last_offer_by, "")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_customer_decline_and_counter_updates_price(self):
        # Provider offers 700 first.
        self.booking.status = Booking.Status.ACCEPTED
        self.booking.quoted_price = 700
        self.booking.last_offer_by = "provider"
        self.booking.save()

        self._login(self.customer)
        response = self.client.post(
            reverse("bookings:decline_offer", args=[self.booking.pk]),
            {"counter_price": "600", "note": "Budget is 600"},
        )
        self.assertRedirects(response, reverse("bookings:detail", args=[self.booking.pk]))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.quoted_price, 600)
        self.assertEqual(self.booking.last_offer_by, "customer")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("600", mail.outbox[0].subject)
        self.assertIn("700", mail.outbox[0].body)

        # Customer cannot accept their own offer.
        response = self.client.post(reverse("bookings:accept_offer", args=[self.booking.pk]))
        self.assertEqual(response.status_code, 302)  # redirect with an error flash
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.last_offer_by, "customer")

    def test_negotiation_blocked_in_late_states(self):
        self.booking.status = Booking.Status.COMPLETED
        self.booking.save()
        self._login(self.customer)
        response = self.client.post(
            reverse("bookings:offer", args=[self.booking.pk]), {"quoted_price": "100"}
        )
        self.assertRedirects(response, reverse("bookings:detail", args=[self.booking.pk]))
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.quoted_price, 500)

    def test_negotiation_history_recorded(self):
        self.booking.status = Booking.Status.ACCEPTED
        self.booking.save(update_fields=["status"])
        self._login(self.customer)
        self.client.post(
            reverse("bookings:offer", args=[self.booking.pk]), {"quoted_price": "650"}
        )
        note = self.booking.history.latest("created_at")
        self.assertIn("650", note.note)


class ComplaintProfessionalSnapshotTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email="cust2@example.com", password="StrongPass123!", role=User.Role.CUSTOMER,
            first_name="Aarav", last_name="Sharma",
        )
        self.customer.is_verified = True
        self.customer.save(update_fields=["is_verified"])
        self.provider = User.objects.create_user(
            email="pro2@example.com", password="StrongPass123!", role=User.Role.PROVIDER,
            first_name="Vikram", last_name="Rao", phone="+919812345678",
        )
        self.provider.is_verified = True
        self.provider.save(update_fields=["is_verified"])
        self.booking = Booking.objects.create(
            customer=self.customer,
            provider=self.provider,
            description="Fan repair",
            address="12/A, Bandra West",
            scheduled_for=_future(),
            quoted_price=400,
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_complaint_snapshots_the_reported_professional(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("complaints:raise"),
            {
                "booking": self.booking.pk,
                "subject": "Job left unfinished",
                "description": "The technician left before completing the repair.",
            },
        )
        self.assertRedirects(response, reverse("complaints:my_complaints"))
        complaint = Complaint.objects.get(subject="Job left unfinished")
        self.assertEqual(complaint.reported_professional_name, "Vikram Rao")
        self.assertEqual(complaint.reported_professional_email, "pro2@example.com")
        self.assertEqual(complaint.reported_professional_phone, "+919812345678")

        # Snapshot survives even if the provider account is deleted.
        self.provider.delete()
        complaint.refresh_from_db()
        self.assertEqual(complaint.reported_professional_name, "Vikram Rao")

    def test_complaint_without_booking_has_no_snapshot(self):
        self.client.force_login(self.customer)
        self.client.post(
            reverse("complaints:raise"),
            {"subject": "App issue", "description": "Dark mode toggle stuck."},
        )
        complaint = Complaint.objects.get(subject="App issue")
        self.assertEqual(complaint.reported_professional_name, "")
