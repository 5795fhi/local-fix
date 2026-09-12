"""
Django settings for the LocalFix project.

LocalFix connects customers with local service providers (electricians,
plumbers, carpenters, cleaners, etc.), managing the full booking lifecycle
from request to payment, reviews, and complaints.
"""
from pathlib import Path
import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from a local .env file if present. On Vercel/Neon
# the variables are injected into the environment directly.
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.development.local", override=False)

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-key-change-in-production-0123456789abcdef",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.vercel.app").split(",")
    if h.strip()
]


def _env_int(name, default):
    """Read an integer env var; fall back to `default` when unset, empty or invalid.

    Deploy panels (Vercel/Render) often contain variables that were created but
    left blank; a bare int(os.environ[...]) would then crash at import time.
    """
    raw = os.environ.get(name, "")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "DJANGO_CSRF_TRUSTED_ORIGINS", "https://*.vercel.app"
    ).split(",")
    if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # LocalFix apps
    "accounts.apps.AccountsConfig",
    "services.apps.ServicesConfig",
    "bookings.apps.BookingsConfig",
    "payments.apps.PaymentsConfig",
    "reviews.apps.ReviewsConfig",
    "complaints.apps.ComplaintsConfig",
    "notifications.apps.NotificationsConfig",
    "assistant.apps.AssistantConfig",
    "core.apps.CoreConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "notifications.middleware.NotificationCountMiddleware",
]

ROOT_URLCONF = "localfix.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.site_context",
            ],
        },
    },
]

WSGI_APPLICATION = "localfix.wsgi.application"
ASGI_APPLICATION = "localfix.asgi.application"

# Database: Neon PostgreSQL in deployed environments, SQLite for local dev.
# Set NEON_DATABASE_URL to the pooled or direct Neon connection string.
_database_url = (
    os.environ.get("NEON_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or os.environ.get("POSTGRES_URL")
)
# Vercel functions should not hold database connections open between invocations.
# An empty Vercel environment variable must not crash settings import during
# collectstatic; use zero unless an explicit value is supplied.
_db_conn_max_age = int(
    os.environ.get("DB_CONN_MAX_AGE") or "0"
)
if _database_url:
    DATABASES = {
        "default": dj_database_url.parse(
            _database_url,
            conn_max_age=_db_conn_max_age,
            ssl_require=True,
        )
    }
elif DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    raise ImproperlyConfigured(
        "NEON_DATABASE_URL (or DATABASE_URL) must be set when DJANGO_DEBUG=False."
    )

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "core:home"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# --- LocalFix domain settings -------------------------------------------------
# OTP configuration for phone/email verification.
OTP_LENGTH = 6
OTP_TTL_SECONDS = 5 * 60  # OTP valid for 5 minutes
OTP_MAX_ATTEMPTS = 5

# --- Email --------------------------------------------------------------------
# Real SMTP delivery. Copy .env.example -> .env and fill in your provider's
# credentials (Gmail app password, Brevo, Mailgun, SES...). With no EMAIL_HOST
# set, mail falls back to the console backend so dev still works.
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = _env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() in ("1", "true", "yes")
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "False").lower() in ("1", "true", "yes")
EMAIL_TIMEOUT = _env_int("EMAIL_TIMEOUT", 10)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "LocalFix <no-reply@localfix.test>")
# Absolute base URL used in email links (set to your deployed domain in prod).
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "http://127.0.0.1:8000")
# Where contact-form messages are delivered.
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "support@localfix.test")

# Platform commission taken from each completed booking (percentage).
PLATFORM_COMMISSION_PERCENT = 10

# AI assistant (Groq).
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
LOCALFIX_AI_MODEL = os.environ.get("LOCALFIX_AI_MODEL", "openai/gpt-oss-20b")

# Security hardening for production (behind HTTPS on Vercel).
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 63072000
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "SAMEORIGIN"
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
