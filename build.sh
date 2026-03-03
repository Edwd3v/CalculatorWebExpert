#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput

if [[ -n "${ADMIN_USERNAME:-}" && -n "${ADMIN_PASSWORD:-}" ]]; then
python manage.py shell <<'PY'
import os
from django.contrib.auth import get_user_model

username = os.environ["ADMIN_USERNAME"].strip()
password = os.environ["ADMIN_PASSWORD"]
email = os.environ.get("ADMIN_EMAIL", "").strip()

if not username:
    print("ADMIN_USERNAME is empty. Skipping admin bootstrap.")
    raise SystemExit(0)

User = get_user_model()
user, created = User.objects.get_or_create(username=username, defaults={"email": email})

if email and user.email != email:
    user.email = email

user.is_staff = True
user.is_superuser = True
user.is_active = True
user.set_password(password)
user.save()

if created:
    print(f"Created superuser '{username}'.")
else:
    print(f"Updated superuser '{username}'.")
PY
else
  echo "ADMIN_USERNAME/ADMIN_PASSWORD not set. Skipping admin bootstrap."
fi
