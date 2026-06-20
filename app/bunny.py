"""
Bunny Stream utilities - signed URL generation for token-authenticated playback.
"""
import hashlib
import time

from django.conf import settings


def generate_signed_url(bunny_video_id, expiry_seconds=86400):
    """Generate a signed Bunny Stream playback URL.

    Uses Bunny's token authentication: SHA256(token_key + video_id + expiry).
    The signed URL expires after expiry_seconds (default 24h).
    """
    hostname = settings.BUNNY_STREAM_CDN_HOSTNAME
    token_key = settings.BUNNY_STREAM_TOKEN_KEY

    expires = int(time.time()) + expiry_seconds
    # Bunny token: SHA256 of token_key + video_id + expires
    token_string = f"{token_key}{bunny_video_id}{expires}"
    token = hashlib.sha256(token_string.encode()).hexdigest()

    url = (
        f"https://{hostname}/{bunny_video_id}/play.mp4"
        f"?token={token}&expires={expires}"
    )
    return url


def get_embed_url(bunny_video_id):
    """Return the Bunny Stream iframe embed URL, or None if not configured."""
    library_id = settings.BUNNY_STREAM_LIBRARY_ID
    if not library_id:
        return None
    return f"https://iframe.mediadelivery.net/embed/{library_id}/{bunny_video_id}"
