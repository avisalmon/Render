"""exo — the correctness pass that runs while generating (spec §8, G3).

These rules run on every generated feature, not in CI, because what they catch
is not a bug that can be fixed once: it is a thing a model does occasionally
and unpredictably. A stray Russian word landed in the middle of a Hebrew
sentence and nothing noticed, because the JSON around it was perfect.

The tests below are as much about **what must not fire** as about what must.
A check that cries wolf gets switched off, and then it catches nothing at all.
"""

import pytest

from exo import quality

# Plain functions over plain strings: no database, no network.
pytestmark = []


A_REAL_FEATURE_HE = {
    "headline": "שנה וחצי אחרי: מה קרה לחנות הפלאפל בשכונה",
    "body": (
        "בשתיים בצהריים, ביום שלישי רגיל, התור מגיע עד הפינה. "
        "אף אחד לא נראה מופתע. ניחוחות של טחינה ושל שמן חם ממלאים את הרחוב, "
        "ואנשים עומדים בשמש בלי להתלונן.\n\n"
        "מאז שנפתח המקום לפני שנה וחצי, הפלאפל הפך לסמל מקומי. "
        "המתכונים מגיעים מהתושבים, והתפריט משתנה כל חודש.\n\n"
        "\"בהתחלה חשבנו שזה יעבוד אחרת לגמרי\", אומרת הבעלים. "
        "\"הלקוחות לימדו אותנו מה זה באמת.\"\n\n"
        "בתיה פקמן מגיעה שלוש פעמים בשבוע. \"זה פשוט המקום שהולכים אליו.\""
    ),
    "document_body": "המטרה: פלאפל כאמנות. מה מיוחד: המתכון נבנה עם הלקוחות.",
}

A_REAL_FEATURE_EN = {
    "headline": "Eighteen months on: what became of the falafel shop",
    "body": (
        "At two in the afternoon on an ordinary Tuesday, the queue reaches the "
        "corner. Nobody looks surprised. The smell of tahini and hot oil fills "
        "the street, and people wait in the sun without complaining.\n\n"
        "Since it opened a year and a half ago, the shop has become a local "
        "landmark. The recipes come from the neighbourhood, and the menu "
        "changes every month.\n\n"
        "\"We thought it would work completely differently,\" the owner says. "
        "\"The customers taught us what this actually was.\"\n\n"
        "Batya Pekman comes three times a week. \"It is just where you go.\""
    ),
    "document_body": "Purpose: falafel as craft. What is special: the shared recipe.",
}


# ---- the ones that must not fire --------------------------------------- #

def test_a_good_feature_has_no_problems():
    assert quality.review_feature(A_REAL_FEATURE_HE, "he") == []
    assert quality.review_feature(A_REAL_FEATURE_EN, "en") == []


def test_latin_inside_hebrew_is_fine():
    """Brand names carry Latin, and so do the framework's own terms. Flagging
    them would make the check unusable in exactly the app it was written for."""
    data = dict(A_REAL_FEATURE_HE)
    data["body"] += "\n\nהם משתמשים ב-Netflix, ב-Uber וב-Dropbox כהשראה, ו-MTP ברור."
    assert quality.review_feature(data, "he") == []


def test_hebrew_inside_english_is_fine():
    """A concept can be named in Hebrew and quoted in an English piece."""
    data = dict(A_REAL_FEATURE_EN)
    data["body"] += "\n\nThe sign still reads חנות פלאפל, as it did on day one."
    assert quality.review_feature(data, "en") == []


def test_a_body_may_mention_the_opening_without_being_an_announcement():
    """"Since it opened a year and a half ago" is exactly what a feature says.
    Only the *headline* is checked for launch language, because this sentence
    in the body is correct and flagging it would be the false positive that
    gets the whole check disabled."""
    data = dict(A_REAL_FEATURE_HE)
    data["body"] += "\n\nמאז שהמקום נפתח, השכונה השתנתה."
    assert quality.review_feature(data, "he") == []


# ---- the ones that must -------------------------------------------------- #

def test_a_stray_script_is_caught():
    """The actual bug: "меню" in the middle of a Hebrew sentence."""
    data = dict(A_REAL_FEATURE_HE)
    data["body"] = data["body"].replace("התפריט", "הס меню")
    problems = quality.review_feature(data, "he")
    assert any("Cyrillic" in p for p in problems), problems


@pytest.mark.parametrize("sample,script", [
    ("שלום меню עולם", "Cyrillic"),
    ("shalom κόσμος world", "Greek"),
    ("hello 世界 world", "Han"),
    ("hello مرحبا world", "Arabic"),
])
def test_every_foreign_script_is_named(sample, script):
    assert quality.foreign_scripts(sample) == [script]


def test_a_clean_string_names_nothing():
    assert quality.foreign_scripts("שלום hello 123 — \"quote\"") == []


def test_a_headline_that_announces_a_launch_is_caught():
    """The genre slipping back, which is what Avi rejected."""
    for headline, language in [
        ("חנות פלאפל משיקה סניף חדש", "he"),
        ("Falafel shop launches new branch", "en"),
        ("Introducing the falafel shop", "en"),
    ]:
        data = dict(A_REAL_FEATURE_HE if language == "he" else A_REAL_FEATURE_EN)
        data["headline"] = headline
        problems = quality.review_feature(data, language)
        assert any("announces a launch" in p for p in problems), (headline, problems)


def test_the_company_talking_about_itself_is_caught():
    for phrase, language in [
        ("הפתרון שלנו הוא הפלאפל הטוב בעיר.", "he"),
        ("Our solution is the best falafel in town.", "en"),
        ("We offer a new kind of falafel.", "en"),
    ]:
        data = dict(A_REAL_FEATURE_HE if language == "he" else A_REAL_FEATURE_EN)
        data["body"] = data["body"] + "\n\n" + phrase
        problems = quality.review_feature(data, language)
        assert any("company's own voice" in p for p in problems), (phrase, problems)


def test_a_feature_with_no_quotes_is_caught():
    data = dict(A_REAL_FEATURE_HE)
    data["body"] = data["body"].replace('"', "")
    assert any("no quotes" in p for p in quality.review_feature(data, "he"))


def test_a_stub_of_a_feature_is_caught():
    data = {"headline": "כותרת", "body": "שתי מילים", "document_body": "x"}
    problems = quality.review_feature(data, "he")
    assert any("characters" in p for p in problems)


def test_a_missing_headline_is_caught():
    data = dict(A_REAL_FEATURE_HE, headline="")
    assert "no headline" in quality.review_feature(data, "he")


# ---- the checker must never be the fault --------------------------------- #

def test_rubbish_input_never_raises():
    """A checker that can crash takes the artifact down with it, which is far
    worse than the blemish it was looking for.

    Note what is asserted: that it *returns a list*, not that the list is
    empty. An empty feature genuinely has problems and should say so; the
    contract here is only that nothing explodes.
    """
    assert quality.review_feature(None, "he") == []
    assert isinstance(quality.review_feature({}, "he"), list)
    assert isinstance(quality.review_feature({"headline": 5, "body": None}, "zz"),
                      list)
    assert quality.review_text(None) == []


def test_the_stub_passes_its_own_rules():
    """The stub has to satisfy the same check as the real thing. A stub that
    quietly failed would mean the suite tested a promise the live app does not
    keep."""
    from exo.ai import _stub_output
    from exo.models import Concept

    # Unsaved instance: the stub reads fields and writes nothing, so this
    # needs no database.
    concept = Concept(title="חנות פלאפל", mtp="פלאפל כאמנות",
                      mtp_note="כל מנה היא משהו שמישהו התכוון אליו",
                      special="המתכון נבנה עם הלקוחות", unique="תחרות פתוחה")
    for language in ("he", "en"):
        produced = _stub_output(concept, [], language)
        assert quality.review_feature(produced, language) == []
