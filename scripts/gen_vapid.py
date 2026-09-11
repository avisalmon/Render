"""Generate a VAPID key pair for Web Push (REQ-11.6.9).

    python scripts/gen_vapid.py

Prints the two values to paste into Render's environment. **The private key is a
credential** — it is what lets anything push notifications to every subscribed
phone — so it belongs in an env var with `sync: false` and never in git, never in
a chat window, never in a screenshot.

Run this once. Regenerating invalidates every existing subscription, because a
browser's subscription is bound to the public key it was created with: everyone
would silently stop receiving notifications and nothing would say why.
"""
from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid01


def generate():
    vapid = Vapid01()
    vapid.generate_keys()
    private = base64.urlsafe_b64encode(
        vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
    ).decode().rstrip("=")
    public = base64.urlsafe_b64encode(
        vapid.public_key.public_bytes(serialization.Encoding.X962,
                                      serialization.PublicFormat.UncompressedPoint)
    ).decode().rstrip("=")
    return public, private


def main():
    public, private = generate()
    print("Add these to Render -> Environment (both sync: false):")
    print()
    print(f"VAPID_PUBLIC_KEY={public}")
    print(f"VAPID_PRIVATE_KEY={private}")
    print()
    print("VAPID_CONTACT_EMAIL=mailto:you@example.com   (optional; defaults to the owner)")
    print()
    print("Keep the private key secret, and do not regenerate it later:")
    print("every existing subscription is bound to the PUBLIC key it was made")
    print("with, so a new pair silently stops every phone already signed up.")


if __name__ == "__main__":
    main()
