# LocalFix — Local Electrician, Plumber & Carpenter Booking

LocalFix is a centralized web platform that connects customers with trusted local
service professionals (electricians, plumbers, carpenters, appliance technicians
and more). Customers browse categories, compare verified providers, book a time,
pay securely through a demo gateway and review completed work. Providers manage
their profile, services, availability and incoming jobs. Administrators verify
providers, moderate complaints and oversee the platform.

**Stack decision:** the source synopsis mentions both Django and Node/Express.
The existing starter files are a coherent **Django 5 + SQLite** project (server-
rendered templates), so this is the documented, chosen stack. The frontend is
**pure HTML/CSS/JS** — a custom design system with zero frameworks, per project
requirements (no React).

## Quick start

```bash
python -m venv venv
source venv/Scripts/activate        # Windows (venv/bin/activate on macOS/Linux)
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_demo          # full demo dataset (idempotent)
python manage.py runserver
```

Open http://127.0.0.1:8000/

## Demo accounts (from `seed_demo`)

| Role | Email | Password |
|---|---|---|
| Administrator | `admin@localfix.test` | `admin12345` |
| Customer | `casey.jordan@example.com` | `customer12345` |
| Provider (approved) | `ava.turner@example.com` | `provider12345` |
| Provider (pending approval) | `ruth.kim@example.com` | `provider12345` |

More providers: `liam.reed@`, `noah.blake@`, `mia.cole@`, `emma.shaw@`,
`omar.diaz@` `…@example.com` (same password). Customers `priya.nair@`,
`tom.olsen@` (same customer password).

## What's seeded

- 8 service categories incl. the five core ones (Electrical, Plumbing, Carpentry,
  Appliance Repair, Home Maintenance)
- 6 approved providers + 1 pending approval
- 7 bookings covering **every lifecycle state** (requested, accepted, in progress,
  completed, paid, rejected, cancelled) with full status history
- Succeeded + pending demo payments with platform fee / provider payout split
- A 5★ review on a paid booking with recalculated provider rating
- Lifecycle notifications and an open complaint
- Demo login/registration flow issues OTP codes in demo mode (shown in the UI
  banner and server console)

## Project structure

```
accounts/      custom user (email login), roles, provider profiles, OTP verify
services/      categories + provider directory/search
bookings/      booking state machine + status history
payments/      mock payment gateway with idempotency keys
reviews/       one review per paid booking, rating aggregation
complaints/    customer/provider disputes + admin triage
notifications/ in-app notification centre
assistant/     AI helper (Vercel AI gateway, rule-based fallback without a key)
core/          landing page, role dashboards, demo seed command
templates/     server-rendered UI (Django templates)
static/        css/app.css (design system) + js/app.js (vanilla JS behaviours)
```

## Key behaviours

- **Booking state machine** — `requested → accepted → in progress → completed →
  paid`, with `rejected`/`cancelled` terminal states; invalid transitions are
  rejected server-side and logged to history.
- **Payments** — amounts recomputed server-side, idempotency key prevents double
  charging, receipt per booking. No real credentials are collected.
- **Authorization** — role decorators, participant-only booking access,
  admin-only moderation. Frontend hiding is never the only guard.
- **Reviews** — only customers, only paid bookings, one per booking (DB-level
  uniqueness via OneToOne).
- **UI** — responsive dark/light themes, scroll-reveal and micro-interaction
  animations with `prefers-reduced-motion` support, mobile drawer navigation.

## Environment

Copy `.env.example` to `.env` for local settings. `DATABASE_URL` switches the
project from SQLite to Postgres for production; secret key and debug flags are
also read from the environment.

## Tests

```bash
python manage.py test
```
