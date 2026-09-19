# LocalFix on Vercel

LocalFix is a server-rendered Django application. Vercel detects `manage.py`
and `localfix/wsgi.py`; `vercel.json` uses the Django framework preset, runs
`collectstatic` at build time, and marks `/static/` assets immutable at the edge
(WhiteNoise serves content-hashed filenames, so this is always safe).

## Required production services

Vercel Functions do not provide durable local storage, so configure:

- A Neon PostgreSQL database, exposed as `NEON_DATABASE_URL`.
- An SMTP provider for email.
- A Groq API key if the AI assistant should use the hosted model.

## Vercel environment variables

Set these for Production, Preview, and Development as appropriate:

```text
DJANGO_SECRET_KEY=<long-random-secret>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=.vercel.app,your-domain.example
DJANGO_CSRF_TRUSTED_ORIGINS=https://*.vercel.app,https://your-domain.example
NEON_DATABASE_URL=postgresql://...neon.tech/...?...sslmode=require
SITE_BASE_URL=https://your-domain.example

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=<smtp-host>
EMAIL_PORT=587
EMAIL_HOST_USER=<smtp-user>
EMAIL_HOST_PASSWORD=<smtp-password>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=LocalFix <no-reply@your-domain.example>
CONTACT_EMAIL=<support-address>

GROQ_API_KEY=<optional>
LOCALFIX_AI_MODEL=openai/gpt-oss-20b
```

## First deployment

1. Push the repository to GitHub and import it into Vercel.
2. Select the repository root as the project root and keep the Django framework preset.
3. Add the environment variables above before the first production deployment.
4. Deploy and check `/`, `/accounts/login/`, `/admin/`, and `/assistant/`.
5. Run migrations against Neon from a trusted release environment:

   ```bash
   python manage.py migrate --noinput
   ```

6. Create the first admin account from that same environment:

   ```bash
   python manage.py createsuperuser
   ```

Do not run `seed_demo` in production unless this is a disposable demo project.

## Verifying which code is live

Open `https://<your-app>.vercel.app/versionz/` after any deployment. It returns
the git commit the running build came from:

```json
{"app": "localfix", "commit": "<short-sha>", "debug": false}
```

The `commit` must match the top of `git log` for the deployment you expect.
If it shows an older commit, the deployment was built from stale code (see
troubleshooting below).

## Health checks

- `GET /healthz/` — liveness. Proves the app is up; never touches the database,
  so it stays green even during a database outage. Use this for uptime alerts.
- `GET /healthz/db/` — readiness. Verifies database connectivity (with
  latency), reports pending migrations as `"status": "degraded"`, and returns
  HTTP 503 when the database is unreachable. Use this to confirm Neon is wired
  up correctly after a deploy.

## Troubleshooting

- **Any page answers `500` with `relation "accounts_providerprofile" does not exist`**
  (or a similar missing table) — the database Vercel points at has no schema yet.
  The build command now runs `python manage.py migrate --noinput`, so a new
  deployment fixes it automatically. To apply it without a rebuild, run the
  migration against the same URL the deployment uses:

  ```bash
  NEON_DATABASE_URL="<the production connection string>" python manage.py migrate --noinput
  ```

  Remove `migrate` from `buildCommand` if you prefer to run migrations by hand
  with a release step; leaving it in means every deploy keeps the schema current.
- **`/contact/` answers 500 with `ValueError: Invalid address "..."`** — a
  configured address (`CONTACT_EMAIL` / `DEFAULT_FROM_EMAIL`) or a visitor's
  input ended with a trailing dot, which Django's mail sanitizer rejects even
  with `fail_silently`. Addresses from the environment are now normalized in
  `settings.py`, the contact form validates visitor input, and delivery
  failures are logged instead of raising. If it still appears, check the
  variable's value for stray quotes, a leading `https://` or a trailing dot.
- **Every page answers `400 Bad Request` (Vercel shows the Django function
  running, e.g. "Route: /django", with a `Host: <app>-<hash>-<team>.vercel.app`)**
  — Django rejected the host (`DisallowedHost`). `DJANGO_ALLOWED_HOSTS` on the
  deployment was blank, pasted with a scheme, or listed only a custom domain,
  so the `*.vercel.app` URL matched nothing. The code now always merges the
  platform hosts, so this cannot happen again; during the window before that
  fix is deployed, either clear the variable (the default includes
  `.vercel.app`) or set it to `.vercel.app,your-domain.example` — no quotes, no
  `https://` — then redeploy, because environment changes only apply to new
  deployments.
- **Build fails with `ValueError: invalid literal for int() ... DB_CONN_MAX_AGE`**
  — this crash is fully fixed in the current code (`manage.py` normalizes an
  empty value to `0`; `settings.py` parses numerics defensively). If you still
  see it, the build is running old code: redeploy from the **latest** deployment
  entry with "Use existing Build Cache" unchecked.
- **Redeploy button rebuilds old code** — "Redeploy" on a *failed/old*
  deployment entry rebuilds that entry's original commit. Instead, push an
  (empty is fine) commit to trigger a fresh build from the tip, or redeploy the
  top-most entry with the build cache disabled.
- **`ImproperlyConfigured: NEON_DATABASE_URL ... must be set`** at build time —
  set `NEON_DATABASE_URL` (Production scope) before deploying with
  `DJANGO_DEBUG=False`. The build imports settings for `collectstatic`, so the
  database variable must exist even though the build itself never touches the
  database.

## Important Vercel constraints

- Do not rely on SQLite for production data.
- Profiles use built-in letter avatars, so no upload storage is required.
- Long-running background jobs and WebSockets need a separate worker/service;
  this application currently uses request/response flows suitable for Vercel Functions.
- Preview deployments need their own database policy if users will create data there.
