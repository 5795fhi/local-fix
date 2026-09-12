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

DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() in ("1", "true", "yes")

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

# Database: external MySQL (PlanetScale/Aiven/Railway/...) via MYSQL_URL or
# DATABASE_URL with a mysql:// scheme, Postgres via DATABASE_URL, or SQLite
# fallback for local dev. See README "Deploying to Render with MySQL".
_database_url = (
    os.environ.get("MYSQL_URL")
    or os.environ.get("CLEARDB_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or os.environ.get("POSTGRES_URL")
)
if _database_url:
    if _database_url.startswith(("mysql://", "mariadb://")):
        import pymysql

        pymysql.install_as_MySQLdb()
        _db = dj_database_url.parse(_database_url, conn_max_age=600)
        _db["ENGINE"] = "django.db.backends.mysql"
        # Managed MySQL providers terminate TLS; point MYSQL_SSL_CA at their
        # CA bundle (e.g. Aiven's ca.pem). Charset utf8mb4 for full Unicode.
        _db.setdefault("OPTIONS", {})
        _db["OPTIONS"]["charset"] = "utf8mb4"
        _ca = os.environ.get("MYSQL_SSL_CA")
        if _ca:
            _db["OPTIONS"]["ssl"] = {"ca": _ca}
        DATABASES = {"default": _db}
    else:
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

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

MEDIA_URL = "/media/"
# Vercel's filesystem is ephemeral. Configure an S3-compatible bucket for
# avatars/uploads in production; local development keeps using ./media.
MEDIA_ROOT = os.environ.get("MEDIA_ROOT", BASE_DIR / "media")

if os.environ.get("AWS_STORAGE_BUCKET_NAME"):
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
    }
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    AWS_STORAGE_BUCKET_NAME = os.environ["AWS_STORAGE_BUCKET_NAME"]
    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "") or None
    AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", "") or None
    AWS_QUERYSTRING_AUTH = os.environ.get("AWS_QUERYSTRING_AUTH", "False").lower() in ("1", "true", "yes")
    AWS_DEFAULT_ACL = None

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
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587") or 587)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() in ("1", "true", "yes")
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "False").lower() in ("1", "true", "yes")
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "10") or 10)
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
