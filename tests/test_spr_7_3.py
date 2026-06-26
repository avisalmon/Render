"""
SPR-7.3 — Matazim course intros (REQ-7.3.1 / QA-13). The insertion logic
(download + Bunny mocked).
"""
from unittest.mock import patch

import pytest
from django.core.management import call_command

from app.models import Course, Video


@pytest.mark.django_db
def test_intro_inserted_as_lesson_1_and_shifts():
    course = Course.objects.create(slug="python", title="פייתון", is_published=True,
                                   domain="matazim", track="software")
    Video.objects.create(course=course, lesson_order=1, title="ישן 1")
    Video.objects.create(course=course, lesson_order=2, title="ישן 2")

    with patch("app.authoring.pipeline.download_youtube", return_value="/tmp/x.mp4"), \
         patch("app.authoring.pipeline.probe_duration", return_value=123), \
         patch("app.authoring.pipeline.bunny_create", return_value="guid-123"), \
         patch("app.authoring.pipeline.bunny_upload", return_value=None):
        call_command("add_course_intros", "--only", "python")

    vids = list(course.videos.order_by("lesson_order"))
    assert vids[0].lesson_order == 1 and vids[0].title == "מבוא להדרכה"
    assert vids[0].bunny_video_id == "guid-123"
    assert vids[0].is_free_preview is True
    assert [v.title for v in vids] == ["מבוא להדרכה", "ישן 1", "ישן 2"]


@pytest.mark.django_db
def test_intro_insert_is_idempotent():
    course = Course.objects.create(slug="python", title="פייתון", is_published=True)
    Video.objects.create(course=course, lesson_order=1, title="מבוא להדרכה", bunny_video_id="g")
    Video.objects.create(course=course, lesson_order=2, title="שיעור")
    with patch("app.authoring.pipeline.download_youtube") as dl:
        call_command("add_course_intros", "--only", "python")
        dl.assert_not_called()  # already has the intro → skipped
    assert course.videos.count() == 2
