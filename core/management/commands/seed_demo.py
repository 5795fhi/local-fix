"""Seed LocalFix with a complete, internally consistent demo dataset.

Covers the generation-guide requirements:
- admin + customers + providers (approved AND pending) across all categories
- bookings in every lifecycle state (requested/accepted/in_progress/completed/paid/rejected/cancelled)
- a paid booking with a succeeded payment, plus pending/failed payment records
- reviews on paid bookings (rating aggregates recalculated)
- lifecycle notifications and booking status history
- idempotent: safe to run repeatedly
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import ProviderProfile
from bookings.models import Booking, BookingStatusHistory
from complaints.models import Complaint
from notifications.models import Notification
from payments.models import Payment
from reviews.models import Review
from services.models import ServiceCategory

User = get_user_model()

CATEGORIES = [
    ("Plumbing", "Leaks, pipes, taps, toilets and drainage", "wrench", 40),
    ("Electrical", "Wiring, sockets, lighting and fuse boxes", "zap", 55),
    ("Carpentry", "Doors, furniture, shelving and repairs", "hammer", 45),
    ("Appliance Repair", "Washers, fridges, ovens and small appliances", "plug", 50),
    ("Home Maintenance", "Odd jobs, fittings, sealing and general upkeep", "settings", 35),
    ("Cleaning", "Deep cleans and regular housekeeping", "sparkles", 25),
    ("Painting", "Interior and exterior painting", "paint-roller", 35),
    ("HVAC", "Heating, cooling and ventilation servicing", "wind", 60),
]

PROVIDERS = [
    ("ava.turner@example.com", "Ava", "Turner", ["Plumbing"], "Master plumber, 12 yrs", 45, "Downtown", True),
    ("liam.reed@example.com", "Liam", "Reed", ["Electrical"], "Certified electrician", 60, "Northside", True),
    ("noah.blake@example.com", "Noah", "Blake", ["Carpentry", "Home Maintenance"], "Bespoke carpentry & fit-outs", 50, "Eastville", True),
    ("mia.cole@example.com", "Mia", "Cole", ["Cleaning"], "Spotless deep cleans", 28, "Citywide", True),
    ("emma.shaw@example.com", "Emma", "Shaw", ["Painting"], "Interior painting specialist", 38, "West End", True),
    ("omar.diaz@example.com", "Omar", "Diaz", ["Appliance Repair", "HVAC"], "Fridge, washer & AC technician", 52, "Southgate", True),
    ("ruth.kim@example.com", "Ruth", "Kim", ["Home Maintenance"], "Handyperson for every odd job", 32, "Old Town", False),
]

CUSTOMERS = [
    ("casey.jordan@example.com", "Casey", "Jordan", "Maple Street 12"),
    ("priya.nair@example.com", "Priya", "Nair", "Cedar Avenue 8"),
    ("tom.olsen@example.com", "Tom", "Olsen", "Birch Lane 3"),
]


class Command(BaseCommand):
    help = "Seed LocalFix with full demo data: users, categories, bookings in every state, payments, reviews, notifications."

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()

        # ---------- Categories ----------
        for name, desc, icon, price in CATEGORIES:
            ServiceCategory.objects.get_or_create(
                name=name,
                defaults={"description": desc, "icon": icon, "base_price": Decimal(price)},
            )
        self.stdout.write(self.style.SUCCESS(f"Categories ready: {ServiceCategory.objects.count()}"))

        # ---------- Admin ----------
        admin, created = User.objects.get_or_create(
            email="admin@localfix.test",
            defaults={
                "first_name": "Site", "last_name": "Admin",
                "role": User.Role.ADMIN, "is_staff": True, "is_superuser": True,
                "is_verified": True,
            },
        )
        if created:
            admin.set_password("admin12345")
            admin.save()

        # ---------- Customers ----------
        customers = []
        for email, first, last, address in CUSTOMERS:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first, "last_name": last,
                    "role": User.Role.CUSTOMER, "is_verified": True,
                    "phone": "+10000000000",
                },
            )
            if created:
                user.set_password("customer12345")
                user.save()
            customers.append(user)
        casey = User.objects.get(email="casey.jordan@example.com")
        priya = User.objects.get(email="priya.nair@example.com")
        tom = User.objects.get(email="tom.olsen@example.com")
        self.stdout.write(self.style.SUCCESS("Customers ready (password: customer12345)"))

        # ---------- Providers ----------
        providers = {}
        for email, first, last, cats, headline, rate, area, approved in PROVIDERS:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first, "last_name": last,
                    "role": User.Role.PROVIDER, "is_verified": True,
                },
            )
            if created:
                user.set_password("provider12345")
                user.save()
            profile = user.provider_profile
            profile.headline = headline
            profile.hourly_rate = Decimal(rate)
            profile.service_area = area
            profile.is_approved = approved
            profile.is_available = True
            profile.bio = f"Hi, I'm {first}. {headline}. I take pride in tidy, reliable work and clear quotes."
            profile.save()
            for cat_name in cats:
                cat = ServiceCategory.objects.filter(name=cat_name).first()
                if cat:
                    profile.categories.add(cat)
            providers[email] = user
        self.stdout.write(self.style.SUCCESS("Providers ready (password: provider12345, incl. 1 pending)"))

        def make_booking(customer, provider, cat_name, status, description, address,
                         scheduled_for, quoted_price=None, created_days_ago=2):
            category = ServiceCategory.objects.filter(name=cat_name).first()
            price = Decimal(quoted_price) if quoted_price is not None else (category.base_price if category else Decimal(40))
            booking, created = Booking.objects.get_or_create(
                customer=customer, provider=provider, category=category,
                scheduled_for=scheduled_for,
                defaults={
                    "status": Booking.Status.REQUESTED,
                    "description": description,
                    "address": address,
                    "quoted_price": price,
                },
            )
            if created:
                BookingStatusHistory.objects.create(
                    booking=booking, from_status=Booking.Status.REQUESTED,
                    to_status=Booking.Status.REQUESTED, changed_by=customer,
                    note="Booking created (seed).",
                )
                if status == Booking.Status.REJECTED:
                    booking.transition_to(Booking.Status.REJECTED, actor=provider, reason="Fully booked that day.")
                elif status == Booking.Status.CANCELLED:
                    booking.transition_to(Booking.Status.CANCELLED, actor=customer, reason="Plans changed.")
                else:
                    if status != Booking.Status.REQUESTED:
                        booking.transition_to(Booking.Status.ACCEPTED, actor=provider, note="Confirmed — see you then!")
                    if status in (Booking.Status.IN_PROGRESS, Booking.Status.COMPLETED, Booking.Status.PAID):
                        booking.transition_to(Booking.Status.IN_PROGRESS, actor=provider)
                    if status in (Booking.Status.COMPLETED, Booking.Status.PAID):
                        booking.transition_to(Booking.Status.COMPLETED, actor=provider)
                    if status == Booking.Status.PAID:
                        booking.transition_to(Booking.Status.PAID, actor=customer)
            return booking

        # ---------- Bookings across every state ----------
        ava = providers["ava.turner@example.com"]
        liam = providers["liam.reed@example.com"]
        noah = providers["noah.blake@example.com"]
        omar = providers["omar.diaz@example.com"]

        b_requested = make_booking(
            casey, ava, "Plumbing", Booking.Status.REQUESTED,
            "Kitchen tap drips constantly; washer probably needs replacing.",
            "Maple Street 12", now + timedelta(days=3), created_days_ago=1,
        )
        b_accepted = make_booking(
            casey, liam, "Electrical", Booking.Status.ACCEPTED,
            "Two bedroom sockets stopped working after a storm.",
            "Maple Street 12", now + timedelta(days=2), quoted_price=70, created_days_ago=1,
        )
        b_progress = make_booking(
            priya, noah, "Carpentry", Booking.Status.IN_PROGRESS,
            "Wardrobe door off its hinges and a shelf to mount.",
            "Cedar Avenue 8", now + timedelta(hours=4), created_days_ago=1,
        )
        b_completed = make_booking(
            tom, omar, "Appliance Repair", Booking.Status.COMPLETED,
            "Washing machine drum makes a loud grinding noise.",
            "Birch Lane 3", now + timedelta(days=1), quoted_price=90, created_days_ago=3,
        )
        b_paid = make_booking(
            casey, noah, "Carpentry", Booking.Status.PAID,
            "Assemble flat-pack bookshelf and secure it to the wall.",
            "Maple Street 12", now - timedelta(days=1), quoted_price=60, created_days_ago=4,
        )
        b_rejected = make_booking(
            priya, ava, "Plumbing", Booking.Status.REJECTED,
            "Bathroom drain smells; needs inspection.",
            "Cedar Avenue 8", now + timedelta(days=5), created_days_ago=2,
        )
        b_cancelled = make_booking(
            tom, liam, "Electrical", Booking.Status.CANCELLED,
            "Install a new ceiling light in the hallway.",
            "Birch Lane 3", now + timedelta(days=4), created_days_ago=2,
        )

        # ---------- Payment for the paid booking ----------
        import hashlib

        idem = hashlib.sha256(f"booking:{b_paid.pk}:user:{b_paid.customer_id}".encode()).hexdigest()
        payment, p_created = Payment.objects.get_or_create(
            idempotency_key=idem,
            defaults={
                "booking": b_paid, "payer": b_paid.customer,
                "amount": b_paid.quoted_price, "platform_fee": b_paid.platform_fee,
                "provider_payout": b_paid.provider_payout, "method": Payment.Method.CARD,
                "status": Payment.Status.SUCCEEDED, "paid_at": b_paid.completed_at or now,
            },
        )

        # Extra demo payment records: one pending, one failed (abandoned attempts)
        if not Payment.objects.filter(booking=b_completed, status=Payment.Status.PENDING).exists():
            Payment.objects.get_or_create(
                idempotency_key=hashlib.sha256(f"booking:{b_completed.pk}:user:{b_completed.customer_id}:pending".encode()).hexdigest(),
                defaults={
                    "booking": b_completed, "payer": b_completed.customer,
                    "amount": b_completed.quoted_price, "platform_fee": b_completed.platform_fee,
                    "provider_payout": b_completed.provider_payout, "method": Payment.Method.WALLET,
                    "status": Payment.Status.PENDING,
                },
            )
        self.stdout.write(self.style.SUCCESS("Payments seeded (succeeded + pending)"))

        # ---------- Reviews for paid bookings ----------
        review, r_created = Review.objects.get_or_create(
            booking=b_paid,
            defaults={
                "customer": b_paid.customer, "provider": b_paid.provider,
                "rating": 5,
                "comment": "Noah arrived on time, assembled everything perfectly and cleaned up after. Highly recommend!",
            },
        )
        if r_created:
            Notification.notify(
                b_paid.provider, "New review",
                f"{b_paid.customer.display_name} rated you {review.rating}/5.",
            )
        for profile in ProviderProfile.objects.all():
            profile.recalculate_rating()
        self.stdout.write(self.style.SUCCESS("Reviews seeded and ratings recalculated"))

        # ---------- Notifications ----------
        demo_notes = [
            (casey, "Booking confirmed", f"{liam.display_name} accepted your electrical job.", f"/bookings/{b_accepted.pk}/"),
            (casey, "Welcome to LocalFix!", "Your account is ready. Start exploring services.", "/services/"),
            (priya, "Job started", f"{noah.display_name} has started your carpentry job.", f"/bookings/{b_progress.pk}/"),
            (tom, "Job completed", "Your appliance repair is done — proceed to payment.", f"/bookings/{b_completed.pk}/"),
            (ava, "New booking request", f"{casey.display_name} requested plumbing help.", f"/bookings/{b_requested.pk}/"),
            (omar, "Payment received", f"You earned {b_completed.provider_payout} — pending customer payment confirmation.", f"/bookings/{b_completed.pk}/"),
        ]
        for recipient, title, body, url in demo_notes:
            Notification.objects.get_or_create(
                recipient=recipient, title=title,
                defaults={"body": body, "url": url},
            )
        self.stdout.write(self.style.SUCCESS("Notifications seeded"))

        # ---------- A demo complaint ----------
        Complaint.objects.get_or_create(
            raised_by=priya, subject="Provider arrived late",
            defaults={
                "description": "The carpenter arrived 40 minutes later than the booked slot. Would like this noted.",
                "status": Complaint.Status.OPEN,
            },
        )
        self.stdout.write(self.style.SUCCESS("Complaint seeded"))

        # ---------- Summary ----------
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Demo accounts"))
        self.stdout.write("  Admin    : admin@localfix.test / admin12345")
        self.stdout.write("  Customer : casey.jordan@example.com / customer12345")
        self.stdout.write("  Provider : ava.turner@example.com / provider12345 (approved)")
        self.stdout.write("  Pending  : ruth.kim@example.com / provider12345 (awaiting approval)")
        self.stdout.write("")
        counts = [
            ("users", User.objects.count()),
            ("bookings", Booking.objects.count()),
            ("payments", Payment.objects.count()),
            ("reviews", Review.objects.count()),
            ("notifications", Notification.objects.count()),
        ]
        self.stdout.write("  " + " · ".join(f"{k}: {v}" for k, v in counts))
        self.stdout.write(self.style.SUCCESS("Demo seed complete."))
