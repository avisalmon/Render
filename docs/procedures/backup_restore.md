# Backup & Restore — BKM

## Overview

Production database (`db.sqlite3`) is backed up nightly to **Google Drive** via `rclone`.
Last 30 daily backups are retained. Backups are triggered by a Render Cron Job at 03:00 UTC.

## Architecture

```
Render cron (03:00 UTC) → python manage.py backup_db
  → sqlite3 WAL checkpoint + .backup API → consistent snapshot
  → rclone upload → gdrive:babook-backups/db_backup_YYYYMMDD_HHMMSS.sqlite3
  → rclone delete --min-age 30d → old backups removed
```

## Django management command

```bash
# Full backup (production)
python manage.py backup_db

# Dry run (test without uploading)
python manage.py backup_db --dry-run

# Custom retention (e.g. keep 7 days)
python manage.py backup_db --retention-days 7
```

The command:
1. Runs `PRAGMA wal_checkpoint(TRUNCATE)` for WAL consistency
2. Uses Python's `sqlite3.Connection.backup()` API (safe under concurrent reads)
3. Uploads timestamped file to `gdrive:babook-backups/`
4. Deletes remote files older than 30 days

## Environment variables

| Variable | Where | Purpose |
|----------|-------|---------|
| `RCLONE_CONF` | Render env (cron job) | Base64-encoded rclone.conf with Google Drive token |

## Initial setup (one-time, done by Avi)

### 1. Configure rclone locally

```powershell
# Install rclone (Windows)
winget install Rclone.Rclone

# Interactive config — creates Google Drive remote named "gdrive"
rclone config
# Choose: New remote → name: gdrive → Storage: Google Drive → follow OAuth
```

### 2. Encode config as base64

```powershell
# Find your rclone config file
rclone config file
# Typically: C:\Users\<user>\AppData\Roaming\rclone\rclone.conf

# Base64 encode it
$conf = [Convert]::ToBase64String([IO.File]::ReadAllBytes("$env:APPDATA\rclone\rclone.conf"))
$conf | Set-Clipboard
# Paste into Render env var RCLONE_CONF
```

### 3. Set env var on Render

Go to Render Dashboard → nightly-backup cron job → Environment → add `RCLONE_CONF` with the base64 string.

### 4. Test

```bash
# On Render shell (or locally with RCLONE_CONF set)
python manage.py backup_db --dry-run
python manage.py backup_db
```

## Restore procedure

### On Render (production)

1. Open Render Shell (Dashboard → mysite → Shell)
2. List available backups:
   ```bash
   rclone ls --config <(echo $RCLONE_CONF | base64 -d) gdrive:babook-backups/
   ```
3. Download desired backup:
   ```bash
   rclone copy --config <(echo $RCLONE_CONF | base64 -d) \
     gdrive:babook-backups/db_backup_YYYYMMDD_HHMMSS.sqlite3 /tmp/
   ```
4. Stop the web service (Render Dashboard → Suspend Service)
5. Replace the database:
   ```bash
   cp /tmp/db_backup_YYYYMMDD_HHMMSS.sqlite3 /var/data/db.sqlite3
   ```
6. Resume the web service
7. Run migrations if schema changed: `python manage.py migrate`

### Locally (development)

1. Download from Google Drive (browser or rclone):
   ```powershell
   rclone copy gdrive:babook-backups/db_backup_YYYYMMDD_HHMMSS.sqlite3 .\data\
   Rename-Item .\data\db_backup_YYYYMMDD_HHMMSS.sqlite3 db.sqlite3
   ```
2. Run `python manage.py migrate` to ensure schema is current

## Render cron job (render.yaml)

```yaml
- type: cron
  name: nightly-backup
  runtime: python
  plan: starter
  schedule: "0 3 * * *"
  buildCommand: ./build.sh
  startCommand: python manage.py backup_db
```

## Retention policy

- Last 30 daily backups retained on Google Drive
- Older files auto-deleted by the management command after each upload
- Google Drive also has its own 30-day trash (extra safety net)
- Render persistent disk has daily snapshots (independent of this)

## Key files

| File | Role |
|------|------|
| `app/management/commands/backup_db.py` | Management command |
| `build.sh` | Installs rclone during build |
| `render.yaml` | Defines the cron job schedule |
| `docs/procedures/backup_restore.md` | This document |
