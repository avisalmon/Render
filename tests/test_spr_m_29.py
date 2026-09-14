"""SPR-M.29 — the written lesson, in מט״צים's own chrome.

Avi, 2026-09-13: "I want the trainings based on babook infrastructure but the
views are matazim dedicated. It's a matazim experience."

The structure was already right — one record of progress, no way out of the
walls — but the experience was not. This page rendered
`notes_markdown|truncatewords:60` into a grey paragraph: raw markdown, hashes
and asterisks included, cut off after sixty words. Eighteen of the nineteen
סקראץ׳ lessons carry notes and all nineteen carry a summary, so a מט״צ was
getting a fragment of the lesson rendered as source code while a learner on the
other product read the whole thing, inside the product that is supposed to be
the better experience.

And a lesson that carries a quiz was worse than thin. The completion rule gates
on `quiz_passed`, so a member would simply have stopped completing the course
with nothing on screen to answer and no explanation, the progress bar quietly
refusing to move.

Traces: REQ-M.126, REQ-M.13, REQ-M.14, RULE-1, RULE-3.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm29

PASSWORD = "sprm29-pass-2207"

NOTES = """## איך מתחילים

ברוכים הבאים. בשיעור הזה נלמד **שלושה דברים**:

- להתקין את הסביבה
- לפתוח פרויקט
- לשמור אותו

אפשר לקרוא עוד [באתר של סקראץ׳](https://scratch.mit.edu).

```python
print("שלום")
```
"""


def _member(email="kid@example.com"):
    from app.models import UserProfile
    from matazim.models import Leader, MemberProfile, Student

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": "יובל"})
    MemberProfile.objects.update_or_create(
        user=user,
        defaults={
            "entrance_test_passed_at": timezone.now(),
            "birth_year": timezone.now().year - 14,
            "guardian_consent_at": timezone.now(),
            "welcome_accepted_at": timezone.now(),
        },
    )
    teacher = User.objects.create_user("noa@example.com", "noa@example.com", PASSWORD)
    UserProfile.objects.update_or_create(user=teacher, defaults={"display_name": "נעה מורה"})
    from matazim.models import Institution

    # SPR-M.40: `Leader.institution` is required, this file has no manager
    # concept of its own.
    inst = Institution.objects.order_by("created_at").first() or Institution.objects.create(
        name="עתיד רמלה"
    )
    leader = Leader.objects.create(user=teacher, institution=inst, approved_at=timezone.now())
    Student.objects.create(user=user, leader=leader, status=Student.IN_TRAINING)
    return user


def _lesson(**extra):
    from app.models import Course, Video

    course = Course.objects.create(slug="scratch", title="סקראץ׳ למתחילים", is_published=True)
    fields = {
        "course": course,
        "title": "התקנה והגדרה",
        "lesson_order": 1,
        "bunny_video_id": "abc123",
        "notes_markdown": NOTES,
        "summary_he": "מתקינים את סקראץ׳ ופותחים פרויקט ראשון.",
    }
    fields.update(extra)
    return Video.objects.create(**fields)


# ------------------------------------------- the written lesson


def test_the_notes_are_rendered_not_dumped(client, db):
    """T-F-M.29.1-1: REQ-M.126, and the defect this sprint exists for.

    Markdown source in a grey paragraph is not a lesson. The headings, the
    list and the bold have to be what a reader sees.
    """
    lesson = _lesson()
    client.force_login(_member())

    html = client.get(reverse("matazim:learn_lesson", args=["scratch", 1])).content.decode()

    assert "<h2>איך מתחילים</h2>" in html, "the notes were not rendered"
    assert "<strong>שלושה דברים</strong>" in html
    assert "<li>להתקין את הסביבה</li>" in html
    assert "## איך מתחילים" not in html, "raw markdown reached the reader"


def test_the_whole_lesson_is_there(client, db):
    """T-F-M.29.1-2: REQ-M.126.

    It used to stop after sixty words. A lesson cut off in the middle is worse
    than one that is missing, because nobody notices the part that is gone.
    """
    lesson = _lesson()
    client.force_login(_member())

    html = client.get(reverse("matazim:learn_lesson", args=["scratch", 1])).content.decode()

    assert "לשמור אותו" in html, "the end of the notes is missing"
    assert lesson.summary_he in html


def test_a_link_in_the_lesson_opens_away_from_the_lesson(client, db):
    """T-F-M.29.1-3: a learner following a link should not lose their place."""
    _lesson()
    client.force_login(_member())

    html = client.get(reverse("matazim:learn_lesson", args=["scratch", 1])).content.decode()
    assert 'rel="noopener noreferrer"' in html
    assert 'target="_blank"' in html


def test_the_notes_are_rendered_by_the_shared_function(db):
    """T-F-M.29.1-4: RULE-3.

    The alternative was eight lines copied from the other product's view, and
    a lesson's notes should look the same wherever they are read.
    """
    from app.lesson_notes import render_lesson_notes

    html = render_lesson_notes("# כותרת\n\nטקסט **מודגש**.")
    assert "<h1>כותרת</h1>" in html
    assert "<strong>מודגש</strong>" in html
    assert render_lesson_notes("") == ""
    assert render_lesson_notes(None) == ""


# ------------------------------------------- the quiz


def test_a_lesson_with_a_quiz_shows_it(client, db):
    """T-F-M.29.2-1: REQ-M.126, and the trap this closes.

    The completion rule gates on `quiz_passed`. A lesson carrying a quiz that
    the page did not render was a member who could not finish the course, with
    nothing on screen to answer and no explanation.
    """
    from app.models import LessonQuiz

    lesson = _lesson()
    LessonQuiz.objects.create(
        video=lesson,
        question="מה עושים קודם?",
        options_json=[
            {"text": "מתקינים", "is_correct": True},
            {"text": "מוחקים", "is_correct": False},
        ],
        requires_correct=True,
    )
    client.force_login(_member())

    html = client.get(reverse("matazim:learn_lesson", args=["scratch", 1])).content.decode()

    assert "מה עושים קודם?" in html
    assert "מתקינים" in html and "מוחקים" in html
    assert 'id="mzQuiz"' in html


def test_a_lesson_without_a_quiz_shows_no_quiz(client, db):
    """T-F-M.29.2-2: an empty question box on every lesson is furniture."""
    _lesson()
    client.force_login(_member())

    html = client.get(reverse("matazim:learn_lesson", args=["scratch", 1])).content.decode()
    assert 'id="mzQuiz"' not in html


def test_the_quiz_pass_is_written_through_the_shared_engine(client, db):
    """T-F-M.29.2-3: REQ-M.14, RULE-3.

    `quiz_passed` is a field on the progress row, so the answer rides the same
    endpoint the heartbeat uses. A second write of our own would be the
    divergence RULE-3 exists to prevent, and it would be invisible.
    """
    import json

    from app.models import LessonQuiz, UserVideoProgress

    lesson = _lesson()
    LessonQuiz.objects.create(
        video=lesson, question="?", options_json=[{"text": "כן", "is_correct": True}]
    )
    user = _member()
    client.force_login(user)

    html = client.get(reverse("matazim:learn_lesson", args=["scratch", 1])).content.decode()
    assert "/api/video-progress/" in html, "the page has no way to record the answer"

    response = client.post(
        "/api/video-progress/",
        data=json.dumps(
            {"video_id": lesson.pk, "position": 0, "percent": 100, "quiz_passed": True}
        ),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert UserVideoProgress.objects.get(user=user, video=lesson).quiz_passed


# ------------------------------------------- the reflection


def test_a_lesson_with_a_reflection_prompt_shows_it(client, db):
    """T-F-M.29.3-1: REQ-M.126. The other half of what the completion rule gates on."""
    _lesson(reflection_prompt="מה היה הכי מפתיע?")
    client.force_login(_member())

    html = client.get(reverse("matazim:learn_lesson", args=["scratch", 1])).content.decode()
    assert "מה היה הכי מפתיע?" in html
    assert 'id="mzReflect"' in html


def test_an_answered_reflection_comes_back(client, db):
    """T-F-M.29.3-2: somebody returning to a lesson should find what they wrote."""
    from app.models import LessonReflection

    lesson = _lesson(reflection_prompt="מה היה הכי מפתיע?")
    user = _member()
    LessonReflection.objects.create(
        user=user, video=lesson, prompt="מה היה הכי מפתיע?", user_text="שהבלוקים נצמדים"
    )
    client.force_login(user)

    html = client.get(reverse("matazim:learn_lesson", args=["scratch", 1])).content.decode()
    assert "שהבלוקים נצמדים" in html


# ------------------------------------------- the walls still hold


def test_the_lesson_still_names_no_other_product(client, db):
    """T-F-M.29.4-1: RULE-1, RULE-2.

    Caught while building this: a `<script>` comment explaining where the write
    goes is served to the reader, and it named the other product. Django
    comments are not rendered; script comments are.
    """
    _lesson()
    client.force_login(_member())

    html = client.get(reverse("matazim:learn_lesson", args=["scratch", 1])).content.decode()
    assert "babook" not in html.lower()
    assert "mz-container" in html, "not our chrome"


def test_the_lesson_links_nowhere_but_our_own_walls(client, db):
    """T-F-M.29.4-2: RULE-1.

    The notes may link out, because they are content a person wrote and those
    links open in their own tab. The page's own navigation may not.
    """
    import re

    _lesson()
    client.force_login(_member())

    html = client.get(reverse("matazim:learn_lesson", args=["scratch", 1])).content.decode()
    notes = html.split('class="mz-notes"')[-1] if 'class="mz-notes"' in html else ""

    for href in re.findall(r'href="(/[^"]*)"', html.replace(notes, "")):
        assert href.startswith(("/matazim/", "/static/")), f"the page leaves the walls: {href}"
