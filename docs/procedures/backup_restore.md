# Backup & Restore — BKM

## Overview

Production database (`db.sqlite3`) is backed up nightly to **Google Drive** via `rclone`.
Last 30 daily backups are retained.

## Backup mechanism

1. Render cron job runs at 02:00 UTC daily
2. Creates a safe copy via `sqlite3 .backup` (consistent even under load)
3. Uploads to Google Drive folder `babook-backups/` with dated filename

```bash
# Backup command (runs on Render)
sqlite3 /var/data/db.sqlite3 ".backup /tmp/db_backup_$(date +%Y%m%d).sqlite3"
rclone copy /tmp/db_backup_$(date +%Y%m%d).sqlite3 gdrive:babook-backups/
```

## Restore procedure

### On Render (production)

1. Download the backup from Google Drive:
   ```bash
   rclone copy gdrive:babook-backups/db_backup_YYYYMMDD.sqlite3 /tmp/
   ```
2. Stop the web service (Render dashboard → Manual Deploy → Suspend)
3. Replace the database:
   ```bash
   cp /tmp/db_backup_YYYYMMDD.sqlite3 /var/data/db.sqlite3
   ```
4. Resume the web service

### Locally (development)

1. Download from Google Drive (browser or rclone)
2. Place in `data/db.sqlite3`
3. Run `python manage.py migrate` to ensure schema is current

## Retention policy

- Keep last 30 daily backups
- Older backups auto-deleted by rclone `--max-age 30d` flag

## Setup (ACT-3)

1. Install rclone on Render (build.sh)
2. Configure rclone with Google Drive OAuth token
3. Add cron job to Render (or use Render Cron Job service)
