"""exo's one door to a language model (spec §8).

**Why one door.** `building_an_app.md` Rule 2 says cross-app reach is rare,
deliberate and named. memz set the precedent: a single adapter module that
reaches for the site's shared wrapper, so every other module in the app
imports from its own app and the encapsulation test has exactly one name to
know about. Views never call a provider.

**Structured output is validated, never trusted.** Options, score and the
stress test come back as JSON and are schema-checked before a row is written.
A model that returns prose where a list was asked for is a failure we retry
once and then surface — not something we half-parse into the database.

**Stub mode is a feature, not a fallback.** With no `OPENAI_API_KEY` the site
wrapper returns a stub string. Rather than propagate that into the journey,
this module produces deterministic, well-formed local content so the whole
flow works end to end with no key and no spend: tests are repeatable, and the
app can be demonstrated live without a bill. It is *labelled* — `is_stub()` is
what the UI reads to say so out loud, because content that looks generated and
is not would be a lie told by omission.

**Failure never loses work.** Every function here reads rows and returns
values; the caller writes rows. A provider error leaves the previous state
exactly as it was.
"""

import json
import logging
import os
import re

from django.conf import settings

from . import prompts, quality
from .models import AiCall, Concept

log = logging.getLogger("exo.ai")


class AiError(Exception):
    """A provider call that could not be turned into usable content."""


class AiLimit(AiError):
    """A guard refused before any provider was called (spec §8, G5)."""


# ---------------------------------------------------------------------------
# the door
# ---------------------------------------------------------------------------


def is_stub():
    """True when no key is configured and content is produced locally."""
    return not getattr(settings, "OPENAI_API_KEY", "")


#: How long exo is willing to wait for a provider (spec §8, G5). The OpenAI
#: SDK's own default is minutes, which on a web worker means a person watching
#: a spinner for longer than they will tolerate and a worker that cannot serve
#: anyone else meanwhile. Bounded here rather than in `app/ai_chat.py`, because
#: that wrapper is shared with every other app on the site and this is exo's
#: judgement about exo's screens, not a site-wide decision to make tonight.
def _timeout():
    try:
        return max(5, min(180, int(os.environ.get("EXO_AI_TIMEOUT", "45") or 45)))
    except (TypeError, ValueError):
        return 45


def _call(messages, system, task, user=None, concept=None, attribute=None):
    """The site's shared wrapper, with exo's timeout and logging around it.

    The inner import is deliberately inside the function: a module-level bind
    would freeze the function object, and every test that swaps the wrapper to
    simulate an outage would be swapping a name nothing reads. memz records
    the same reasoning.

    The call runs on a worker thread purely so the wait can be bounded. If the
    deadline passes we stop waiting and raise; the thread finishes its HTTP
    request in the background and its result is discarded. That is deliberate:
    abandoning a response costs one wasted call, while waiting costs the person
    their patience and the worker its availability.
    """
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as Timeout

    from app.ai_chat import call_openai

    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(call_openai, messages, system_prompt=system)
    # `shutdown(wait=False)` rather than a `with` block: the context manager
    # joins its threads on the way out, which would reinstate exactly the wait
    # this timeout exists to avoid.
    pool.shutdown(wait=False)
    try:
        result = future.result(timeout=_timeout()) or {}
    except Timeout:
        log.warning("exo ai %s: no answer within %ss", task, _timeout())
        _log_call(user, concept, task, {}, ok=False,
                  detail=f"timeout after {_timeout()}s", attribute=attribute)
        raise AiError(f"{task}: the model did not answer in time")

    content = (result.get("content") or "").strip()
    ok = bool(content)
    _log_call(user, concept, task, result, ok=ok,
              detail="" if ok else "empty response", attribute=attribute)
    if not ok:
        raise AiError("empty response from the model")
    return content


def _log_call(user, concept, task, result, ok, detail="", attribute=None):
    """Every provider call, logged (spec §8, G5) — including the ones that
    failed, since a timeout that leaves no trace is a cost nobody can explain
    later. Accounting must never be the reason a feature fails, so this
    swallows its own errors."""
    try:
        AiCall.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            concept=concept,
            attribute=attribute,
            task=task,
            model=(result or {}).get("model") or "",
            prompt_tokens=(result or {}).get("prompt_tokens") or 0,
            completion_tokens=(result or {}).get("completion_tokens") or 0,
            ok=ok,
            detail=detail,
        )
    except Exception:
        log.exception("exo: could not log an AI call")


_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


def _json_call(messages, system, task, schema_keys, user=None, concept=None,
               retries=1, attribute=None, check=None):
    """A call that must return a JSON object with `schema_keys`.

    Retried once, because a single malformed answer is usually noise; after
    that it is a real failure and the caller gets to show a retry rather than
    a page of nonsense.

    `check` is the second question, and a different one. The schema says
    whether this is the right *shape*; `check` says whether the content is any
    good — a stray Cyrillic word in a Hebrew sentence, a feature that has
    drifted back into announcing a launch, a body too short to read. See
    `exo/quality.py`.

    **The two failures are not treated the same.** A malformed answer is
    unusable and, after the retries, raises. Content problems are asked about
    again, but if the second answer is no better the *better of the two* is
    returned with the blemish logged, because refusing outright would mean a
    stray foreign word costs somebody the artifact they came for. Losing the
    work is worse than a small flaw in it.
    """
    last = None
    best = None
    best_problems = None

    for attempt in range(retries + 1):
        content = _call(messages, system, task, user=user, concept=concept,
                        attribute=attribute)
        match = _JSON_BLOCK.search(content)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                last = exc
            else:
                if all(k in data for k in schema_keys):
                    problems = check(data) if check else []
                    if not problems:
                        return data
                    # Keep the least bad answer seen so far.
                    if best is None or len(problems) < len(best_problems):
                        best, best_problems = data, problems
                    last = ValueError("; ".join(problems))
                else:
                    last = ValueError(f"missing keys, wanted {schema_keys}")
        else:
            last = ValueError("no JSON object in the response")
        log.warning("exo ai %s: unusable response (attempt %s): %s",
                    task, attempt + 1, last)

    if best is not None:
        log.warning("exo ai %s: returning the best of %s attempts with: %s",
                    task, retries + 1, "; ".join(best_problems))
        return best
    raise AiError(f"{task}: {last}")


# ---------------------------------------------------------------------------
# the guards (spec §8, G5)
# ---------------------------------------------------------------------------
#
# Three ceilings, in widening circles: this concept's stage, this person's day,
# and the whole site's day. The approval gate is the real cost control; these
# exist so that a loop in a template, a member with a stuck retry button, or a
# workshop that goes better than expected cannot turn into a bill nobody chose.
#
# All three raise `AiLimit` *before* any provider is reached, and every view
# turns that into "try again later" rather than an error — a limit is a wait,
# not a fault, and it must never read like the app is broken.

def _env_int(name, default):
    try:
        value = int(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def limits():
    """The ceilings in force, in one place, so the usage screen shows the same
    numbers the guards actually enforce instead of a second copy that drifts."""
    return {
        "concepts_per_member": _env_int("EXO_MAX_CONCEPTS", 20),
        # Four option batches per slot per day. Avi's number, and it is a
        # readability limit as much as a cost one: generating now adds
        # rather than replaces, so an uncapped slot grows until nobody
        # can choose from it.
        "regen_per_stage_per_day": _env_int("EXO_MAX_REGEN_PER_STAGE_PER_DAY", 4),
        # The press release is the thing people came for, and iterating on it
        # is the work rather than waste. Four was the answer to a question
        # about option batches, and applying it here too meant the final
        # artifact ran out after four tries in a day. Its own number now.
        "output_per_day": _env_int("EXO_MAX_OUTPUT_PER_DAY", 12),
        "stress_per_day": _env_int("EXO_MAX_STRESS_PER_DAY", 8),
        "calls_per_member_per_day": _env_int("EXO_MAX_CALLS_PER_DAY", 120),
        "calls_site_per_day": _env_int("EXO_DAILY_SPEND_GUARD", 800),
        "timeout_seconds": _timeout(),
    }


def _since():
    from django.utils import timezone

    return timezone.now() - timezone.timedelta(days=1)


def used_today(user=None, task=None, concept=None, attribute=None):
    """Successful-or-not provider calls in the last 24 hours.

    Failures count. A retry storm against a provider that is down costs real
    money for every attempt, so a guard that only counted successes would let
    exactly the worst case through.
    """
    rows = AiCall.objects.filter(created_at__gte=_since())
    if user is not None:
        rows = rows.filter(user=user)
    if task is not None:
        rows = rows.filter(task=task)
    if concept is not None:
        rows = rows.filter(concept=concept)
    if attribute is not None:
        rows = rows.filter(attribute=attribute)
    return rows.count()


def guard_status():
    """What the site has spent today against its ceiling, for the cockpit."""
    ceiling = limits()["calls_site_per_day"]
    used = used_today()
    return {"used": used, "ceiling": ceiling, "over": used >= ceiling}


#: Each stage gets the ceiling that suits it. They are not the same kind of
#: act: another batch of options is a browse, another press release is the
#: work. One shared number meant the cheapest question set the budget for the
#: most valuable one.
def _ceiling_for(task, caps):
    return {
        "options": caps["regen_per_stage_per_day"],
        "output": caps["output_per_day"],
        "stress_test": caps["stress_per_day"],
    }.get(task)


def _guard(user, task, concept=None, attribute=None):
    """Refuse, before spending anything, if any of the three ceilings is hit.

    Each refusal names *which* ceiling. "You have reached a limit" with no
    subject is a dead end: the person cannot tell whether to wait an hour,
    start a new idea, or give up, and the first thing they ask is which limit
    they hit. The reason travels to the screen.
    """
    caps = limits()

    if used_today() >= caps["calls_site_per_day"]:
        # Site-wide: degrade, never fail. Everything that is not an AI call
        # keeps working exactly as it did.
        log.warning("exo ai: daily site guard reached, refusing %s", task)
        raise AiLimit("limit_site")

    # Per concept, and *per slot* where the stage has slots. Filling thirteen
    # slots once is the workshop working; hitting one slot thirteen times is
    # what this ceiling is for.
    ceiling = _ceiling_for(task, caps)
    if concept is not None and ceiling is not None and used_today(
        user=user, task=task, concept=concept, attribute=attribute,
    ) >= ceiling:
        raise AiLimit(f"limit_stage:{task}:{ceiling}")

    if used_today(user=user) >= caps["calls_per_member_per_day"]:
        raise AiLimit("limit_member")


def _limit_for(user, task, concept=None, attribute=None):
    """Kept as the name the stage functions call, so the guard has one entry
    point and adding a ceiling never means editing five call sites."""
    _guard(user, task, concept=concept, attribute=attribute)


def word_count(text):
    return len((text or "").split())


def trim_words(text, limit):
    """Hold a field to its word limit.

    The prompt asks for a slogan and says so twice, but a model that is asked
    for seven words will sometimes write nine, and a purpose that quietly
    grows back into a vision statement is exactly the thing this rule exists
    to prevent. Trimming here rather than rejecting keeps a good answer that
    ran slightly long, and the person can edit it before it is saved: nothing
    from this function is written to a row without them seeing it first.
    """
    words = str(text or "").strip().split()
    if len(words) <= limit:
        return " ".join(words)
    return " ".join(words[:limit])


# ---------------------------------------------------------------------------
# moderation (spec §8, G6)
# ---------------------------------------------------------------------------


def public_text_is_safe(text, user=None):
    """(ok, detail) — may this text go on a wall the whole world can read?

    Called before a release becomes `public` or `timed`, never for private
    work: what a person writes for themselves is their own business.

    **Fails open**, like the rest of the site (`app/safety.py`): if the check
    cannot run, the release is published and the failure is logged. A moderation
    outage that silently made the museum read-only during a live workshop would
    do more damage than the rare thing it would have caught, and Avi can hide
    anything from the cockpit in one click.
    """
    text = (text or "").strip()
    if not text:
        return True, ""
    if is_stub():
        return True, "stub"
    try:
        from app.ai_chat import check_moderation

        ok, result = check_moderation(text[:4000], user=user)
        if not ok:
            flagged = ", ".join((result or {}).get("categories") or {}) or "flagged"
            log.warning("exo: a release was refused publication (%s)", flagged)
            return False, flagged
        return True, ""
    except Exception:
        log.exception("exo: moderation check could not run; publishing anyway")
        return True, "unavailable"


# ---------------------------------------------------------------------------
# stage 1 — the interview
# ---------------------------------------------------------------------------


def interview_reply(concept, history, language, user=None):
    """The assistant's next turn."""
    if is_stub():
        return _stub_interview(concept, history, language)
    system = prompts.INTERVIEW_SYSTEM.format(
        language_rule=prompts.language_rule(language)
    )
    messages = [{"role": m.role, "content": m.content} for m in history]
    return _call(messages, system, "interview", user=user, concept=concept)


def settle(concept, history, language, user=None):
    """Distil the conversation into MTP / special / unique."""
    if is_stub():
        return _stub_settle(concept, history, language)
    system = prompts.SETTLE_SYSTEM.format(
        language_rule=prompts.language_rule(language)
    )
    messages = [{"role": m.role, "content": m.content} for m in history]
    messages.append({
        "role": "user",
        "content": "Summarise the idea now, as the JSON object described.",
    })
    data = _json_call(messages, system, "settle", ("mtp", "special", "unique"),
                      user=user, concept=concept)
    return {
        "mtp": trim_words(data.get("mtp"), Concept.MTP_MAX_WORDS),
        "mtp_note": trim_words(data.get("mtp_note"), Concept.MTP_NOTE_MAX_WORDS),
        "special": str(data.get("special") or "").strip(),
        "unique": str(data.get("unique") or "").strip(),
    }


# ---------------------------------------------------------------------------
# stage 3 — options per attribute
# ---------------------------------------------------------------------------


def generate_options(concept, attribute, entries, language, user=None):
    """3-4 options for one attribute, built on the user's own entries."""
    if is_stub():
        return _stub_options(concept, attribute, entries, language)
    _limit_for(user, "options", concept=concept, attribute=attribute)
    system = prompts.OPTIONS_SYSTEM.format(
        language_rule=prompts.language_rule(language)
    )
    own = "\n".join(f"- {e.text}" for e in entries) or "(they wrote nothing here)"
    user_msg = (
        f"THE IDEA: {concept.title}\n"
        f"PURPOSE (MTP), a slogan: {concept.mtp}\n"
        f"WHAT THE SLOGAN MEANS: {concept.mtp_note}\n"
        f"WHAT IS SPECIAL: {concept.special}\n"
        f"WHAT IS UNIQUE: {concept.unique}\n\n"
        # Both names. The English term is what the framework is written in and
        # what the model knows it by; the name in the reader's language is what
        # any heading the model writes should actually say. Without the second,
        # a Hebrew document comes back with "Community & Crowd" as a heading.
        f"ATTRIBUTE: {attribute.name_en} — {attribute.short_def_en}\n"
        f"ATTRIBUTE NAME IN THE OUTPUT LANGUAGE: {attribute.tr('name', language)}\n\n"
        f"THEIR OWN NOTES FOR THIS ATTRIBUTE:\n{own}"
    )
    data = _json_call([{"role": "user", "content": user_msg}], system,
                      "options", ("options",), user=user, concept=concept,
                      attribute=attribute,
                      # Options are short prose, so only the script check
                      # applies: there is no genre here to drift out of.
                      check=lambda d: quality.review_text(json.dumps(d, ensure_ascii=False)))
    out = []
    for item in (data.get("options") or [])[:4]:
        content = str((item or {}).get("content") or "").strip()
        if content:
            out.append({
                "content": content,
                "research_note": str((item or {}).get("research_note") or "").strip(),
            })
    if not out:
        raise AiError("options: the model returned none")
    return out


# ---------------------------------------------------------------------------
# stage 4 — the output, the score, the stress test
# ---------------------------------------------------------------------------


def generate_output(concept, selections, language, user=None):
    """The detailed document and the Amazon-style press release."""
    if is_stub():
        return _stub_output(concept, selections, language)
    _limit_for(user, "output", concept=concept)
    system = prompts.OUTPUT_SYSTEM.format(
        language_rule=prompts.language_rule(language)
    )
    chosen = "\n".join(
        f"- {a.tr('name', language)} ({a.name_en}): {'; '.join(texts)}"
        for a, texts in selections
    ) or "(nothing was selected)"
    user_msg = (
        f"THE IDEA: {concept.title}\n"
        f"PURPOSE (MTP), a slogan: {concept.mtp}\n"
        f"WHAT THE SLOGAN MEANS: {concept.mtp_note}\n"
        f"WHAT IS SPECIAL: {concept.special}\n"
        f"WHAT IS UNIQUE: {concept.unique}\n\n"
        f"WHAT THEY CHOSE, BY ATTRIBUTE:\n{chosen}"
    )
    # The correctness pass runs as part of generating, not as a test: these
    # are failures a model produces occasionally and unpredictably, so they
    # cannot be caught once and fixed, only caught every time.
    data = _json_call([{"role": "user", "content": user_msg}], system, "output",
                      ("headline", "body", "document_body"),
                      user=user, concept=concept,
                      check=lambda d: quality.review_feature(d, language))
    return {
        "headline": str(data.get("headline") or "").strip()[:300],
        "body": str(data.get("body") or "").strip(),
        "document_body": str(data.get("document_body") or "").strip(),
    }


def score(concept, release, language, user=None):
    """A single 0-100 number and one line saying why (spec §5.4, D4.3)."""
    if is_stub():
        return _stub_score(concept, release, language)
    system = prompts.SCORE_SYSTEM.format(
        language_rule=prompts.language_rule(language)
    )
    user_msg = (
        f"PURPOSE: {concept.mtp} — {concept.mtp_note}\n\n"
        f"THE CONCEPT DOCUMENT:\n{release.document_body}"
    )
    data = _json_call([{"role": "user", "content": user_msg}], system, "score",
                      ("score",), user=user, concept=concept)
    try:
        value = max(0, min(100, int(float(data.get("score")))))
    except (TypeError, ValueError):
        raise AiError("score: not a number")
    return {"score": value, "rationale": str(data.get("rationale") or "").strip()}


def stress_test(concept, release, language, user=None):
    """Amazon's kill question, turned on the release (spec §5.4, D4.4)."""
    if is_stub():
        return _stub_stress(concept, release, language)
    _limit_for(user, "stress_test", concept=concept)
    system = prompts.STRESS_TEST_SYSTEM.format(
        language_rule=prompts.language_rule(language)
    )
    user_msg = f"HEADLINE: {release.headline}\n\nTHE RELEASE:\n{release.body}"
    data = _json_call([{"role": "user", "content": user_msg}], system,
                      "stress_test", ("points",), user=user, concept=concept)
    points = [str(p).strip() for p in (data.get("points") or []) if str(p).strip()]
    if not points:
        raise AiError("stress test: no points returned")
    return points[:5]


# ---------------------------------------------------------------------------
# stub content — deterministic, well-formed, and labelled as such
# ---------------------------------------------------------------------------


def _he(language):
    return language == "he"


def _stub_interview(concept, history, language):
    turns = sum(1 for m in history if m.role == "user")
    title = concept.title
    if _he(language):
        script = [
            f"אז אתה רוצה לבנות {title}. תן לי לוודא שהבנתי — במשפט אחד, "
            f"מה הדבר שהוא אמור לפתור, ולמי?",
            "הבנתי. ומה לדעתך יכול להיות מיוחד בזה — משהו שהיית שם לב אליו "
            "אילו מישהו אחר היה בונה את זה?",
            "ומה יכול להיות ייחודי? כלומר משהו שאף אחד אחר לא יכול להציע כרגע.",
            "יש לי תמונה ברורה מספיק. אפשר לסכם את הרעיון ולעבור הלאה.",
        ]
    else:
        script = [
            f"So you want to build {title}. Let me check I have it — in one "
            f"sentence, what is it meant to solve, and for whom?",
            "Got it. What do you think could be special about it — something "
            "you would notice if someone else built it?",
            "And what could be unique? Something no one else can offer today.",
            "I have a clear enough picture. We can settle the idea and move on.",
        ]
    return script[min(turns, len(script) - 1)]


def _stub_settle(concept, history, language):
    """The stub obeys the same slogan rule as the real path. A stub that
    returned a paragraph would let the whole suite pass while the live app
    broke the one thing this stage is for."""
    said = " ".join(m.content for m in history if m.role == "user")[:180]
    short = " ".join(concept.title.split()[:4])
    if _he(language):
        return {
            "mtp": f"{short} לכל אחד",
            "mtp_note": f"שהרעיון של {short} יהיה זמין לכל מי שצריך אותו.",
            "special": said or "הרעיון נוגע בצורך אמיתי ומוכר.",
            "unique": "השילוב הזה עדיין לא קיים בשוק בצורה נגישה.",
        }
    return {
        "mtp": f"{short} for everyone",
        "mtp_note": f"Making {short} available to anyone who needs it.",
        "special": said or "The idea addresses a real and familiar need.",
        "unique": "This combination does not exist accessibly in the market yet.",
    }


def _stub_options(concept, attribute, entries, language):
    own = [e.text for e in entries][:2]
    name = attribute.name_he if _he(language) else attribute.name_en
    base = []
    if _he(language):
        base = [
            f"להשתמש ב{name} כדי להגיע למשתמשים שכבר מחפשים את זה, בלי לבנות "
            f"ערוץ חדש מאפס.",
            f"לפתוח את {name} לשותפים חיצוניים, כך שהצמיחה לא תלויה בגיוס פנימי.",
            f"למדוד את {name} מהיום הראשון, כדי שההחלטה הבאה תתבסס על נתון ולא על תחושה.",
        ]
    else:
        base = [
            f"Use {name} to reach people who are already looking for this, "
            f"instead of building a channel from scratch.",
            f"Open {name} to outside partners, so growth does not depend on "
            f"internal hiring.",
            f"Measure {name} from day one, so the next decision rests on a "
            f"number rather than a feeling.",
        ]
    options = []
    for text in own:
        options.append({
            "content": (f"לפתח את מה שכתבת: {text}" if _he(language)
                        else f"Develop what you wrote: {text}"),
            "research_note": ("נבנה על הרעיון שלך עצמו." if _he(language)
                              else "Built on your own note."),
        })
    for text in base:
        options.append({
            "content": text,
            "research_note": ("תוכן הדגמה — ללא מפתח AI מוגדר." if _he(language)
                              else "Demo content — no AI key configured."),
        })
    return options[:4]


def _stub_output(concept, selections, language):
    """A feature, not a launch notice.

    The stub has to demonstrate the real shape or it is worse than useless: a
    stub that produced an announcement would keep the whole suite green while
    the live app did the thing it was told to stop doing. So this one opens on
    a scene, is written a year and a half in, and quotes two people.
    """
    lines = []
    for attribute, texts in selections:
        name = attribute.name_he if _he(language) else attribute.name_en
        lines.append(f"{name}\n" + "\n".join(f"  · {t}" for t in texts))
    chosen = "\n\n".join(lines)
    if _he(language):
        headline = f"שנה וחצי אחרי: מה קרה ל{concept.title}"
        body = (
            "בשתיים בצהריים, ביום שלישי רגיל, התור מגיע עד הפינה. אף אחד "
            "לא נראה מופתע.\n\n"
            f"שנה וחצי אחרי שנפתח, {concept.title} כבר לא מנסה להסביר את "
            f"עצמו. {concept.mtp}\n\n"
            "\"בהתחלה חשבנו שזה יעבוד אחרת לגמרי\", אומרת הבעלים וצוחקת. "
            "\"הלקוחות לימדו אותנו מה זה באמת.\"\n\n"
            "בתיה פקמן מגיעה לכאן שלוש פעמים בשבוע. \"בשלב מסוים זה פשוט "
            "הפך למקום שהולכים אליו\", היא אומרת.\n\n"
            f"מה שמחזיק את זה: {concept.special}\n\n"
            "— תוכן הדגמה, נוצר ללא מפתח AI."
        )
        document = (
            f"המטרה\n{concept.mtp}\n{concept.mtp_note}\n\n"
            f"מה מיוחד\n{concept.special}\n\n"
            f"מה ייחודי\n{concept.unique}\n\n"
            f"מה נבחר\n{chosen}\n\n"
            "— תוכן הדגמה, נוצר ללא מפתח AI."
        )
    else:
        headline = f"Eighteen months on: what became of {concept.title}"
        body = (
            "At two in the afternoon on an ordinary Tuesday, the queue reaches "
            "the corner. Nobody looks surprised.\n\n"
            f"A year and a half after opening, {concept.title} has stopped "
            f"explaining itself. {concept.mtp}\n\n"
            "\"We thought it would work completely differently,\" the owner "
            "says, laughing. \"The customers taught us what this actually "
            "was.\"\n\n"
            "Batya Pekman comes three times a week. \"At some point it just "
            "became the place you go,\" she says.\n\n"
            f"What holds it together: {concept.special}\n\n"
            "— Demo content, generated with no AI key."
        )
        document = (
            f"Purpose\n{concept.mtp}\n{concept.mtp_note}\n\n"
            f"What is special\n{concept.special}\n\n"
            f"What is unique\n{concept.unique}\n\n"
            f"What was chosen\n{chosen}\n\n"
            "— Demo content, generated with no AI key."
        )
    return {"headline": headline, "body": body, "document_body": document}


def _stub_score(concept, release, language):
    # Deterministic and defensible: more chosen material, more leverage shown.
    picked = release.concept.options.filter(is_selected=True).count()
    value = max(30, min(88, 38 + picked * 4))
    rationale = ("ציון הדגמה, מבוסס על כמות הבחירות." if _he(language)
                 else "Demo score, based on how much was selected.")
    return {"score": value, "rationale": rationale}


def _stub_stress(concept, release, language):
    if _he(language):
        return [
            "הכותרת אומרת מה זה, אבל לא למי — לקוח לא יידע אם זה בשבילו.",
            "ההבטחה המרכזית עדיין כללית מדי; חסר מספר או זמן קונקרטי.",
            "הציטוט של הלקוחה הוא החלק המשכנע ביותר — שווה להרחיב אותו.",
            "לא מוסבר איך זה עובד בפועל ביום הראשון.",
            "— תוכן הדגמה, נוצר ללא מפתח AI.",
        ]
    return [
        "The headline says what it is but not who it is for — a customer "
        "cannot tell if this is for them.",
        "The central promise is still generic; it needs a number or a timeframe.",
        "The customer quote is the most convincing part — it deserves more room.",
        "It never explains how this actually works on day one.",
        "— Demo content, generated with no AI key.",
    ]
