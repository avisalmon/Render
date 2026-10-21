"""The tracks the course opens with (REQ-C.20).

How a track is added "through the chat": a line is added here and deployed,
and `seed_cohort` creates it. One-time per track (methodology: seeding is a
one-time import): an existing track is never changed by the seed, and an owner
is set only on a track that has none, so nothing an owner or Avi changed on
the site is ever overwritten.
"""

TRACKS = [
    # slug, name, position, is_example, owner email (or "")
    ("computer-science", "מדעי המחשב", 10, False, ""),
    ("electronics", "אלקטרוניקה", 20, False, ""),
    ("physics", "פיזיקה", 30, False, ""),
    ("mechatronics", "מכטרוניקה", 40, False, ""),
    ("design", "עיצוב", 50, False, ""),
    ("data-science", "מדעי הנתונים", 60, False, ""),
    ("imaginary-electronics", "מגמה דמיונית: אלקטרוניקה", 5, True, "avi.salmon@gmail.com"),
]


def seed(stdout=None):
    from django.contrib.auth import get_user_model
    from django.utils import timezone

    from .access import display_name_for
    from .models import Member, Track

    User = get_user_model()
    made = 0
    for slug, name, position, example, owner_email in TRACKS:
        track = Track.objects.filter(slug=slug).first()
        if track is None:
            track = Track.objects.create(slug=slug, name=name, position=position, is_example=example)
            made += 1
        if owner_email and track.owner_id is None:
            user = User.objects.filter(email__iexact=owner_email).order_by("id").first()
            if user is not None:
                member, _ = Member.objects.get_or_create(user=user, defaults={
                    "display_name": display_name_for(user), "status": Member.APPROVED,
                    "is_admin": user.is_superuser, "decided_at": timezone.now(),
                })
                track.owner = member
                track.save(update_fields=["owner"])
    if stdout:
        stdout.write(f"cohort: {made} new tracks, {Track.objects.count()} in all")
    return made
