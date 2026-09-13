"""SPR-M.27 — proposing a change is a conversation.

Avi, 2026-09-13: "I want the experience of proposing an improvement to be like
a chat, so she will write what she wants, you will comment and suggest and
discuss, and there will be a button סיים שיחה ושלח בקשה when she just want to
submit. For me, when approving, I want to see your recommendation."

The test that matters most here is `test_she_can_send_before_the_assistant_says
_anything`. An assistant that asks one more clarifying question before it will
accept a complaint is a suggestion box with extra steps, and she would use it
once. REQ-M.116 makes that a rule; this is what keeps it one.

Every test here runs with no model configured, which the root conftest enforces
for the whole suite. That is not avoidance: an unreachable model is a state
this product has to work in, and running the tests there means the fail-open
path is the one under test rather than the one nobody exercises.

Traces: REQ-M.115 to M.118, REQ-M.112, §4.11.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.sprm27

PASSWORD = "sprm27-pass-6624"


def _user(email, name):
    from app.models import UserProfile

    user = User.objects.create_user(username=email, email=email, password=PASSWORD)
    UserProfile.objects.update_or_create(user=user, defaults={"display_name": name})
    return user


def _manager(email="naomi@example.com"):
    from matazim.models import MemberProfile

    user = _user(email, "נעמי")
    MemberProfile.objects.update_or_create(user=user, defaults={"is_program_manager": True})
    return user


def _root(email="avi@example.com"):
    user = User.objects.create_superuser(email, email, PASSWORD)
    from app.models import UserProfile

    UserProfile.objects.update_or_create(user=user, defaults={"display_name": "אבי"})
    return user


def _start(client, body="הרשימה מבלבלת אותי", screen="/matazim/leader/students/"):
    from matazim.models import Request

    client.post(
        reverse("matazim:new_request"),
        {"body": body, "kind": Request.PROBLEM, "from_screen": screen},
    )
    return Request.objects.get()


# ------------------------------------------- F-M.27.1/2: it is a conversation


def test_writing_opens_a_conversation_rather_than_filing_a_form(client, db):
    """T-F-M.27.1-1: REQ-M.115, REQ-M.117."""
    from matazim.models import Request, RequestMessage

    client.force_login(_manager())
    draft = _start(client)

    assert draft.status == Request.DRAFT
    assert draft.from_screen == "/matazim/leader/students/"

    turns = list(draft.messages.all())
    assert len(turns) == 1, "her opening line should be the first turn"
    assert turns[0].who == RequestMessage.HER
    assert turns[0].body == "הרשימה מבלבלת אותי"


def test_she_can_keep_talking_and_every_word_is_hers(client, db):
    """T-F-M.27.1-2: REQ-M.112, REQ-M.117.

    Stored exactly as typed. A paraphrase of a complaint is a complaint that
    has already been answered.
    """
    from matazim.models import RequestMessage

    client.force_login(_manager())
    draft = _start(client)

    said = "בעיקר כשיש  שתי כיתות.\n\nובטלפון זה גרוע יותר. "
    client.post(reverse("matazim:talk", args=[draft.pk]), {"body": said})

    hers = [m.body for m in draft.messages.filter(who=RequestMessage.HER)]
    assert hers == ["הרשימה מבלבלת אותי", said.strip()]


def test_an_empty_turn_adds_nothing(client, db):
    """T-F-M.27.1-3: a stray submit must not put a blank line in a transcript."""
    client.force_login(_manager())
    draft = _start(client)

    client.post(reverse("matazim:talk", args=[draft.pk]), {"body": "   "})
    assert draft.messages.count() == 1


def test_the_conversation_is_private_to_the_person_having_it(client, db):
    """T-F-M.27.1-4: §4.4.

    An unsent draft is the most private thing in this product. Not even root
    has a reason to be in one: it is a thought somebody has not finished.
    """
    client.force_login(_manager("naomi@example.com"))
    draft = _start(client)

    client.force_login(_manager("other@example.com"))
    assert client.get(reverse("matazim:talk", args=[draft.pk])).status_code == 404

    client.force_login(_root())
    assert client.get(reverse("matazim:talk", args=[draft.pk])).status_code == 404


# ------------------------------------------- F-M.27.3: it never blocks her


def test_she_can_send_before_the_assistant_says_anything(client, db):
    """T-F-M.27.3-1: REQ-M.116, and the rule this sprint could most easily break.

    One message, no reply, straight to send. An assistant that wants one more
    clarifying question before it will accept a complaint is a suggestion box
    with extra steps.
    """
    from matazim.models import Request

    client.force_login(_manager())
    draft = _start(client)
    assert not draft.messages.filter(who="assistant").exists()

    response = client.post(reverse("matazim:send_request", args=[draft.pk]))
    assert response.status_code == 302

    draft.refresh_from_db()
    assert draft.status == Request.NEW, "the conversation stood between her and the button"


def test_the_send_button_is_on_the_screen_from_the_first_turn(client, db):
    """T-F-M.27.3-2: REQ-M.116.

    Present in the markup and not hidden behind a condition about how much has
    been discussed. Checked as the form's action, so a copy change does not
    fail this and a removed button does.
    """
    client.force_login(_manager())
    draft = _start(client)

    html = client.get(reverse("matazim:talk", args=[draft.pk])).content.decode()
    assert reverse("matazim:send_request", args=[draft.pk]) in html
    assert "סיים שיחה ושלח בקשה" in html


def test_a_draft_never_reaches_avis_queue(client, db):
    """T-F-M.27.3-3: REQ-M.117.

    A conversation she started and has not sent is not work anybody owes her
    an answer on, and it must not sit in his queue looking like one.
    """
    client.force_login(_manager())
    draft = _start(client, body="עוד לא סיימתי לחשוב על זה")

    client.force_login(_root())
    html = client.get(reverse("matazim:request_queue")).content.decode()
    assert "עוד לא סיימתי לחשוב על זה" not in html


def test_she_can_throw_a_draft_away(client, db):
    """T-F-M.27.3-4: REQ-M.117. An abandoned thought is not a backlog item."""
    from matazim.models import Request

    client.force_login(_manager())
    draft = _start(client)

    client.post(reverse("matazim:discard_request", args=[draft.pk]))
    assert not Request.objects.filter(pk=draft.pk).exists()


def test_a_sent_request_can_no_longer_be_talked_into(client, db):
    """T-F-M.27.3-5: once it is his, it is a record rather than a draft."""
    client.force_login(_manager())
    draft = _start(client)
    client.post(reverse("matazim:send_request", args=[draft.pk]))

    assert client.get(reverse("matazim:talk", args=[draft.pk])).status_code == 404
    assert client.post(
        reverse("matazim:discard_request", args=[draft.pk])
    ).status_code == 404


# ------------------------------------------- F-M.27.4: Avi's recommendation


def test_the_recommendation_is_taken_apart_for_the_card(db):
    """T-F-M.27.4-1: REQ-M.118.

    Three things in three places: what it touches, what I would do, and why.
    Split in Python rather than in a template, because his card and her log
    render from the same partial and would otherwise drift.
    """
    from matazim.assess import split_recommendation

    refs, call, why = split_recommendation(
        "REQ-M.24, REQ-M.33\nלבנות\nהייתי בונה את זה בספרינט הבא, זה קטן."
    )
    assert refs == "REQ-M.24, REQ-M.33"
    assert call == "לבנות"
    assert why == "הייתי בונה את זה בספרינט הבא, זה קטן."

    # A model that skips the citation line still parses.
    refs, call, why = split_recommendation("כבר קיים\nזה כבר במסך המחזור.")
    assert call == "כבר קיים"
    assert why == "זה כבר במסך המחזור."

    assert split_recommendation("") == ("", "", "")


def test_avi_sees_the_recommendation_beside_what_she_wrote(client, db):
    """T-F-M.27.4-2: REQ-M.118, REQ-M.112.

    Beside her words, never instead of them.
    """
    client.force_login(_manager())
    draft = _start(client, body="אי אפשר לראות מי מחכה לאישור")
    client.post(reverse("matazim:send_request", args=[draft.pk]))

    draft.refresh_from_db()
    draft.recommendation = "REQ-M.94\nלבנות\nהייתי מוסיף תג לשורה ברוסטר."
    draft.save(update_fields=["recommendation"])

    client.force_login(_root())
    html = client.get(reverse("matazim:request_queue")).content.decode()

    assert "אי אפשר לראות מי מחכה לאישור" in html, "her words are gone"
    assert "ההמלצה שלי" in html
    assert "הייתי מוסיף תג לשורה ברוסטר." in html
    assert "REQ-M.94" in html, "he cannot check the recommendation against anything"


def test_the_transcript_reaches_his_card(client, db):
    """T-F-M.27.4-3: REQ-M.117. The working out, for when he wants it."""
    client.force_login(_manager())
    draft = _start(client)
    client.post(reverse("matazim:talk", args=[draft.pk]), {"body": "בעיקר בטלפון"})
    client.post(reverse("matazim:send_request", args=[draft.pk]))

    client.force_login(_root())
    html = client.get(reverse("matazim:request_queue")).content.decode()
    assert "בעיקר בטלפון" in html
    assert "השיחה" in html


# ------------------------------------------- need to know


@pytest.mark.parametrize("view", ["new_request", "my_requests"])
def test_a_member_cannot_reach_the_loop(client, db, view):
    """T-F-M.27.5-1: REQ-M.102. This is a tool for the people who own it."""
    from matazim.models import MemberProfile

    member = _user("kid@example.com", "יובל")
    MemberProfile.objects.update_or_create(
        user=member, defaults={"birth_year": timezone.now().year - 14}
    )
    client.force_login(member)
    assert client.get(reverse(f"matazim:{view}")).status_code == 403


# ------------------------------------------- F-M.27.6: a proposal, not an edit


def test_the_assistant_may_offer_a_wording_and_she_may_ignore_it(client, db):
    """T-F-M.27.6-1: REQ-M.119.

    Avi: "Her words stays. The chat can propose new wording." Those two sit
    together only if the proposal is an offer rather than an edit applied to
    her, so nothing changes until she presses the button.
    """
    from matazim.models import RequestMessage

    client.force_login(_manager())
    draft = _start(client, body="הרשימה מבלבלת")

    RequestMessage.objects.create(
        request=draft,
        who=RequestMessage.ASSISTANT,
        body="REQ-M.94 נוגע בזה.\nנוסח מוצע: להוסיף תג שמראה מי מחכה לאישור.",
    )

    html = client.get(reverse("matazim:talk", args=[draft.pk])).content.decode()
    assert "להוסיף תג שמראה מי מחכה לאישור." in html
    assert reverse("matazim:adopt_wording", args=[draft.pk]) in html

    draft.refresh_from_db()
    assert draft.body == "הרשימה מבלבלת", "the suggestion edited her request by itself"


def test_adopting_a_wording_makes_it_hers_and_keeps_the_original(client, db):
    """T-F-M.27.6-2: REQ-M.119, REQ-M.112.

    The adopted text is stored as a turn of hers, because she chose it, and
    what she wrote first is still the opening line of the conversation.
    """
    from matazim.models import RequestMessage

    client.force_login(_manager())
    draft = _start(client, body="הרשימה מבלבלת")
    RequestMessage.objects.create(
        request=draft,
        who=RequestMessage.ASSISTANT,
        body="נוסח מוצע: להוסיף תג שמראה מי מחכה לאישור.",
    )

    client.post(reverse("matazim:adopt_wording", args=[draft.pk]))

    draft.refresh_from_db()
    assert draft.body == "להוסיף תג שמראה מי מחכה לאישור."

    turns = list(draft.messages.all())
    assert turns[0].body == "הרשימה מבלבלת", "her original words are gone"
    assert turns[0].is_hers
    assert turns[-1].body == "להוסיף תג שמראה מי מחכה לאישור."
    assert turns[-1].is_hers, "an adopted wording must be recorded as hers, not the machine's"


def test_a_proposal_is_printed_once(client, db):
    """T-F-M.27.6-3: it is a control, so it must not also be prose above it."""
    from matazim.models import RequestMessage

    client.force_login(_manager())
    draft = _start(client)
    RequestMessage.objects.create(
        request=draft,
        who=RequestMessage.ASSISTANT,
        body="שאלה אחת.\nנוסח מוצע: משפט הצעה ייחודי מאוד.",
    )

    html = client.get(reverse("matazim:talk", args=[draft.pk])).content.decode()
    assert html.count("משפט הצעה ייחודי מאוד.") == 1
    assert "שאלה אחת." in html, "the rest of the answer was thrown away with the proposal"


def test_adopting_nothing_changes_nothing(client, db):
    """T-F-M.27.6-4: a stray post when no proposal is on the table."""
    client.force_login(_manager())
    draft = _start(client, body="הרשימה מבלבלת")

    client.post(reverse("matazim:adopt_wording", args=[draft.pk]))

    draft.refresh_from_db()
    assert draft.body == "הרשימה מבלבלת"
    assert draft.messages.count() == 1


# ------------------------------------------- F-M.27.8: the scripted model


@pytest.fixture
def scripted(monkeypatch):
    """Replies written by hand against the real prompt (matazim/model_script.py).

    Avi's idea: the app cannot call me, so I read the prompt it would send and
    wrote what the model should answer. These tests are the reason that is
    worth doing — they exercise the whole loop against realistic content rather
    than against strings invented to satisfy a parser, deterministically and
    without a key.
    """
    monkeypatch.setenv("MATAZIM_SCRIPTED_AI", "1")


def test_the_prompt_carries_the_rules_and_the_screens(db):
    """T-F-M.27.8-1: REQ-M.115.

    Avi: "How do you plan to build the prompt so it will know the spec and the
    design of the site?" This is the answer, checked rather than asserted: the
    four spec sections and the routing table are in the prompt, all derived, so
    the day somebody adds a screen or changes RULE-1 the model is told without
    anybody remembering to update a string.
    """
    from matazim.assess import discussion_prompt
    from matazim.models import Request, RequestMessage

    naomi = _manager()
    row = Request.objects.create(
        author=naomi, body="שאלה", kind=Request.IDEA,
        from_screen="/matazim/my-path/", status=Request.DRAFT,
    )
    RequestMessage.objects.create(request=row, who=RequestMessage.HER, body="שאלה")

    prompt = discussion_prompt(row)

    assert "RULE-1" in prompt, "the model could propose a link out of the walls"
    assert "/matazim/leader/students/" in prompt, "it does not know what screens exist"
    assert "REQ-M.24" in prompt, "the requirement list is missing"
    assert "/matazim/my-path/" in prompt, "it does not know where she was standing"
    assert len(prompt) > 20000, "the context collapsed to something too thin to answer from"


def test_a_conversation_about_a_link_out_of_the_walls(client, db, scripted):
    """T-F-M.27.8-2: RULE-1, through the whole loop.

    The case that proves the design context earns its place: without §2.3 in
    the prompt there is nothing to tell the model that this one is forbidden.
    """
    from matazim.models import RequestMessage

    client.force_login(_manager())
    draft = _start(client, body="אפשר להוסיף קישור לקורסים באתר הראשי?")

    reply = draft.messages.filter(who=RequestMessage.ASSISTANT).first()
    assert reply is not None, "the scripted model said nothing"
    assert "RULE-1" in reply.body
    assert "/matazim/courses/" in reply.body, "refused without saying what does exist"


def test_a_conversation_about_something_that_already_exists(client, db, scripted):
    """T-F-M.27.8-3: REQ-M.115.

    The whole argument for a conversation: she gets the answer now instead of
    waiting a fortnight to be told it was already there.
    """
    from matazim.models import RequestMessage

    client.force_login(_manager())
    draft = _start(client, body="אפשר לייצא את המחזור לאקסל?")

    reply = draft.messages.filter(who=RequestMessage.ASSISTANT).first()
    assert "REQ-M.24" in reply.body
    assert "כבר קיים" in reply.body


def test_the_recommendation_never_contradicts_the_conversation(client, db, scripted):
    """T-F-M.27.8-4: REQ-M.118.

    If a turn named REQ-M.33, the recommendation on the same card must not then
    say there is no related requirement. Two opinions one paragraph apart is
    how Avi learns to stop reading both.
    """
    from matazim.assess import split_recommendation

    client.force_login(_manager())
    draft = _start(client, body="אני רוצה שיישלח מייל כשמט״צ מסיים את שתי ההדרכות")
    client.post(reverse("matazim:send_request", args=[draft.pk]))

    draft.refresh_from_db()
    refs, call, why = split_recommendation(draft.recommendation)

    assert "REQ-M.33" in refs, f"the conversation cited REQ-M.33 and the recommendation says {refs!r}"
    assert call, "no recommendation was made"
    assert why


def test_a_scripted_reply_is_never_used_unless_asked_for(client, db):
    """T-F-M.27.8-5: the fixtures are mine, not a model's.

    A screen presenting hand-written text as a model's opinion would be lying
    about where the words came from, so this stays off unless the environment
    asks for it. No `scripted` fixture here on purpose.
    """
    from matazim.models import RequestMessage

    client.force_login(_manager())
    draft = _start(client, body="אפשר לייצא את המחזור לאקסל?")

    assert not draft.messages.filter(who=RequestMessage.ASSISTANT).exists(), (
        "a scripted reply appeared without MATAZIM_SCRIPTED_AI being set"
    )
