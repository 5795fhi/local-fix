#!/usr/bin/env bash
set -euo pipefail

# Vercel's Django integration discovers localfix/wsgi.py automatically.
# Keep build-time work limited to immutable static assets; run migrations
# against the production database as an explicit release step.
python manage.py collectstatic --noinput
