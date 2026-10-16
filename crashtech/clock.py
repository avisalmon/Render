"""Time, said the way a person reads it at 3am.

The review found that during a 24-hour event no screen anywhere said how
long was left, which for a participant is the single most important fact
of the night. This is the wording; the event home carries it, and a few
lines of script keep it ticking where scripts run. Without a script the
server's sentence is still true to the minute it was rendered.
"""

from django.utils import timezone


def remaining(target, now=None):
    """`"13h 42m"`, `"3 days"`, `"40 minutes"`, or `""` once it has passed."""
    now = now or timezone.now()
    seconds = int((target - now).total_seconds())
    if seconds <= 0:
        return ""
    minutes = seconds // 60
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days >= 2:
        return f"{days} days"
    if days == 1:
        return f"1 day {hours}h"
    if hours:
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    return "less than a minute"


def ago(moment, now=None):
    """`"4 minutes ago"`, for "the latest submission" on an admin's home."""
    if moment is None:
        return ""
    now = now or timezone.now()
    seconds = max(0, int((now - moment).total_seconds()))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    return f"{hours // 24} days ago"


def ordinal(place):
    """1st, 2nd, 3rd, 4th, 11th, 12th, 13th, 21st."""
    if 10 <= place % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(place % 10, "th")
    return f"{place}{suffix}"
