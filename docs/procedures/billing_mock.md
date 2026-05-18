# Billing — Mock Mode (Free/Base/Master Tiers)

## Architecture

```
User → /pricing/ → sees 3 cards → clicks "Choose" → POST /pricing/choose/ → Entitlement saved
```

## Current status: MOCK MODE

All tiers are free (₪0). Users select any tier instantly. Real Stripe
integration is deferred to a future sprint.

## Tiers

| Tier | Price (mock) | Video access | Copilot access |
|------|-------------|--------------|----------------|
| Free | ₪0 | No (free previews only) | No |
| Base | ₪0 (real: ₪49/mo) | Yes (all videos) | No |
| Master | ₪0 (real: ₪149/mo) | Yes (all videos) | Yes |

## Entitlement model

```python
class Entitlement(models.Model):
    TIER_CHOICES = [("free", "Free"), ("base", "Base"), ("master", "Master")]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default="free")
    updated_at = models.DateTimeField(auto_now=True)
```

Properties:
- `has_video_access` → `True` if tier is `base` or `master`
- `has_copilot_access` → `True` if tier is `master`

## Views

| URL | View | Method | Purpose |
|-----|------|--------|---------|
| `/pricing/` | `pricing()` | GET | Show tier cards with current plan badge |
| `/pricing/choose/` | `choose_tier()` | POST | Set user's tier (login required) |

## Access gating

The `lesson()` view checks entitlement before serving paid videos:

1. Anonymous user on paid video → redirect to login
2. Logged-in user with no entitlement or Free tier → 403
3. Base or Master tier → serve video

Invalid tier values in POST are silently defaulted to `"free"`.

## Key files

| File | Role |
|------|------|
| `app/models.py` | `Entitlement` model |
| `app/views.py` | `pricing()`, `choose_tier()`, gating in `lesson()` |
| `templates/app/pricing.html` | 3-card pricing page |
| `app/urls.py` | `/pricing/` and `/pricing/choose/` routes |
| `tests/test_spr_1_5.py` | 17 tests covering model, views, gating |

## Future: real billing (Stripe)

When real billing is implemented:
- `choose_tier()` will redirect to Stripe Checkout instead of instant save
- Stripe webhook will create/update Entitlement on successful payment
- Customer Portal for subscription management
- Green Invoice integration for Israeli VAT compliance
