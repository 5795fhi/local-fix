"""
Django settings for the LocalFix project.

LocalFix connects customers with local service providers (electricians,
plumbers, carpenters, cleaners, etc.), managing the full booking lifecycle
from request to payment, reviews, and complaints.
"""
from pathlib import Path
import os

import dj_database_url
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

DEBUG = os.environ.get("DJANGO_DEBUG", "True").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,.vercel.app").split(",")
    if h.strip()
]

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

# Database: Neon Postgres via DATABASE_URL, SQLite fallback for local dev.
_database_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
if _database_url:
    DATABASES = {
        "default": dj_database_url.parse(
            _database_url,
            conn_max_age=600,
            ssl_require=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

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

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

# --- LocalFix domain settings -------------------------------------------------
# OTP configuration for phone/email verification.
OTP_LENGTH = 6
OTP_TTL_SECONDS = 5 * 60  # OTP valid for 5 minutes
OTP_MAX_ATTEMPTS = 5

# Platform commission taken from each completed booking (percentage).
PLATFORM_COMMISSION_PERCENT = 10

# AI assistant (Vercel AI Gateway).
AI_GATEWAY_API_KEY = os.environ.get("AI_GATEWAY_API_KEY", "")
AI_GATEWAY_BASE_URL = os.environ.get(
    "AI_GATEWAY_BASE_URL", "https://ai-gateway.vercel.sh/v1"
)
LOCALFIX_AI_MODEL = os.environ.get("LOCALFIX_AI_MODEL", "openai/gpt-4o-mini")

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
