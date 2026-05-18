#!/usr/bin/env bash
set -o errexit

python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --no-input

# Install rclone for database backups to Google Drive
if ! command -v rclone &> /dev/null; then
    curl -s https://rclone.org/install.sh | bash
fi
