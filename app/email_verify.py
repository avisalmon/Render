"""Email verification for the password-signup path (REQ-7.2.1, QA-1).

Google signups are trusted (verified by Google). Password signups get a signed
link they must click; until verified, a banner nudges them. Closes the
forgot-password hole (every account has a real, owned email).
"""
from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.urls import reverse

SALT = "babook.email.verify"
MAX_AGE = 60 * 60 * 24 * 7  # 7 days


def make_token(user):
    return signing.dumps({"uid": user.pk, "email": user.email}, salt=SALT)


def verify_token(token):
    """Return the user_id if the token is valid and still matches the email."""
    try:
        data = signing.loads(token, salt=SALT, max_age=MAX_AGE)
    except signing.BadSignature:
        return None
    return data


def send_verification_email(request, user):
    if not user.email:
        return False
    token = make_token(user)
    url = request.build_absolute_uri(reverse("verify_email") + f"?token={token}")
    name = (getattr(user, "profile", None) and user.profile.public_name) or user.username
    body = (
        f"שלום {name},\n\n"
        "תודה שנרשמת ל-babook! כדי להפעיל את החשבון ולוודא שהאימייל שלך נכון, "
        "לחצו על הקישור הבא:\n\n"
        f"{url}\n\n"
        "אם לא נרשמתם - אפשר להתעלם מהמייל הזה.\n\n"
        "צוות babook"
    )
    try:
        send_mail(
            "אימות האימייל שלך ב-babook",
            body,
            getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@babook.co.il"),
            [user.email],
            fail_silently=True,
        )
        return True
    except Exception:
        return False
