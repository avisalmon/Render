"""Is the generated text actually right? (spec §8, G3)

The schema check in `ai._json_call` answers "is this the shape we asked for".
This answers the different question "is this any good", and it runs as part of
generating rather than as a test, because the failures it catches are things a
model does occasionally and unpredictably: they cannot be caught once and
fixed, only caught every time.

Three kinds of problem, each from something that actually happened:

1. **A script that does not belong.** A Hebrew feature came back with the
   Russian word "меню" sitting inside a Hebrew sentence. Nothing in the app
   noticed, because the JSON was perfectly well-formed.

2. **The genre slipping back.** The output is a newspaper feature written a
   year and a half after the thing opened. Models drift towards the
   announcement they have seen a million of, and an announcement is exactly
   what Avi rejected. The two unambiguous tells are a headline announcing a
   launch and the company talking about itself in the first person.

3. **A shape nobody would read.** A four-line "feature" with no quotes in it
   is a failure even when every field is present.

**What a problem causes is a retry, not a refusal.** `_json_call` asks again;
if the second answer is no better, the better of the two is used and the
blemish is logged. Refusing outright would mean a stray foreign word costs
somebody the artifact they came for, which is a worse outcome than a small
flaw in it.

Deliberately conservative. A check that cries wolf gets switched off, so each
rule here only fires on something that is never legitimate.
"""

import re

#: Scripts that never legitimately appear in this app's output. Latin is
#: allowed in Hebrew text on purpose: brand names carry it ("Netflix",
#: "Uber", "Dropbox"), and so do the framework's own terms. Hebrew is allowed
#: in English text for the same reason, since a concept can be named in
#: Hebrew and quoted in an English piece.
FOREIGN_SCRIPTS = {
    "Cyrillic": r"[Ѐ-ӿ]",
    "Greek": r"[Ͱ-Ͽ]",
    "Arabic": r"[؀-ۿ]",
    "Devanagari": r"[ऀ-ॿ]",
    "Armenian": r"[԰-֏]",
    "Thai": r"[฀-๿]",
    "Han": r"[一-鿿]",
    "Hangul": r"[가-힯]",
    "Kana": r"[぀-ヿ]",
}

#: A headline announcing a launch. Checked in the headline only: a body can
#: legitimately say "since it opened a year and a half ago", and flagging that
#: would be the kind of false positive that gets a check disabled.
LAUNCH_HEADLINE = {
    "he": re.compile(r"יוצא לדרך|יוצאת לדרך|משיק|משיקה|נפתח בקרוב|עומד להיפתח"),
    "en": re.compile(r"\b(launch(es|ing)?|unveil(s|ing)?|introduc(es|ing)|"
                     r"coming soon|now open)\b", re.I),
}

#: The company talking about itself. This one is unambiguous in both
#: languages: a reporter never says "our solution".
COMPANY_VOICE = {
    "he": re.compile(r"הפתרון שלנו|אנחנו מציעים|אנו מציעים|השירות שלנו מאפשר|"
                     r"אנחנו מאמינים|אנו מתכננים"),
    "en": re.compile(r"\bour (solution|service|platform|mission)\b|"
                     r"\bwe (offer|provide|believe|plan to|are excited)\b", re.I),
}

#: Below this a "feature" is a stub, whatever the fields say.
MIN_BODY_CHARS = 400
MAX_HEADLINE_CHARS = 140

#: Straight and curly, both languages' conventions.
QUOTE_MARKS = re.compile(r'["“”«»]')


def foreign_scripts(text):
    """Names of scripts present that should not be. Empty when clean."""
    found = []
    for name, pattern in FOREIGN_SCRIPTS.items():
        if re.search(pattern, text or ""):
            found.append(name)
    return found


def _language_of(language):
    return "he" if (language or "he").startswith("he") else "en"


def review_feature(data, language):
    """Problems with a generated feature, as short readable strings.

    Returns [] when it is fine. Never raises: a checker that can crash is a
    checker that takes the feature down with it.
    """
    try:
        lang = _language_of(language)
        headline = str(data.get("headline") or "")
        body = str(data.get("body") or "")
        document = str(data.get("document_body") or "")
        problems = []

        for where, text in (("headline", headline), ("body", body),
                            ("document", document)):
            for script in foreign_scripts(text):
                problems.append(f"{script} characters in the {where}")

        if LAUNCH_HEADLINE[lang].search(headline):
            problems.append("the headline announces a launch rather than "
                            "reporting on something already running")

        if COMPANY_VOICE[lang].search(body):
            problems.append("written in the company's own voice rather than "
                            "a reporter's")

        if not headline.strip():
            problems.append("no headline")
        elif len(headline) > MAX_HEADLINE_CHARS:
            problems.append(f"headline is {len(headline)} characters")

        if len(body.strip()) < MIN_BODY_CHARS:
            problems.append(f"the feature is only {len(body.strip())} characters")
        if len(QUOTE_MARKS.findall(body)) < 4:
            problems.append("no quotes: a feature without them is not reportage")

        return problems
    except Exception:  # pragma: no cover - a checker must never be the fault
        return []


def review_text(text):
    """The script check alone, for the stages that only produce prose."""
    return [f"{script} characters" for script in foreign_scripts(text or "")]
