# Copilot Seat Provisioning — GitHub API

## Architecture

```
User upgrades to Master tier → app/copilot.py → GitHub API → org invite + Copilot seat
User downgrades/expires       → app/copilot.py → GitHub API → revoke seat + remove from org
```

## Provider

- **Service:** GitHub REST API (org memberships + Copilot billing)
- **Org:** `babook-learn`
- **Package:** None (direct `requests` calls, currently stubbed)

## Current status: STUBBED

All GitHub API calls are stubs until `GITHUB_PAT` is configured with a real
token. No HTTP requests are made. This is safe for testing and development.

## Settings wiring

```python
GITHUB_ORG = os.environ.get("GITHUB_ORG", "babook-learn")
GITHUB_PAT = os.environ.get("GITHUB_PAT", "")
COPILOT_MAX_SEATS = int(os.environ.get("COPILOT_MAX_SEATS", "10"))
COPILOT_GRACE_PERIOD_DAYS = int(os.environ.get("COPILOT_GRACE_PERIOD_DAYS", "14"))
COPILOT_INACTIVITY_WARN_DAYS = int(os.environ.get("COPILOT_INACTIVITY_WARN_DAYS", "30"))
COPILOT_INACTIVITY_RECLAIM_DAYS = int(os.environ.get("COPILOT_INACTIVITY_RECLAIM_DAYS", "60"))
COPILOT_SEAT_COST_USD = float(os.environ.get("COPILOT_SEAT_COST_USD", "19.0"))
```

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GITHUB_ORG` | `babook-learn` | Target GitHub organization |
| `GITHUB_PAT` | _(empty)_ | Personal Access Token; empty = stub mode |
| `COPILOT_MAX_SEATS` | `10` | Max concurrent Copilot seats |
| `COPILOT_GRACE_PERIOD_DAYS` | `14` | Grace period after downgrade before seat revoke |
| `COPILOT_INACTIVITY_WARN_DAYS` | `30` | Days idle before warning |
| `COPILOT_INACTIVITY_RECLAIM_DAYS` | `60` | Days idle before seat reclaim |
| `COPILOT_SEAT_COST_USD` | `19.0` | Monthly cost per seat (for tracking) |

## API endpoints (when real)

| Action | GitHub API |
|--------|-----------|
| Invite to org | `PUT /orgs/{org}/memberships/{username}` |
| Assign seat | `POST /orgs/{org}/copilot/billing/selected_users` |
| Revoke seat | `DELETE /orgs/{org}/copilot/billing/selected_users` |
| Remove member | `DELETE /orgs/{org}/members/{username}` |

## Django models

- `CopilotSeat` — tracks assigned seats (user, github_username, status, timestamps)
- `SeatEvent` — audit log of all provisioning actions

## Access control

Only users with **Master** tier entitlement are eligible for Copilot seats
(`Entitlement.has_copilot_access` property).

## Key files

| File | Role |
|------|------|
| `app/copilot.py` | All GitHub API logic (stubbed) |
| `app/models.py` | `CopilotSeat`, `SeatEvent` models |
| `app/views.py` | Copilot dashboard view |
| `templates/app/copilot_dashboard.html` | Seat management UI |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "STUB" in logs | Set `GITHUB_PAT` to activate real API calls |
| Max seats reached | Increase `COPILOT_MAX_SEATS` or reclaim inactive seats |
| Invite not received | Check GitHub email settings for the user |
| PAT expired | Generate new Fine-Grained PAT with org:write + copilot scopes |
