"""
SPR-7.5 — Re-transcription tooling (REQ-7.5.1 / QA-14). Orchestration only
(download + OpenAI mocked); the real batch is a supervised run.
"""
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command

from app.models import Course, Video


def _fake_ffmpeg(cmd, *a, **k):
    # the ffmpeg output file is the last positional arg in cmd
    open(cmd[-1], "wb").write(b"x")
    from unittest.mock import MagicMock
    return MagicMock()


@pytest.mark.django_db
def test_retranscribe_updates_notes():
    course = Course.objects.create(slug="python", title="פייתון", is_published=True)
    v = Video.objects.create(course=course, lesson_order=1, title="שיעור",
                             bunny_video_id="guid1", notes_markdown="ישן")

    def fake_urlretrieve(url, dest):
        open(dest, "wb").write(b"x")

    client = MagicMock()
    client.audio.transcriptions.create.return_value = "טקסט מתומלל"
    with patch("app.bunny.generate_signed_url", return_value="https://x/play.mp4"), \
         patch("urllib.request.urlretrieve", side_effect=fake_urlretrieve), \
         patch("app.authoring.pipeline.probe_duration", return_value=0), \
         patch("app.authoring.pipeline._client", return_value=client), \
         patch("app.authoring.pipeline.gen_notes", return_value="## סיכום חדש"), \
         patch("subprocess.run", side_effect=_fake_ffmpeg):
        call_command("retranscribe_course", "python")
    v.refresh_from_db()
    assert v.notes_markdown == "## סיכום חדש"


@pytest.mark.django_db
def test_retranscribe_dry_run_does_not_save():
    course = Course.objects.create(slug="python", title="פייתון", is_published=True)
    v = Video.objects.create(course=course, lesson_order=1, title="שיעור",
                             bunny_video_id="guid1", notes_markdown="ישן")

    client = MagicMock()
    client.audio.transcriptions.create.return_value = "טקסט"
    with patch("app.bunny.generate_signed_url", return_value="https://x/play.mp4"), \
         patch("urllib.request.urlretrieve", side_effect=lambda u, d: open(d, "wb").write(b"x")), \
         patch("app.authoring.pipeline.probe_duration", return_value=0), \
         patch("app.authoring.pipeline._client", return_value=client), \
         patch("app.authoring.pipeline.gen_notes", return_value="## חדש"), \
         patch("subprocess.run", side_effect=_fake_ffmpeg):
        call_command("retranscribe_course", "python", "--dry-run")
    v.refresh_from_db()
    assert v.notes_markdown == "ישן"  # dry run: unchanged
