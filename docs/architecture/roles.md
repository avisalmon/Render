# Roles & Permissions

## Overview

babook.co.il uses a simple role-based access model via the `UserProfile` model.

> **Canonical access matrix:** the authoritative logged-out vs logged-in
> capability table lives in [main_spec.md §5.1](../main_spec.md) (REQ-5.1.1).
> This file summarizes roles; on any conflict, the §5.1 matrix wins.

## Roles

| Role | Access | How assigned |
|---|---|---|
| `admin` | Full Django admin, all features, user management | Manual (superuser) |
| `staff` | Django admin (limited), content management, all lessons unlocked | Manual via admin |
| `member` | Enrolled/entitled lessons, quizzes, reflections, certificates, AI chat, profile | Registered user |
| `guest` (logged out) | Browse full catalog + course pages, watch each course's free first lesson, contact form, newsletter | Anonymous visitor |

## Guest vs member (REQ-5.1.1 summary)

A **logged-out visitor** explores everything and tastes one free lesson per
course; a gated action (non-preview lesson, enroll, reflect, chat, profile)
routes to the context-aware registration wall at `/join/` - never a bare
403/login page (REQ-5.1.2). A **member** gets the personalized homepage,
progress, quizzes, reflections, certificates, and AI chat. Authors
additionally get `/studio/` (REQ-4.1.1).

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
