"""Google Drive as this Render project's shared storage (2026-09-15).

One dedicated Google Cloud project and OAuth client, used by every app on
this site that needs to hold files bigger than the database wants — trip
photos today, matazim submissions or memz uploads later. Not the home
security app's Drive: that one is a separate OAuth grant on a separate
machine, and reusing it would have coupled two systems that deploy on
completely different schedules. This is its own thing, set up once with
`app/management/commands/drive_setup.py`.

**Hand-written, not `google-api-python-client`.** Upload, download, delete
and a token refresh do not justify that dependency tree. The shape here is
close to `seccore/drive.py` in the separate Security repo (the home app's own
Drive client) because the problem is the same, but the two are not shared
code and were never meant to be — different project, different OAuth client,
different failure domain.

**One root folder (`DRIVE_FOLDER_ID`), one subfolder per app.** ustrip's
photos live in `<root>/ustrip/`; a future app gets its own named subfolder
the same way. An app never sees another app's subfolder id unless it goes
looking for it, and nothing here hands one out — `from_env(subfolder=...)`
takes the caller's own app name and nothing else.

Same two safety notes as the home app's version, because they are properties
of Drive and OAuth, not of who is asking:

- **A service account cannot be used here.** Service accounts have no
  storage quota in consumer Drive; files must land in the owner's own
  account, which means an OAuth refresh token for that account.
- **The seven-day trap.** A Google Cloud project left in "Testing"
  publishing status has its refresh tokens expire after seven days —
  uploads stop silently while everything else looks healthy. Publish the
  OAuth consent screen before relying on this for anything that matters on
  a deadline.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass

log = logging.getLogger("app.drive")

TOKEN_URL = "https://oauth2.googleapis.com/token"
FILES_URL = "https://www.googleapis.com/drive/v3/files"
UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
FOLDER_MIME = "application/vnd.google-apps.folder"
HTTP_TIMEOUT = 60


class DriveError(RuntimeError):
    pass


def folder_id_from(value: str) -> str:
    """Accept either a bare folder id or a Drive sharing URL."""
    text = str(value or "").strip()
    if "/folders/" in text:
        text = text.split("/folders/", 1)[1]
    return text.split("?")[0].split("/")[0].strip()


@dataclass
class DriveFile:
    file_id: str
    url: str


def _default_transport(method, url, headers=None, data=None, files=None, timeout=None):
    import requests

    r = requests.request(method, url, headers=headers, data=data, files=files,
                          timeout=timeout or HTTP_TIMEOUT)
    return r.status_code, r.content


class DriveClient:
    """Upload, serve and delete inside one app's subfolder of the shared
    Drive folder."""

    def __init__(self, client_id, client_secret, refresh_token, parent_folder_id,
                 subfolder_name: str, transport=None, timeout: int = HTTP_TIMEOUT):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.parent_folder_id = folder_id_from(parent_folder_id)
        self.subfolder_name = subfolder_name
        self._send = transport or _default_transport
        self.timeout = timeout
        self._token = ""
        self._token_expires = 0.0
        self._subfolder_id = ""

    # -- auth --------------------------------------------------------------- #
    def access_token(self, force: bool = False) -> str:
        """A valid access token, refreshed at most once an hour."""
        if not force and self._token and time.time() < self._token_expires:
            return self._token
        status, raw = self._send(
            "POST", TOKEN_URL,
            data={"client_id": self.client_id, "client_secret": self.client_secret,
                  "refresh_token": self.refresh_token, "grant_type": "refresh_token"},
            timeout=self.timeout)
        body = _json(raw)
        if status != 200:
            if body.get("error") == "invalid_grant":
                raise DriveError(
                    "Google rejected the refresh token (invalid_grant). The usual "
                    "cause is a Cloud project left in 'Testing' publishing status, "
                    "which expires refresh tokens after 7 days -- set it to "
                    "'Published' in the Google Cloud console. It also happens if "
                    "access was revoked at https://myaccount.google.com/permissions.")
            raise DriveError(f"token refresh failed ({status}): {body}")
        self._token = body.get("access_token", "")
        self._token_expires = time.time() + int(body.get("expires_in", 3600)) - 60
        return self._token

    def _auth(self):
        return {"Authorization": f"Bearer {self.access_token()}"}

    def _call(self, method, url, retry_auth=True, **kw):
        status, raw = self._send(method, url, headers=self._auth(), timeout=self.timeout, **kw)
        if status == 401 and retry_auth:
            self.access_token(force=True)
            status, raw = self._send(method, url, headers=self._auth(), timeout=self.timeout, **kw)
        return status, raw

    # -- folder --------------------------------------------------------------- #
    def create_folder(self, name: str, parent: str = "") -> str:
        """Make a folder and return its id. `parent` empty means Drive's own
        top level ("My Drive").

        The one primitive `DRIVE_FOLDER_ID` setup actually needs: the
        `drive.file` scope (deliberately the narrowest one that works, see
        the module docstring) only ever lets this client see files *it
        created itself*. A folder made by hand in the Drive web UI, even by
        the account's own owner, is invisible to it — found the hard way,
        setting this up for real, as "did not resolve to a folder your
        account can see" from a folder that very obviously existed. The root
        folder has to come from here, not from clicking around Drive."""
        meta = {"name": name, "mimeType": FOLDER_MIME}
        if parent:
            meta["parents"] = [parent]
        status, raw = self._call("POST", FILES_URL, data=json.dumps(meta))
        body = _json(raw)
        if status not in (200, 201) or not body.get("id"):
            raise DriveError(f"could not create folder {name!r}: ({status}) {body}")
        return body["id"]

    def subfolder_id(self) -> str:
        """This app's own folder inside the shared root, found once and
        remembered for the process, made on first use rather than assumed to
        exist."""
        if self._subfolder_id:
            return self._subfolder_id
        parent = self.parent_folder_id
        if not parent:
            return ""
        query = (f"name='{self.subfolder_name}' and mimeType='{FOLDER_MIME}' "
                 f"and '{parent}' in parents and trashed=false")
        _status, raw = self._call("GET", f"{FILES_URL}?q={query}&fields=files(id)")
        found = _json(raw).get("files") or []
        if found:
            self._subfolder_id = found[0].get("id", "")
            return self._subfolder_id
        _status, raw = self._call(
            "POST", FILES_URL,
            data=json.dumps({"name": self.subfolder_name, "mimeType": FOLDER_MIME,
                              "parents": [parent]}))
        self._subfolder_id = _json(raw).get("id", "")
        return self._subfolder_id

    def root_folder_name(self) -> str:
        """The name of the configured root folder, or "" if the id is wrong
        or unreachable. Read-only -- unlike `subfolder_id()`, never creates
        anything, so it is safe to call just to check a setup is working."""
        if not self.parent_folder_id:
            return ""
        status, raw = self._call("GET", f"{FILES_URL}/{self.parent_folder_id}?fields=id,name")
        if status != 200:
            return ""
        return _json(raw).get("name", "")

    # -- the three operations that matter -------------------------------------- #
    def upload_bytes(self, blob: bytes, name: str, mime: str = "application/octet-stream"):
        """Upload bytes we hold, straight from the request -- never touches
        disk on this end, so there is nothing to clean up if the upload
        fails."""
        folder = self.subfolder_id()
        meta = {"name": name}
        if folder:
            meta["parents"] = [folder]
        status, raw = self._call(
            "POST", f"{UPLOAD_URL}?uploadType=multipart&fields=id,webViewLink",
            files={"metadata": ("metadata", json.dumps(meta), "application/json"),
                   "file": (name, blob, mime)})
        body = _json(raw)
        if status not in (200, 201) or not body.get("id"):
            log.error("drive upload failed (%s): %s", status, body)
            return None
        return DriveFile(body["id"],
                          body.get("webViewLink") or f"https://drive.google.com/file/d/{body['id']}/view")

    def download(self, file_id: str) -> bytes:
        """Fetch a file's bytes -- for serving through a proxy view, never by
        hotlinking a Drive URL. A Drive `webViewLink` only opens for whoever
        is signed into the account it belongs to, which is never the
        end user, so every app using this client gates access itself."""
        if not file_id:
            return b""
        status, raw = self._call("GET", f"{FILES_URL}/{file_id}?alt=media")
        if status != 200:
            log.error("drive download failed (%s) for %s", status, file_id)
            return b""
        return raw

    def delete(self, file_id: str) -> bool:
        """Delete by id. A 404 counts as success: the goal state is 'not
        there', and treating it as failure would retry forever against a
        file that is already gone."""
        if not file_id:
            return True
        status, raw = self._call("DELETE", f"{FILES_URL}/{file_id}")
        if status in (200, 204, 404):
            return True
        log.error("drive delete of %s failed (%s): %s", file_id, status, _json(raw))
        return False


def _json(raw) -> dict:
    try:
        return json.loads(raw.decode("utf-8")) if raw else {}
    except Exception:
        return {}


def from_env(subfolder: str, transport=None):
    """A client scoped to `subfolder`, or None when Drive is not configured.

    "Unset means closed": nothing changes, and nothing silently falls back to
    local disk, until all four values are set. `subfolder` is required and
    always the caller's own app name (`"ustrip"`, `"matazim"`, ...) -- there
    is no default, because a missing subfolder name would otherwise upload
    into the shared root itself, where every app's files would land in one
    undifferentiated pile.
    """
    cid = os.environ.get("DRIVE_CLIENT_ID", "")
    secret = os.environ.get("DRIVE_CLIENT_SECRET", "")
    refresh = os.environ.get("DRIVE_REFRESH_TOKEN", "")
    parent = os.environ.get("DRIVE_FOLDER_ID", "")
    if not (cid and secret and refresh and parent):
        return None
    return DriveClient(
        client_id=cid, client_secret=secret, refresh_token=refresh,
        parent_folder_id=parent, subfolder_name=subfolder, transport=transport,
    )
