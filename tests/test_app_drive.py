"""app/drive.py — the shared Drive client's own request-building logic.

`DriveClient` accepts an injectable `transport`, exactly so tests never touch
the real Google API — the ustrip-level tests (test_ustrip_photos_drive.py)
already cover the integration surface with a fake `DriveClient` double; these
test the client's own request shapes directly.

`create_folder` exists because of a real bug found setting this up for the
first time, live, against a real Google account: `DRIVE_FOLDER_ID` pointed at
a folder created by hand in the Drive web UI, and the narrow `drive.file`
scope (deliberately the least-privileged one that works) refused to see it —
that scope only ever grants visibility into files an app *created itself*.
"did not resolve to a folder your account can see" on a folder that
obviously existed was the symptom; the fix is that the root folder has to be
made through this client, never through Drive's own UI.
"""

import json

import pytest

from app.drive import DriveClient, DriveError


class _FakeTransport:
    """Records every call and returns a canned (status, body) per URL."""

    def __init__(self, responses):
        self.responses = responses  # {(method, url_startswith): (status, dict)}
        self.calls = []

    def __call__(self, method, url, headers=None, data=None, files=None, timeout=None):
        self.calls.append({"method": method, "url": url, "data": data})
        if method == "POST" and "/token" in url:
            return 200, json.dumps({"access_token": "fake-token", "expires_in": 3600}).encode()
        for (m, prefix), (status, body) in self.responses.items():
            if method == m and url.startswith(prefix):
                return status, json.dumps(body).encode()
        raise AssertionError(f"unexpected call: {method} {url}")


def _client(responses):
    transport = _FakeTransport(responses)
    client = DriveClient(
        client_id="cid", client_secret="secret", refresh_token="refresh",
        parent_folder_id="", subfolder_name="", transport=transport,
    )
    return client, transport


def test_create_folder_at_drive_root_sends_no_parents():
    """No `parent` argument means "My Drive" itself — the request body must
    not include a `parents` key at all, not an empty list (an empty
    `parents: []` is not the same request to the Drive API)."""
    client, transport = _client({
        ("POST", "https://www.googleapis.com/drive/v3/files"): (200, {"id": "new-folder-id"}),
    })

    folder_id = client.create_folder("babook storage")

    assert folder_id == "new-folder-id"
    body = json.loads(next(c for c in transport.calls if c["method"] == "POST" and "files" in c["url"])["data"])
    assert body == {"name": "babook storage", "mimeType": "application/vnd.google-apps.folder"}
    assert "parents" not in body


def test_create_folder_with_a_parent_includes_it():
    client, transport = _client({
        ("POST", "https://www.googleapis.com/drive/v3/files"): (200, {"id": "sub-id"}),
    })

    folder_id = client.create_folder("ustrip", parent="root-id")

    assert folder_id == "sub-id"
    body = json.loads(next(c for c in transport.calls if c["method"] == "POST" and "files" in c["url"])["data"])
    assert body["parents"] == ["root-id"]


def test_create_folder_raises_loudly_on_failure():
    """A silent None here would surface later as a confusing "could not
    upload" from something that never touched a folder at all — the failure
    belongs at the point it actually happened."""
    client, _transport = _client({
        ("POST", "https://www.googleapis.com/drive/v3/files"): (403, {"error": "insufficientPermissions"}),
    })

    with pytest.raises(DriveError, match="could not create folder"):
        client.create_folder("babook storage")


def test_root_folder_name_never_creates_anything():
    """The read-only counterpart used by `drive_setup --check`: it must be
    possible to verify a setup repeatedly without leaving folders behind."""
    client, transport = _client({
        ("GET", "https://www.googleapis.com/drive/v3/files/root-id"): (200, {"id": "root-id", "name": "babook storage"}),
    })
    client.parent_folder_id = "root-id"

    name = client.root_folder_name()

    assert name == "babook storage"
    assert not any(c["method"] == "POST" and "files" in c["url"] for c in transport.calls)
