"""One-time Google Drive setup: get a refresh token for YOUR OWN account.

This project's dedicated Drive storage (app/drive.py, 2026-09-15) — its own
Google Cloud project and OAuth client, separate from the home security app's.
Deliberately not shared with that one: it runs on a different machine on a
different deploy schedule, and reusing its grant would have coupled two
systems that have nothing to do with each other.

Run this once, locally, on any machine with a browser:

    .\\env\\Scripts\\python.exe manage.py drive_setup
    .\\env\\Scripts\\python.exe manage.py drive_setup --check   (verify after)

It opens your browser, you approve, and it prints (or writes to your local
`.env`) the three values Render needs.

WHY YOUR OWN ACCOUNT AND NOT A SERVICE ACCOUNT
-----------------------------------------------
Service accounts have **no storage quota** in consumer Google Drive — files
uploaded by one have nowhere to live. The files must land in your own Drive,
which means an OAuth refresh token for your account.

THE SEVEN-DAY TRAP — READ THIS
-------------------------------
If the OAuth consent screen is left in **"Testing"** publishing status,
Google **expires refresh tokens after 7 days**. Everything works for a week
and then uploads stop, silently, while the rest of the app looks perfectly
healthy. Set it to **"Published" / "In production"** before relying on this
for anything with a deadline. No verification review is needed for a
personal project using your own account.

WHY A LOOPBACK REDIRECT
------------------------
This uses `http://127.0.0.1:<port>`, not the old copy-paste "out of band"
flow — Google disabled OOB in 2022. A **Desktop app** client type permits
loopback redirects automatically, with nothing to register.

WHAT TO DO FIRST (about five minutes, once)
---------------------------------------------
1. https://console.cloud.google.com/ → create a project (any name — e.g.
   "babook storage").
2. APIs & Services → Library → enable **Google Drive API**.
3. APIs & Services → OAuth consent screen:
      - User type: External
      - Fill the required name/email fields
      - **PUBLISH THE APP** (see the trap above)
4. APIs & Services → Credentials → Create credentials →
   **OAuth client ID** → Application type: **Desktop app**.

   Do NOT reuse the "Web application" client babook's own Google login uses
   (django-allauth) — that one is a different type, needs its redirect URIs
   registered by hand, and mixing an unattended uploader into the site's
   login client makes both harder to reason about and to revoke.

5. Copy the Client ID and Client secret, then run this command.

The scope requested is **`drive.file`** — the narrowest that works. It
grants access only to files this application itself creates, so it cannot
read anything else already in your Drive. That is what an unattended
uploader should have.

AFTER THIS: one more manual step
----------------------------------
This command gets you `DRIVE_CLIENT_ID`, `DRIVE_CLIENT_SECRET`,
`DRIVE_REFRESH_TOKEN`. You still need `DRIVE_FOLDER_ID` — create (or pick)
one folder in Drive to be the root everything lives under, open it, and
copy the id out of its URL (`drive.google.com/drive/folders/<THIS PART>`).
Apps create their own named subfolder inside it on first use; nothing here
does that for you ahead of time.

Then put all four in Render (babook service → Environment) — this project
does not read them from a committed .env in production, only locally.
"""

from __future__ import annotations

import http.server
import json
import os
import socket
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

from django.core.management.base import BaseCommand

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/drive.file"


class _CatchCode(http.server.BaseHTTPRequestHandler):
    """Receives Google's redirect and keeps the `code` query parameter."""

    code = None
    error = None

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        _CatchCode.code = (params.get("code") or [None])[0]
        _CatchCode.error = (params.get("error") or [None])[0]
        body = ("<html><body style='font-family:sans-serif;padding:3rem'>"
                "<h2>%s</h2><p>You can close this tab and return to the "
                "terminal.</p></body></html>" %
                ("Authorised — thank you." if _CatchCode.code
                 else f"Failed: {_CatchCode.error}")).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass  # keep the console clean


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _write_env(lines):
    """Append the credentials to the repo-root `.env`, replacing any earlier
    DRIVE_* block. Local dev only — Render never reads this file."""
    env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))), ".env")
    existing = ""
    if os.path.isfile(env):
        with open(env, encoding="utf-8") as fh:
            existing = fh.read()
    keep = [ln for ln in existing.splitlines()
            if not ln.startswith(("DRIVE_CLIENT_ID=", "DRIVE_CLIENT_SECRET=",
                                   "DRIVE_REFRESH_TOKEN="))]
    body = "\n".join(keep).rstrip() + "\n\n" + "\n".join(lines) + "\n"
    with open(env, "w", encoding="utf-8") as fh:
        fh.write(body)
    return env


class Command(BaseCommand):
    help = "One-time: get a Drive OAuth refresh token for this project's shared storage."

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true", help="verify the stored credentials work")
        parser.add_argument("--write-env", action="store_true",
                             help="write to the local .env instead of printing the refresh token")
        parser.add_argument("--client-id", default="")
        parser.add_argument("--client-secret", default="")

    def handle(self, *args, **options):
        if options["check"]:
            raise SystemExit(self._check())
        raise SystemExit(self._main(options))

    def _main(self, options) -> int:
        client_id = options["client_id"]
        client_secret = options["client_secret"]
        if not (client_id and client_secret):
            self.stdout.write(__doc__)
            self.stdout.write("=" * 72)
            client_id = input("Client ID:     ").strip()
            client_secret = input("Client secret: ").strip()
        if not (client_id and client_secret):
            self.stdout.write("Both are required. Nothing written.")
            return 1

        port = _free_port()
        redirect = f"http://127.0.0.1:{port}"
        params = {
            "client_id": client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": SCOPE,
            # Both required to be GIVEN a refresh token at all: without
            # access_type=offline Google returns only an access token, and
            # without prompt=consent it withholds the refresh token on a
            # repeat approval.
            "access_type": "offline",
            "prompt": "consent",
        }
        url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

        server = http.server.HTTPServer(("127.0.0.1", port), _CatchCode)
        threading.Thread(target=server.handle_request, daemon=True).start()

        self.stdout.write(f"\nOpening your browser. If it does not open, paste this:\n\n{url}\n")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        self.stdout.write(f"Waiting for the redirect on {redirect} ...")
        for _ in range(300):
            if _CatchCode.code or _CatchCode.error:
                break
            threading.Event().wait(1)
        server.server_close()

        if _CatchCode.error or not _CatchCode.code:
            self.stdout.write(f"\nNo authorisation code ({_CatchCode.error or 'timed out'}). Nothing written.")
            return 1

        body = urllib.parse.urlencode({
            "code": _CatchCode.code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect,
            "grant_type": "authorization_code",
        }).encode()
        req = urllib.request.Request(
            TOKEN_URL, data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                payload = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            detail = getattr(e, "read", lambda: b"")()
            self.stdout.write(f"\nToken exchange failed: {e}\n{detail.decode('utf-8', 'replace')}")
            return 1

        refresh = payload.get("refresh_token")
        if not refresh:
            self.stdout.write(
                "\nGoogle returned no refresh token. That happens on a repeat approval "
                "when prompt=consent is dropped, or when access_type is not 'offline'. "
                "Revoke this app at https://myaccount.google.com/permissions and run it "
                "again."
            )
            return 1

        lines = [f"DRIVE_CLIENT_ID={client_id}",
                 f"DRIVE_CLIENT_SECRET={client_secret}",
                 f"DRIVE_REFRESH_TOKEN={refresh}"]
        self.stdout.write("\n" + "=" * 72)
        if options["write_env"]:
            # Preferred: a refresh token printed to a console is a secret
            # sitting in scrollback and in any transcript of the session.
            self.stdout.write(f"written to {_write_env(lines)} (git-ignored)")
        else:
            self.stdout.write("Add these to Render's environment (and your local .env if you want "
                               "to test locally):\n")
            self.stdout.write("\n".join(lines))
        self.stdout.write(
            "\nStill needed: DRIVE_FOLDER_ID — a Drive folder id you create or pick "
            "yourself. See the top of this file for how."
        )
        self.stdout.write("\nThen verify:\n    .\\env\\Scripts\\python.exe manage.py drive_setup --check")
        return 0

    def _check(self) -> int:
        """Prove the stored credentials actually work, end to end."""
        from app import drive

        cid = os.environ.get("DRIVE_CLIENT_ID", "")
        secret = os.environ.get("DRIVE_CLIENT_SECRET", "")
        refresh = os.environ.get("DRIVE_REFRESH_TOKEN", "")
        folder = os.environ.get("DRIVE_FOLDER_ID", "")
        if not (cid and secret and refresh):
            self.stdout.write(
                "DRIVE_CLIENT_ID / DRIVE_CLIENT_SECRET / DRIVE_REFRESH_TOKEN are not all "
                "set — run this without --check first."
            )
            return 1
        if not folder:
            self.stdout.write(
                "Token credentials look present, but DRIVE_FOLDER_ID is not set yet — "
                "see the top of this file for how to get one."
            )
            return 1

        client = drive.DriveClient(cid, secret, refresh, folder, subfolder_name="")
        try:
            client.access_token()
            self.stdout.write("token refresh : OK")
        except drive.DriveError as e:
            self.stdout.write(f"FAILED: {e}")
            return 1
        name = client.root_folder_name()
        if not name:
            self.stdout.write(
                f"FAILED: DRIVE_FOLDER_ID ({folder}) did not resolve to a folder your "
                "account can see. Check the id and that it's shared with this account."
            )
            return 1
        quoted_name = '"' + name + '"'
        self.stdout.write(f"root folder   : {quoted_name} ({folder})")
        self.stdout.write("\nDrive is ready.")
        return 0
