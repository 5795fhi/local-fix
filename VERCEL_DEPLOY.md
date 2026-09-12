# LocalFix on Vercel

LocalFix is a server-rendered Django application. Vercel detects `manage.py`
and `localfix/wsgi.py`; `vercel.json` only defines the static collection build.

## Required production services

Vercel Functions do not provide durable local storage, so configure:

- A managed PostgreSQL database, exposed as `DATABASE_URL`.
- An SMTP provider for email.
- A Groq API key if the AI assistant should use the hosted model.

## Vercel environment variables

Set these for Production, Preview, and Development as appropriate:

```text
DJANGO_SECRET_KEY=<long-random-secret>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=.vercel.app,your-domain.example
DJANGO_CSRF_TRUSTED_ORIGINS=https://*.vercel.app,https://your-domain.example
DATABASE_URL=postgresql://...
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
5. Run migrations against the production database from a trusted release environment:

   ```bash
   python manage.py migrate --noinput
   ```

6. Create the first admin account from that same environment:

   ```bash
   python manage.py createsuperuser
   ```

Do not run `seed_demo` in production unless this is a disposable demo project.

## Important Vercel constraints

- Do not rely on SQLite for production data.
- Profiles use built-in letter avatars, so no upload storage is required.
- Long-running background jobs and WebSockets need a separate worker/service;
  this application currently uses request/response flows suitable for Vercel Functions.
- Preview deployments need their own database policy if users will create data there.
