#!/usr/bin/env bash
# Render build script — set this as the Build Command on your Web Service.
set -euo pipefail

pip install --upgrade pip
pip install -r requirements.txt

# Whitenoise needs collected static files at build time.
python manage.py collectstatic --noinput

# Apply migrations at deploy time (safe on MySQL; single instance only).
python manage.py migrate --noinput

# Load the Indian demo dataset on first boot. Remove this line once you go
# live with real users, or guard it behind an env var as below.
if [ "${SEED_DEMO_ON_DEPLOY:-True}" = "True" ]; then
  python manage.py seed_demo
fi
