# Copilot Policy — babook-learn org

> Org-level Copilot Business policies configured in GitHub UI.
> Review and update these when onboarding new users.

## Policies (set in GitHub org settings)

| Policy | Setting | Rationale |
|---|---|---|
| Suggestions matching public code | **Block** | Avoid copyright issues in training context |
| Telemetry (code snippets to GitHub) | **Disabled** | Privacy for subscribers |
| Allowed editors | **VS Code, JetBrains, Neovim** | Standard dev tools for training |
| Copilot Chat | **Enabled** | Core training value |
| Copilot in CLI | **Enabled** | Useful for learners |

## How to update

1. Go to https://github.com/organizations/babook-learn/settings/copilot
2. Adjust policies under "Policies" tab
3. Update this document to match

## Seat assignment flow

1. User subscribes to Copilot tier on babook.co.il
2. System auto-invites GitHub username to `babook-learn` org
3. User accepts invite (email or github.com/orgs/babook-learn/invitation)
4. System assigns Copilot Business seat
5. User installs VS Code Copilot extension and signs in

## Revocation

- On subscription cancel: seat revoked immediately, org removal after 14 days
- On inactivity (60 days): seat reclaimed, user notified
- Admin can manually reclaim via /admin/copilot-dashboard/
