# Roles & Permissions

## Overview

babook.co.il uses a simple role-based access model via the `UserProfile` model.

## Roles

| Role | Access | How assigned |
|---|---|---|
| `admin` | Full Django admin, all features, user management | Manual (superuser) |
| `staff` | Django admin (limited), content management | Manual via admin |
| `member` | Paid content, video playback, AI chat | On active subscription |
| `guest` | Free preview videos, public pages only | Default for new signups |

## Implementation

- `UserProfile.role` field (CharField with choices)
- Auto-created via `post_save` signal on `User` creation
- Default role: `guest`

## Checking permissions in views

```python
from django.contrib.auth.decorators import login_required

@login_required
def paid_view(request):
    profile = request.user.userprofile
    if profile.role not in ('member', 'staff', 'admin'):
        return HttpResponseForbidden()
    ...
```

## Promoting a user

Via Django admin:
1. Go to `/admin/app/userprofile/`
2. Find the user
3. Change `role` field
4. Save

## Superuser creation (Render)

```bash
# SSH into Render or use Render Shell
python manage.py createsuperuser
```

Or locally:
```bash
python manage.py createsuperuser --username admin --email avi@babook.co.il
```
