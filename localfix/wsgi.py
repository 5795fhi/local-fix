import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "localfix.settings")

application = get_wsgi_application()

# Some serverless platforms (including Vercel's Python runtime) resolve the
# ASGI/WSGI callable as `app`. Expose an alias so the handler never fails with
# "unable to import 'app'" regardless of which name it looks up.
app = application
