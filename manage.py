#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "localfix.settings")
    # Deployment providers may define this variable with an empty value.
    # Normalize it before Django imports settings.py, where it is parsed as
    # an integer during commands such as `collectstatic`.
    if not os.environ.get("DB_CONN_MAX_AGE", "").strip():
        os.environ["DB_CONN_MAX_AGE"] = "0"
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
