"""Getting a person's profile, without a signal and without a backfill.

Deliberately on demand rather than via a `post_save` signal on `User`:
accounts on this site predate SensorLab by years, so a signal would only
ever cover people who sign up *after* it was installed and would need a
backfill migration for everyone else. `get_or_create` at the point of use
covers both, and cannot be installed in the wrong order.
"""

from .models import SensorLabProfile


def profile_for(user):
    """This person's SensorLab profile, created on first arrival."""
    profile, _created = SensorLabProfile.objects.get_or_create(user=user)
    return profile
