"""ustrip — photos live in Drive, not on Render's disk (Sprint 15, spec §0a.3).

What this guards, beyond what test_ustrip_items.py's happy-path upload
already covers:

- Drive being unconfigured refuses the upload loudly rather than silently
  falling back to local disk (the exact risk this sprint exists to close).
- The proxy view is gated the same way every other ustrip URL is — signed
  in as family, or refused — never a raw Drive URL that "anyone with the
  link" could open.
- Deleting a photo deletes the Drive file too, so nothing accumulates
  there that the app has forgotten about.
- A journal post can still be text-only; a photo is optional there and
  required on an item photo, matching the model as it was before this
  sprint.
- `migrate_ustrip_photos_to_drive` moves an old local file to Drive and
  only frees the local file after the upload is confirmed.
"""

import io

import pytest
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from PIL import Image

from app import drive
from ustrip.models import ItineraryDay, ItineraryPhoto, JournalPost, Trip


def _png(name="stop.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), (200, 90, 40)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class FakeDriveClient:
    """Same double as test_ustrip_items.py's — kept local per this repo's own
    convention of per-file fixtures rather than a shared conftest."""

    def __init__(self, upload_fails=False):
        self.uploaded = []
        self.deleted = []
        self.upload_fails = upload_fails
        self._next_id = 0

    def upload_bytes(self, blob, name, mime="image/jpeg"):
        if self.upload_fails:
            return None
        self._next_id += 1
        file_id = f"fake-{self._next_id}"
        self.uploaded.append((file_id, blob, name, mime))
        return drive.DriveFile(file_id, f"https://drive.google.com/file/d/{file_id}/view")

    def download(self, file_id):
        for fid, blob, _name, _mime in self.uploaded:
            if fid == file_id:
                return blob
        return b""

    def delete(self, file_id):
        self.deleted.append(file_id)
        return True


@pytest.fixture
def fake_drive(monkeypatch):
    client = FakeDriveClient()
    monkeypatch.setattr(drive, "from_env", lambda subfolder, transport=None: client)
    return client


@pytest.fixture
def drive_not_configured(monkeypatch):
    """The real `from_env()` behaviour when none of the four env vars are
    set — the state production is in until Avi copies the keys over."""
    monkeypatch.setattr(drive, "from_env", lambda subfolder, transport=None: None)


@pytest.fixture
def family_group(db):
    group, _ = Group.objects.get_or_create(name="family")
    return group


@pytest.fixture
def member(db, family_group):
    user = User.objects.create_user("family_member", password="x", first_name="Avi")
    user.groups.add(family_group)
    return user


@pytest.fixture
def stranger(db):
    """Signed in, but not in the family group — a real babook account, same
    as the one Sprint 13.1's lockdown tests use."""
    return User.objects.create_user("not_family", password="x")


@pytest.fixture
def trip(db):
    return Trip.objects.create(name="USA Trip 2026", start_date="2026-09-18", end_date="2026-10-02")


@pytest.fixture
def day(trip):
    return ItineraryDay.objects.create(trip=trip, order=0, label="1", date_label="Fri Sep 18", title="Arrival")


@pytest.fixture
def item(day):
    from ustrip.models import ItineraryItem

    return ItineraryItem.objects.create(day=day, order=0, kind="activity", title="Watkins Glen")


# --- Refuses loudly when Drive is not configured ----------------------------


@pytest.mark.django_db
def test_upload_refuses_out_loud_when_drive_is_not_configured(client, member, item, drive_not_configured):
    """Spec §0a.1: refused out loud, never silently lost — and never a
    silent fallback to local disk, which is the fault this sprint exists to
    close."""
    client.force_login(member)
    response = client.post("/ustrip/api/itinerary-photos/", {"item": item.id, "photo": _png()})
    assert response.status_code == 400
    assert "photo" in response.json()
    assert not ItineraryPhoto.objects.filter(item=item).exists()


@pytest.mark.django_db
def test_upload_refuses_out_loud_when_drive_upload_fails(client, member, item, monkeypatch):
    failing = FakeDriveClient(upload_fails=True)
    monkeypatch.setattr(drive, "from_env", lambda subfolder, transport=None: failing)
    client.force_login(member)
    response = client.post("/ustrip/api/itinerary-photos/", {"item": item.id, "photo": _png()})
    assert response.status_code == 400
    assert not ItineraryPhoto.objects.filter(item=item).exists()


# --- A journal post can still be text-only -----------------------------------


@pytest.mark.django_db
def test_a_journal_post_can_be_text_only(client, member, trip, fake_drive):
    client.force_login(member)
    response = client.post("/ustrip/api/journal-posts/", {"trip": trip.id, "caption": "Long day."})
    assert response.status_code == 201
    assert response.json()["photo_url"] == ""
    assert not fake_drive.uploaded


@pytest.mark.django_db
def test_a_journal_post_with_a_photo_goes_to_drive(client, member, trip, fake_drive):
    client.force_login(member)
    response = client.post(
        "/ustrip/api/journal-posts/", {"trip": trip.id, "caption": "Niagara!", "photo": _png()}
    )
    assert response.status_code == 201
    post = JournalPost.objects.get(trip=trip)
    assert post.drive_file_id == fake_drive.uploaded[0][0]
    assert not post.photo
    assert response.json()["photo_url"].endswith(f"/ustrip/journal/photo/{post.id}/file/")


# --- The proxy view is gated exactly like every other ustrip URL ------------


@pytest.mark.django_db
def test_a_family_member_can_view_the_photo(client, member, item, fake_drive):
    photo = ItineraryPhoto.objects.create(
        item=item, uploaded_by=member, drive_file_id="fake-1", content_type="image/jpeg"
    )
    fake_drive.uploaded.append(("fake-1", b"\x89PNGfakebytes", "x.jpg", "image/jpeg"))
    client.force_login(member)
    response = client.get(f"/ustrip/itinerary/photo/{photo.id}/file/")
    assert response.status_code == 200
    assert response.content == b"\x89PNGfakebytes"
    assert response["Content-Type"] == "image/jpeg"


@pytest.mark.django_db
def test_a_stranger_is_refused_the_photo(client, stranger, item, fake_drive):
    """Signed in to babook, but never added to `family` — Sprint 13.1's
    threat model applies to photo bytes exactly as it does to every other
    row (spec §3)."""
    photo = ItineraryPhoto.objects.create(item=item, drive_file_id="fake-1")
    client.force_login(stranger)
    response = client.get(f"/ustrip/itinerary/photo/{photo.id}/file/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_an_anonymous_visitor_is_refused_the_photo(client, item, fake_drive):
    photo = ItineraryPhoto.objects.create(item=item, drive_file_id="fake-1")
    response = client.get(f"/ustrip/itinerary/photo/{photo.id}/file/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_a_row_with_no_photo_at_all_is_404_not_a_broken_image(client, member, item, fake_drive):
    photo = ItineraryPhoto.objects.create(item=item, uploaded_by=member)  # never uploaded
    client.force_login(member)
    response = client.get(f"/ustrip/itinerary/photo/{photo.id}/file/")
    assert response.status_code == 404


# --- Deleting a photo deletes it in Drive too --------------------------------


@pytest.mark.django_db
def test_deleting_a_photo_deletes_it_in_drive(client, member, item, fake_drive):
    fake_drive.uploaded.append(("fake-1", b"x", "x.jpg", "image/jpeg"))
    photo = ItineraryPhoto.objects.create(item=item, uploaded_by=member, drive_file_id="fake-1")
    client.force_login(member)
    response = client.delete(f"/ustrip/api/itinerary-photos/{photo.id}/")
    assert response.status_code == 204
    assert fake_drive.deleted == ["fake-1"]


@pytest.mark.django_db
def test_deleting_a_row_with_no_drive_file_does_not_call_drive(client, member, item, fake_drive):
    """A row that never finished uploading (photo missing entirely) must not
    call delete() with an empty id — DriveClient.delete already treats that
    as a no-op, but nothing should even ask."""
    photo = ItineraryPhoto.objects.create(item=item, uploaded_by=member)
    client.force_login(member)
    client.delete(f"/ustrip/api/itinerary-photos/{photo.id}/")
    assert fake_drive.deleted == []


# --- The one-time backfill command -------------------------------------------


@pytest.mark.django_db
def test_migrate_command_moves_a_local_photo_to_drive_and_frees_the_file(item, fake_drive, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    photo = ItineraryPhoto.objects.create(item=item, photo=_png("old.png"))
    local_path = photo.photo.path
    assert __import__("os").path.exists(local_path)

    call_command("migrate_ustrip_photos_to_drive")

    photo.refresh_from_db()
    assert photo.drive_file_id == fake_drive.uploaded[0][0]
    assert not photo.photo
    assert not __import__("os").path.exists(local_path)


@pytest.mark.django_db
def test_migrate_command_leaves_a_failed_upload_untouched(item, settings, tmp_path, monkeypatch):
    """A failure must never delete the one copy the family has — the local
    file stays, `drive_file_id` stays blank, and a second run can retry."""
    settings.MEDIA_ROOT = tmp_path
    failing = FakeDriveClient(upload_fails=True)
    monkeypatch.setattr(drive, "from_env", lambda subfolder, transport=None: failing)
    photo = ItineraryPhoto.objects.create(item=item, photo=_png("old.png"))

    call_command("migrate_ustrip_photos_to_drive")

    photo.refresh_from_db()
    assert photo.drive_file_id == ""
    assert photo.photo
    assert __import__("os").path.exists(photo.photo.path)


@pytest.mark.django_db
def test_migrate_command_is_idempotent(item, fake_drive, settings, tmp_path):
    """Already-migrated rows are skipped outright — re-running after success
    must not re-upload or touch a row a second time."""
    settings.MEDIA_ROOT = tmp_path
    ItineraryPhoto.objects.create(item=item, drive_file_id="already-there", drive_url="https://drive/x")

    call_command("migrate_ustrip_photos_to_drive")

    assert fake_drive.uploaded == []


@pytest.mark.django_db
def test_migrate_command_refuses_when_drive_is_not_configured(item, drive_not_configured, settings, tmp_path):
    from django.core.management.base import CommandError

    settings.MEDIA_ROOT = tmp_path
    ItineraryPhoto.objects.create(item=item, photo=_png())
    with pytest.raises(CommandError):
        call_command("migrate_ustrip_photos_to_drive")
