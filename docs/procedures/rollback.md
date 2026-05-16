# Rollback — BKM

## Overview

Render auto-deploys from `main`. To rollback a bad deploy:

## Option 1: Revert commit (preferred)

```bash
# Locally
git revert HEAD
git push origin main
```
Render auto-deploys the revert. Fastest, leaves audit trail.

## Option 2: Manual deploy of previous commit

1. Go to Render Dashboard → babook service → Deploys
2. Find the last known-good deploy
3. Click "Redeploy" on that commit

## Option 3: Force push (emergency only)

```bash
git reset --hard <good-commit-hash>
git push --force origin main
```
**Warning:** Destructive. Only use if revert is not feasible.

## Database rollback

If the bad deploy corrupted data:

1. Identify the pre-corruption backup (see `backup_restore.md`)
2. Suspend the service
3. Restore from backup
4. Resume service
5. Run `python manage.py migrate` if schema changed

## Environment variable rollback

1. Render Dashboard → Environment
2. Change the variable back to previous value
3. Click "Save Changes" — triggers redeploy automatically

## Post-rollback checklist

- [ ] Verify `/healthz` returns 200
- [ ] Verify homepage loads
- [ ] Verify login works (Google OAuth)
- [ ] Check Render logs for errors
- [ ] Notify team if user-facing impact
