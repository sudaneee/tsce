#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def settings_module_from_env_file():
    """Servers set DJANGO_SETTINGS_MODULE=config.settings.prod in backend/.env, so plain
    `python manage.py …` uses production settings there; development needs no .env."""
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "DJANGO_SETTINGS_MODULE" and value.strip():
                return value.split("#")[0].strip()
    return None


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module_from_env_file() or "config.settings.dev")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
