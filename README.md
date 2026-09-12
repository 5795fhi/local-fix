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
| Customer | `aarti.deshmukh@example.com` | `customer12345` |
| Provider (approved) | `rohit.pawar@example.com` | `provider12345` |
| Provider (pending approval) | `suresh.kamble@example.com` | `provider12345` |

All demo users use the `@example.com` domain. More customers: `rohan.mehta@`,
`sanjana.iyer@`, `meera.joshi@`. More providers: `sameer.shaikh@`,
`ganesh.joshi@`, `sachin.deshmukh@`, `vaishali.patil@`, `faisal.ansari@`
… (same role passwords).

## What's seeded

- 8 service categories with INR base prices (Plumbing ₹449, Electrical ₹499,
  AC service ₹799, …)
- **48 Indian service professionals** spread across all categories, located on
  Mumbai's Western Railway line from **Churchgate to Virar** (Andheri West,
  Bandra West, Borivali West, Vasai, Nalasopara, Virar, …) — 44 approved + 4
  pending approval, each with a locally generated avatar image under `media/avatars/`
- 4 Indian customers with realistic Mumbai society addresses
- 7 bookings covering **every lifecycle state** (requested, accepted, in progress,
  completed, paid, rejected, cancelled) with full status history
- Succeeded + pending demo payments with platform fee / provider payout split
- A 5★ review on a paid booking with recalculated provider rating
- Lifecycle notifications and an open complaint
- Demo login/registration flow issues OTP codes in demo mode (shown in the UI
  banner and server console) until real SMTP credentials are configured

## Project structure

```
accounts/      custom user (email login), roles, provider profiles, OTP verify
services/      categories + provider directory/search
bookings/      booking state machine + status history
payments/      mock payment gateway with idempotency keys
reviews/       one review per paid booking, rating aggregation
complaints/    customer/provider disputes + admin triage
notifications/ in-app notification centre
assistant/     AI helper (Groq API via the official SDK, rule-based fallback without a key)
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

## Setting up real email

The app sends **real emails** for: OTP verification (register, login, password
change, email change), the one-time welcome email, booking status updates
(requested/accepted/in-progress/completed/paid/rejected/cancelled — both
customer and provider get theirs), and contact-form messages. Everything flows
through `accounts/emails.py` + `templates/emails/`.

**You only have to do three things:**

1. **Pick a provider and get SMTP credentials** (any one of these works):

   | Provider | EMAIL_HOST | Port | Notes |
   |---|---|---|---|
   | **Gmail** (easiest for testing) | `smtp.gmail.com` | 587 | Enable 2-step verification on your Google account, then create an **App Password** at https://myaccount.google.com/apppasswords — use that 16-character password, not your normal one |
   | **Brevo** (free 300/day) | `smtp-relay.brevo.com` | 587 | Sign up at brevo.com → SMTP & API page shows your login (an email) and SMTP key |
   | **Mailgun** | `smtp.mailgun.org` | 587 | Add + verify your domain first |
   | **AWS SES** | `email-smtp.ap-south-1.amazonaws.com` | 587 | Verify sender + move out of sandbox |

2. **Fill these in `.env`** (already listed in `.env.example`):

   ```env
   EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_HOST_USER=youraddress@gmail.com
   EMAIL_HOST_PASSWORD=your-16-char-app-password
   EMAIL_USE_TLS=True
   DEFAULT_FROM_EMAIL=LocalFix <youraddress@gmail.com>
   SITE_BASE_URL=http://127.0.0.1:8000   # your public URL in production
   CONTACT_EMAIL=where-contact-form-goes@example.com
   ```

3. **Restart the server and test.** Register a new account with a real email
   address — the OTP lands in the inbox (5-minute validity). The console backend
   is used automatically whenever `EMAIL_HOST` is empty, so local dev without
   credentials still prints codes to the terminal and the demo UI banner.

Gmail notes: the "From" address must be your Gmail account or a verified alias.
For production, prefer Brevo/Mailgun/SES over Gmail — Gmail throttles bulk mail
and app passwords can be revoked.

## Deploying to Render with MySQL

The app auto-detects the database from `MYSQL_URL` (falls back to SQLite when
unset — local dev needs no database setup). PyMySQL is bundled and installed as
`MySQLdb` inside `localfix/settings.py`, so no C dependencies are required.

1. Push this repo to GitHub.
2. On Render: **New → Blueprint**, select the repo — `render.yaml` provisions a
   web service + a MySQL database and wires `MYSQL_URL` automatically. Or create
   them manually:
   - **New → MySQL** — create the database.
   - **New → Web Service** — runtime Python, build `./build.sh`, start
     `gunicorn localfix.wsgi:application --bind 0.0.0.0:$PORT`.
3. Set the env vars listed in `render.yaml` (secret key is auto-generated;
   `MYSQL_URL` is injected if you use the blueprint).
4. `build.sh` runs migrations, collects static files and loads the demo seed on
   first deploy. **After go-live, delete the `seed_demo` block from `build.sh`**
   (it clears and recreates `@example.com` users on every deploy).
5. Media uploads (avatars) need a **persistent disk**: mount at `/var/data` and
   set `MEDIA_ROOT=/var/data/media`. On the free plan uploads vanish on redeploys.
6. Set `SITE_BASE_URL` to your Render URL so links inside emails work.

Prefer Postgres or Neon instead? Set `DATABASE_URL=postgres://…` — the settings
support both schemes out of the box.

## Tests

```bash
python manage.py test
```
