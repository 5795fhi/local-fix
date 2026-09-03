from django.test import TestCase
from django.urls import reverse

from accounts.models import ProviderProfile, User


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
