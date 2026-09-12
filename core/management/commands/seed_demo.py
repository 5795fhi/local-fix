"""Seed LocalFix with a complete, internally consistent Indian demo dataset.

- 48 service professionals spread across every category, located on Mumbai's
  Western Railway line from Churchgate to Virar
- Indian customers with realistic Mumbai addresses
- INR pricing (₹ per hour / visit)
- Bookings in every lifecycle state, payments, reviews, notifications
- A locally generated avatar image for each seeded user (SVG letter-avatar,
  saved under MEDIA_ROOT/avatars/), so profiles have real images without any
  external download
- Idempotent: re-running replaces the demo dataset (all @example.com users)
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
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

DEMO_EMAIL_DOMAIN = "example.com"

CATEGORIES = [
    ("Plumbing", "Leaks, taps, pipes, toilets and drainage work", "wrench", 449),
    ("Electrical", "Wiring, sockets, fans, lighting and MCB boards", "zap", 499),
    ("Carpentry", "Doors, furniture, wardrobes and wood repairs", "hammer", 549),
    ("Appliance Repair", "Washing machines, fridges, ovens and microwaves", "plug", 599),
    ("Home Maintenance", "Odd jobs, fittings, sealing and general upkeep", "settings", 349),
    ("Cleaning", "Deep cleaning and regular housekeeping", "sparkles", 249),
    ("Painting", "Interior and exterior painting, putty and polish", "paint-roller", 399),
    ("HVAC", "AC servicing, installation and gas refilling", "wind", 799),
]

# Western Railway local line, south → north: Churchgate … Virar.
CHURCHGATE_TO_VIRAR = [
    "Churchgate", "Marine Lines", "Charni Road", "Grant Road",
    "Mumbai Central", "Mahalaxmi", "Lower Parel", "Dadar West",
    "Bandra West", "Khar West", "Santacruz West", "Vile Parle West",
    "Andheri West", "Jogeshwari West", "Goregaon West", "Malad West",
    "Kandivali West", "Borivali West", "Dahisar East", "Mira Road",
    "Bhayandar West", "Naigaon", "Vasai West", "Nalasopara West",
    "Virar West",
]

# (first, last, categories, headline, ₹/hr, station, years, approved)
PROVIDERS = [
    # Plumbing
    ("Rohit", "Pawar", ["Plumbing"], "Bathroom & kitchen leak specialist, 12 yrs in Andheri", 450, "Andheri West", 12, True),
    ("Sameer", "Shaikh", ["Plumbing"], "Tap, flush tank and drainage expert", 380, "Bandra West", 8, True),
    ("Kiran", "Sawant", ["Plumbing"], "Pipe-line repairs and new bathroom fittings", 500, "Borivali West", 10, True),
    ("Ramesh", "Yadav", ["Plumbing"], "Borewell and overhead tank plumbing", 350, "Vasai West", 15, True),
    ("Nilesh", "Mhatre", ["Plumbing"], "Water purifier & sink blockage expert", 420, "Malad West", 6, True),
    ("Jignesh", "Patel", ["Plumbing"], "High-rise society plumbing contractor", 550, "Churchgate", 9, True),
    ("Suresh", "Kamble", ["Plumbing"], "Same-day leak fixes, western suburbs", 330, "Nalasopara West", 11, False),
    # Electrical
    ("Sachin", "Deshmukh", ["Electrical", "Home Maintenance"], "Licensed electrician — wiring, MCB, inverter", 600, "Dadar West", 14, True),
    ("Prakash", "Jadhav", ["Electrical"], "Fan, chandelier and tube-light fitting", 480, "Vile Parle West", 9, True),
    ("Deepak", "Gupta", ["Electrical"], "House rewiring and switchboard upgrades", 420, "Mira Road", 7, True),
    ("Imran", "Qureshi", ["Electrical"], "Short-circuit diagnosis and safety checks", 550, "Grant Road", 12, True),
    ("Vinod", "Shetty", ["Electrical"], "Doorbell, geyser and socket repairs", 380, "Kandivali West", 10, True),
    ("Amit", "Thakur", ["Electrical"], "Inverter & stabiliser installation", 450, "Virar West", 5, True),
    ("Ashok", "Gaikwad", ["Electrical"], "Society lighting and panel work", 400, "Dahisar East", 13, False),
    # Carpentry
    ("Ganesh", "Joshi", ["Carpentry"], "Modular kitchen & wardrobe carpenter", 550, "Lower Parel", 16, True),
    ("Rahul", "Naik", ["Carpentry"], "Door, drawer and lock repairs", 450, "Goregaon West", 8, True),
    ("Mahesh", "Chavan", ["Carpentry"], "Custom shelving and wall units", 500, "Santacruz West", 11, True),
    ("Bhavesh", "Shah", ["Carpentry"], "Furniture polishing and teak wood work", 650, "Marine Lines", 12, True),
    ("Vikas", "Bhoir", ["Carpentry"], "Bed, table and flat-pack assembly", 380, "Bhayandar West", 7, True),
    ("Kailas", "Salvi", ["Carpentry"], "False ceiling and kitchen trolleys", 420, "Khar West", 9, False),
    # Appliance Repair
    ("Sanjay", "Kadam", ["Appliance Repair", "Home Maintenance"], "Washing machine & dishwasher technician", 500, "Mahalaxmi", 12, True),
    ("Mohammad", "Shaikh", ["Appliance Repair"], "Refrigerator cooling & gas charging", 420, "Mumbai Central", 9, True),
    ("Pradeep", "Verma", ["Appliance Repair"], "Microwave and induction cooktop repairs", 450, "Jogeshwari West", 8, True),
    ("Pratik", "Mehta", ["Appliance Repair"], "TV, water purifier & mixer repairs", 600, "Charni Road", 6, True),
    ("Umesh", "Panchal", ["Appliance Repair"], "Geyser and room heater servicing", 400, "Naigaon", 10, True),
    ("Kishor", "Rane", ["Appliance Repair"], "Washing machine drum & motor expert", 380, "Vasai West", 14, True),
    # Cleaning
    ("Vaishali", "Patil", ["Cleaning"], "Deep home cleaning with own equipment", 250, "Andheri West", 7, True),
    ("Sneha", "Fernandes", ["Cleaning"], "Kitchen & bathroom deep cleans", 280, "Bandra West", 5, True),
    ("Ayesha", "Khan", ["Cleaning"], "Sofa shampooing and carpet cleaning", 260, "Grant Road", 8, True),
    ("Shweta", "Bhosale", ["Cleaning"], "Move-in/move-out flat cleaning", 240, "Borivali West", 6, True),
    ("Rekha", "Dubey", ["Cleaning"], "Weekly housekeeping and utensil help", 300, "Vile Parle West", 10, True),
    ("Jyoti", "Waghmare", ["Cleaning"], "Water tank and terrace cleaning", 220, "Mira Road", 4, True),
    # Painting
    ("Sunil", "Choudhary", ["Painting"], "Interior emulsion & texture painting", 400, "Dadar West", 15, True),
    ("Ravi", "Solanki", ["Painting"], "Exterior weather-coat painting", 350, "Malad West", 9, True),
    ("Manoj", "Yadav", ["Painting"], "Putty, primer and polish finish work", 320, "Nalasopara West", 11, True),
    ("Chirag", "Bhanushali", ["Painting"], "Stencil and accent wall designs", 450, "Kandivali West", 8, True),
    ("Dinesh", "More", ["Painting"], "Waterproofing before monsoon", 300, "Naigaon", 12, True),
    # HVAC
    ("Faisal", "Ansari", ["HVAC"], "AC installation & copper piping", 700, "Mumbai Central", 13, True),
    ("Santosh", "Nair", ["HVAC"], "Split AC deep service & gas refill", 650, "Santacruz West", 11, True),
    ("Rajesh", "Pandey", ["HVAC"], "Window AC repair and AMC plans", 600, "Khar West", 10, True),
    ("Akash", "Pawar", ["HVAC"], "AC jet service same-day visits", 550, "Goregaon West", 6, True),
    ("Harshad", "Kotian", ["HVAC"], "VRF & central cooling maintenance", 620, "Dahisar East", 9, True),
    # Home Maintenance
    ("Raju", "Mistry", ["Home Maintenance"], "All-round handyman — 18 yrs experience", 350, "Lower Parel", 18, True),
    ("Vikram", "Singh", ["Home Maintenance"], "Curtain rods, TV wall mount, fittings", 400, "Andheri West", 10, True),
    ("Mayur", "Vaghela", ["Home Maintenance"], "Minor plumbing-electric-carpentry jobs", 320, "Mira Road", 7, True),
    ("Rajesh", "Iyer", ["Home Maintenance"], "Door hinges, grouting and sealing", 450, "Mahalaxmi", 12, True),
    ("Sandeep", "Yadav", ["Home Maintenance"], "Furniture shifting & small repairs", 300, "Virar West", 9, True),
    ("Pradeep", "Sonawane", ["Home Maintenance"], "Monsoon-proofing and leak sealing", 280, "Vasai West", 8, True),
]

# (email, first, last, address)
CUSTOMERS = [
    ("aarti.deshmukh@example.com", "Aarti", "Deshmukh",
     "B-702, Sai Darshan CHS, SV Road, Andheri West"),
    ("rohan.mehta@example.com", "Rohan", "Mehta",
     "12/A, Sea Breeze Apartments, Carter Road, Bandra West"),
    ("sanjana.iyer@example.com", "Sanjana", "Iyer",
     "C-14, Shanti Niketan CHS, Lokhandwala, Andheri West"),
    ("meera.joshi@example.com", "Meera", "Joshi",
     "3, Krishna Kunj, Station Road, Borivali West"),
]

_AVATAR_PALETTE = [
    ("#0ea5e9", "#0369a1"), ("#f59e0b", "#b45309"), ("#10b981", "#047857"),
    ("#8b5cf6", "#6d28d9"), ("#ef4444", "#b91c1c"), ("#14b8a6", "#0f766e"),
    ("#f97316", "#c2410c"), ("#3b82f6", "#1d4ed8"), ("#ec4899", "#be185d"),
    ("#22c55e", "#15803d"), ("#6366f1", "#4338ca"), ("#e11d48", "#9f1239"),
]


def _avatar_svg(initials, idx):
    """A local SVG letter-avatar so seeded users have real images offline."""
    c1, c2 = _AVATAR_PALETTE[idx % len(_AVATAR_PALETTE)]
    safe = "".join(ch for ch in initials if ch.isalnum())[:2].upper() or "P"
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/>'
        "</linearGradient></defs>"
        '<rect width="160" height="160" rx="80" fill="url(#g)"/>'
        '<text x="80" y="84" text-anchor="middle" dominant-baseline="central" '
        'font-family="Segoe UI, Arial, sans-serif" font-size="64" font-weight="700" '
        f'fill="#ffffff">{safe}</text></svg>'
    )


class Command(BaseCommand):
    help = (
        "Seed LocalFix with Indian demo data: 48 pros on the Churchgate–Virar "
        "route, Mumbai customers, INR pricing and bookings in every state."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()

        # ---------- Replace previous demo dataset ----------
        removed, _ = User.objects.filter(email__endswith=f"@{DEMO_EMAIL_DOMAIN}").delete()
        self.stdout.write(f"Cleared {removed} previous demo record(s).")

        # ---------- Categories ----------
        for name, desc, icon, price in CATEGORIES:
            cat, _ = ServiceCategory.objects.update_or_create(
                name=name,
                defaults={
                    "description": desc,
                    "icon": icon,
                    "base_price": Decimal(price),
                    "is_active": True,
                },
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
            user = User.objects.create(
                email=email,
                first_name=first, last_name=last,
                role=User.Role.CUSTOMER, is_verified=True,
                phone=self._indian_phone(),
            )
            user.set_password("customer12345")
            user.save()
            self._attach_avatar(user)
            customers.append(user)
        aarti, rohan, sanjana, meera = customers
        self.stdout.write(self.style.SUCCESS("Customers ready (password: customer12345)"))

        # ---------- Providers (48, Churchgate → Virar) ----------
        providers = {}
        avatar_idx = 0
        for first, last, cats, headline, rate, station, years, approved in PROVIDERS:
            email = f"{first.lower()}.{last.lower()}@{DEMO_EMAIL_DOMAIN}"
            user = User.objects.create(
                email=email,
                first_name=first, last_name=last,
                role=User.Role.PROVIDER, is_verified=True,
                phone=self._indian_phone(),
            )
            user.set_password("provider12345")
            user.save()
            self._attach_avatar(user, avatar_idx)
            avatar_idx += 1

            profile = user.provider_profile
            profile.headline = headline
            profile.hourly_rate = Decimal(rate)
            profile.years_experience = years
            profile.service_area = station
            profile.is_approved = approved
            profile.is_available = True
            profile.bio = (
                f"Namaste, I'm {first}. {headline}. Based near {station} station — "
                f"I cover {station} and nearby areas on the Western line. "
                "Neat work, honest rates and a 30-day service guarantee."
            )
            profile.save()
            for cat_name in cats:
                cat = ServiceCategory.objects.filter(name=cat_name).first()
                if cat:
                    profile.categories.add(cat)
            providers[email] = user
        self.stdout.write(self.style.SUCCESS(
            f"Providers ready: {len(providers)} pros across {len(CATEGORIES)} services "
            "(password: provider12345)"
        ))

        def pro(email):
            return providers[email]

        def make_booking(customer, provider, cat_name, status, description, address,
                         scheduled_for, quoted_price=None, created_days_ago=2):
            category = ServiceCategory.objects.filter(name=cat_name).first()
            price = Decimal(quoted_price) if quoted_price is not None else (category.base_price if category else Decimal(449))
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
        b_requested = make_booking(
            aarti, pro("rohit.pawar@example.com"), "Plumbing", Booking.Status.REQUESTED,
            "Kitchen tap leaking since morning; sink drains very slowly.",
            CUSTOMERS[0][3], now + timedelta(days=3), created_days_ago=1,
        )
        b_accepted = make_booking(
            rohan, pro("sachin.deshmukh@example.com"), "Electrical", Booking.Status.ACCEPTED,
            "Two bedroom sockets stopped working after a power fluctuation.",
            CUSTOMERS[1][3], now + timedelta(days=2), quoted_price=650, created_days_ago=1,
        )
        b_progress = make_booking(
            sanjana, pro("ganesh.joshi@example.com"), "Carpentry", Booking.Status.IN_PROGRESS,
            "Wardrobe door off its hinges; need one extra shelf in the bedroom.",
            CUSTOMERS[2][3], now + timedelta(hours=4), created_days_ago=1,
        )
        b_completed = make_booking(
            meera, pro("sanjay.kadam@example.com"), "Appliance Repair", Booking.Status.COMPLETED,
            "Washing machine drum makes a loud grinding noise on spin.",
            CUSTOMERS[3][3], now + timedelta(days=1), quoted_price=850, created_days_ago=3,
        )
        b_paid = make_booking(
            rohan, pro("bhavesh.shah@example.com"), "Carpentry", Booking.Status.PAID,
            "Balcony door stuck; needs re-hinging and a fresh polish.",
            CUSTOMERS[1][3], now - timedelta(days=1), quoted_price=900, created_days_ago=4,
        )
        b_rejected = make_booking(
            sanjana, pro("kiran.sawant@example.com"), "Plumbing", Booking.Status.REJECTED,
            "Bathroom drain smells; needs inspection.",
            CUSTOMERS[2][3], now + timedelta(days=5), created_days_ago=2,
        )
        b_cancelled = make_booking(
            meera, pro("prakash.jadhav@example.com"), "Electrical", Booking.Status.CANCELLED,
            "Install a new ceiling light in the passage.",
            CUSTOMERS[3][3], now + timedelta(days=4), created_days_ago=2,
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

        # Extra demo payment record: one pending attempt on the completed booking
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

        # ---------- Review for the paid booking ----------
        paid_pro_first = b_paid.provider.first_name
        review, r_created = Review.objects.get_or_create(
            booking=b_paid,
            defaults={
                "customer": b_paid.customer, "provider": b_paid.provider,
                "rating": 5,
                "comment": (
                    f"{paid_pro_first} arrived on time, fixed the balcony door neatly and "
                    "cleaned up after. Highly recommend!"
                ),
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
            (aarti, "Booking confirmed", f"{b_accepted.provider.display_name} accepted your electrical job.", f"/bookings/{b_accepted.pk}/"),
            (aarti, "Welcome to LocalFix!", "Your account is ready. Start exploring services.", "/services/"),
            (rohan, "Job started", f"{b_progress.provider.display_name} has started your carpentry job.", f"/bookings/{b_progress.pk}/"),
            (meera, "Job completed", "Your appliance repair is done — proceed to payment.", f"/bookings/{b_completed.pk}/"),
            (b_requested.provider, "New booking request", f"{aarti.display_name} requested plumbing help.", f"/bookings/{b_requested.pk}/"),
            (b_completed.provider, "Payment received", f"You earned {b_completed.provider_payout} — pending confirmation.", f"/bookings/{b_completed.pk}/"),
        ]
        for recipient, title, body, url in demo_notes:
            Notification.objects.get_or_create(
                recipient=recipient, title=title,
                defaults={"body": body, "url": url},
            )
        self.stdout.write(self.style.SUCCESS("Notifications seeded"))

        # ---------- A demo complaint ----------
        Complaint.objects.get_or_create(
            raised_by=sanjana, subject="Provider arrived late",
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
        self.stdout.write("  Customer : aarti.deshmukh@example.com / customer12345")
        self.stdout.write("  Provider : rohit.pawar@example.com / provider12345 (approved, Andheri West)")
        self.stdout.write("  Pending  : suresh.kamble@example.com / provider12345 (awaiting approval)")
        self.stdout.write("")
        counts = [
            ("users", User.objects.count()),
            ("providers", ProviderProfile.objects.count()),
            ("bookings", Booking.objects.count()),
            ("payments", Payment.objects.count()),
            ("reviews", Review.objects.count()),
            ("notifications", Notification.objects.count()),
        ]
        self.stdout.write("  " + " · ".join(f"{k}: {v}" for k, v in counts))
        self.stdout.write(self.style.SUCCESS("Demo seed complete."))

    # ------------------------------------------------------------------
    def _indian_phone(self):
        """Deterministic +91 mobile numbers."""
        seq = getattr(self, "_phone_seq", 0) + 1
        self._phone_seq = seq
        digits = (9000000000 + seq * 738197) % 10**10
        return f"+91{digits}"

    def _attach_avatar(self, user, idx=0):
        """Save a locally generated SVG letter-avatar for the user."""
        if user.avatar:
            return
        initials = f"{user.first_name[:1]}{user.last_name[:1]}"
        slug = user.email.split("@")[0]
        svg = _avatar_svg(initials, idx)
        user.avatar.save(
            f"{slug}.svg",
            ContentFile(svg.encode("utf-8")),
            save=True,
        )
