"""Writing a challenge with AI (spec 14, B.6).

Three kinds of turn, one conversation: `chat` (talk about the idea and
rewrite the card), `build` (write the whole challenge as a draft), `edit`
(propose changes to the built draft, applied only on the teacher's click).

The model always answers JSON. Without an OpenAI key (a developer's PC,
every test) `_call` answers from a fixed stub through the same parser, so
every screen and every path runs without a bill. Tests replace `_call` to
feed the parser what a real model might say.

Costs are logged on each answer (IdeaMessage.cost_usd) and capped in our
own code, per creator per day and for the app per month (methodology 24).
"""

import base64
import io
import json
import logging
import os
import textwrap
import threading
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import close_old_connections, transaction
from django.db.models import Sum
from django.utils import timezone

from . import text as text_tools
from .models import (
    Experience,
    FinalLock,
    Hint,
    Idea,
    IdeaMessage,
    Material,
    Station,
    StationMaterial,
    Subject,
)

log = logging.getLogger(__name__)

# $ per 1M tokens: input, cached input, output (the site's measured table, 2026-10-28).
PRICES = {
    "gpt-6.1-terra": (Decimal("1.00"), Decimal("0.05"), Decimal("5.00")),
    "gpt-6.1-sol": (Decimal("2.00"), Decimal("0.10"), Decimal("10.00")),
    "gpt-6-luna": (Decimal("0.10"), Decimal("0.01"), Decimal("0.50")),
}
MAX_PICTURE_SIDE = 1600
STALE = timedelta(minutes=6)


def chat_model():
    return os.environ.get("BREAKOUT_CHAT_MODEL", "gpt-6.1-terra")


def build_model():
    return os.environ.get("BREAKOUT_BUILD_MODEL", "gpt-6.1-sol")


def daily_cap():
    return Decimal(os.environ.get("BREAKOUT_AI_DAILY_USD", "2"))


def monthly_cap():
    return Decimal(os.environ.get("BREAKOUT_AI_MONTHLY_USD", "40"))


def stub_mode():
    return not (getattr(settings, "OPENAI_API_KEY", "") or "")


def cost(model, tokens_in, tokens_cached, tokens_out):
    if model not in PRICES:
        return Decimal("0")
    pin, pcache, pout = PRICES[model]
    return ((Decimal(tokens_in - tokens_cached) * pin + Decimal(tokens_cached) * pcache
             + Decimal(tokens_out) * pout) / Decimal(1_000_000)).quantize(Decimal("0.00001"))


# ------------------------------------------------------------------ caps


def spent_today(user):
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return IdeaMessage.objects.filter(idea__author=user, created_at__gte=start).aggregate(s=Sum("cost_usd"))["s"] or Decimal("0")


def spent_this_month(user=None):
    start = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = IdeaMessage.objects.filter(created_at__gte=start)
    if user is not None:
        rows = rows.filter(idea__author=user)
    return rows.aggregate(s=Sum("cost_usd"))["s"] or Decimal("0")


def over_cap(user):
    """A sentence for the teacher when a cap is reached, else ''."""
    if spent_this_month() >= monthly_cap():
        return "הגענו לתקרת השימוש החודשית של האתר ב-AI. אפשר להמשיך לערוך בטפסים; השיחה תיפתח שוב בחודש הבא."
    if spent_today(user) >= daily_cap():
        return "הגעתם לתקרת השימוש היומית ב-AI. אפשר להמשיך לערוך בטפסים, והשיחה תיפתח שוב מחר."
    return ""


# --------------------------------------------------------------- prompts

ABOUT = """
    You help an Israeli teacher design a paper escape-room challenge ("אתגר") for a group of
    children or teenagers. The children never use a screen: everything is paper, scissors, glue,
    tape and office supplies. Groups of 4 to 6 move through stations; each station is a puzzle
    on paper (decode, logic, find the error, order, sort, cipher, cut-fold-assemble), and each
    solved station gives one piece of a final code that opens a paper lock at the end. Puzzles
    should be hands-on where possible (cut, fold, assemble), fair, and solvable at the agreed grade.
    Speak Hebrew to the teacher, address them in the plural (אתם), plainly and warmly, without
    emojis. The thing is called "אתגר" (masculine). Stay on designing classroom challenges.
"""

CHAT_SYSTEM = textwrap.dedent(ABOUT + """
    Now you talk with the teacher about their idea until it is clear. Offer concrete proposals
    (a story, station ideas, how the code is built), ask at most two questions at a time, and
    read any sketch or photo they attach as inspiration. Keep everything agreed so far.

    Answer JSON only, no fences:
      {"message": "what you say to the teacher, in Hebrew",
       "brief": {"title": "a working title", "theme": "the subject and the idea in one line",
                 "audience_from": 7, "audience_to": 9, "station_count": 4, "duration_minutes": 45,
                 "story_line": "the opening story in one or two sentences",
                 "stations_plan": ["one line per station: what the group does and what it yields"],
                 "open_questions": ["what is still undecided"]},
       "ready": true when the brief is complete enough to build}
    Grades are numbers 1 to 12. Rewrite the whole brief every turn.
""").strip()

BUILD_SYSTEM = textwrap.dedent(ABOUT + """
    Now write the whole challenge from the agreed brief and the conversation.

    Answer JSON only, no fences:
      {"title": "...", "tagline": "one line for the library card", "story": "what the teacher reads
       to open the challenge", "teacher_notes": "how to set up the room and run it",
       "audience_from": 7, "audience_to": 9, "group_size_min": 4, "group_size_max": 6,
       "duration_minutes": 45, "prep_minutes": 30, "difficulty": "easy|medium|hard",
       "subjects": ["slugs from the list below"],
       "stations": [{"name": "...", "story_text": "what the group reads at the station",
                     "puzzle_text": "the puzzle exactly as printed for the group",
                     "solution": "the exact answer", "solution_explained": "for the teacher: how one gets there",
                     "contribution": "this station's piece of the final code, exactly",
                     "mechanic": "decode|logic|find_the_error|order|sort|cipher|assemble|other",
                     "estimated_minutes": 8, "setup_notes": "what the teacher prepares, physically",
                     "hints": ["gentle", "clearer", "nearly the answer"],
                     "materials": [{"name": "exact name from the catalogue", "quantity": 1, "note": "..."}]}],
       "lock": {"description": "the physical lock", "code_rule": "how the pieces make the code",
                "final_code": "the code", "final_message": "what the group finds when it opens",
                "setup_notes": "..."}}

    Rules: exactly the agreed number of stations. Every station has a puzzle and an exact
    solution. The final code is the stations' contributions in station order, joined; say so in
    code_rule. Two or three hints per station, from gentle to nearly the answer. Materials only
    from this catalogue, by exact name: {materials}. Subjects only from: {subjects}.
""").strip()

EDIT_SYSTEM = textwrap.dedent(ABOUT + """
    The challenge is built; the teacher now asks for changes. The current challenge is below as
    JSON, stations numbered from 1. Propose the changes that do what they ask; nothing changes
    until the teacher applies your proposal. If they only ask a question, answer with no changes.
    If a change breaks the chain from the stations' pieces to the final code, change the lock too.

    Answer JSON only, no fences:
      {"message": "what you say, in Hebrew",
       "changes": [{"target": "experience", "field": "title|tagline|story|teacher_notes", "value": "..."},
                   {"target": "station", "station": 2, "field": "name|story_text|puzzle_text|solution|solution_explained|contribution|setup_notes", "value": "..."},
                   {"target": "hints", "station": 2, "value": ["...", "..."]},
                   {"target": "lock", "field": "description|code_rule|final_code|final_message|setup_notes", "value": "..."}]}

    The challenge now:
    {current}
""").strip()

EXPERIENCE_FIELDS = {"title": True, "tagline": True, "story": False, "teacher_notes": False}  # name: one line
STATION_FIELDS = {"name": True, "story_text": False, "puzzle_text": False, "solution": False,
                  "solution_explained": False, "contribution": True, "setup_notes": False}
LOCK_FIELDS = {"description": False, "code_rule": False, "final_code": True, "final_message": False, "setup_notes": False}
FIELD_LABELS = {
    "title": "שם", "tagline": "משפט לכרטיס", "story": "סיפור הפתיחה", "teacher_notes": "הערות למורה",
    "name": "שם התחנה", "story_text": "הסיפור בתחנה", "puzzle_text": "החידה", "solution": "הפתרון",
    "solution_explained": "הסבר הפתרון", "contribution": "החלק בקוד", "setup_notes": "הכנה",
    "description": "המנעול", "code_rule": "איך נבנה הקוד", "final_code": "הקוד", "final_message": "מה מוצאים בפנים",
}


def build_system():
    materials = ", ".join(Material.objects.filter(is_active=True).values_list("name", flat=True)) or "(none)"
    subjects = ", ".join(f"{s} ({n})" for s, n in Subject.objects.values_list("slug", "name")) or "(none)"
    return BUILD_SYSTEM.replace("{materials}", materials).replace("{subjects}", subjects)


def current_json(exp):
    lock = FinalLock.objects.filter(experience=exp).first()
    return json.dumps({
        "title": exp.title, "tagline": exp.tagline, "story": exp.story, "teacher_notes": exp.teacher_notes,
        "stations": [{"n": i, "name": s.name, "story_text": s.story_text, "puzzle_text": s.puzzle_text,
                      "solution": s.solution, "solution_explained": s.solution_explained,
                      "contribution": s.contribution, "setup_notes": s.setup_notes,
                      "hints": [h.text for h in s.hints.all()]}
                     for i, s in enumerate(exp.stations.all(), start=1)],
        "lock": {f: getattr(lock, f) for f in LOCK_FIELDS} if lock else {},
    }, ensure_ascii=False)


def brief_text(idea):
    return json.dumps({
        "title": idea.title, "theme": idea.theme, "audience_from": idea.audience_from, "audience_to": idea.audience_to,
        "station_count": idea.station_count, "duration_minutes": idea.duration_minutes, "story_line": idea.story_line,
        "stations_plan": idea.plan_lines, "open_questions": idea.open_lines,
    }, ensure_ascii=False)


# ------------------------------------------------------------- history


def _picture_part(msg, detail):
    with msg.picture.open("rb") as fh:
        data = base64.b64encode(fh.read()).decode()
    return {"type": "input_image", "image_url": f"data:image/jpeg;base64,{data}", "detail": detail}


def history(idea, system, upto=None, pictures=3):
    """The conversation as model input: every finished message, the newest
    pictures at full detail and older ones at low detail."""
    msgs = [m for m in idea.messages.all() if m.state == IdeaMessage.DONE and (upto is None or m.pk < upto.pk)]
    with_pics = [m.pk for m in msgs if m.picture]
    recent = set(with_pics[-pictures:])
    items = [{"role": "system", "content": system}]
    for m in msgs:
        if m.role == IdeaMessage.TEACHER:
            parts = [{"type": "input_text", "text": m.text or "(ראו את התמונה)"}]
            if m.picture:
                try:
                    parts.append(_picture_part(m, "auto" if m.pk in recent else "low"))
                except OSError:
                    log.warning("breakout idea picture %s is missing", m.pk)
            items.append({"role": "user", "content": parts})
        elif m.text:
            items.append({"role": "assistant", "content": m.text})
    return items


# --------------------------------------------------------------- calls

_client = None


def _openai():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=180)
    return _client


def _call(kind, model, items):
    """One model call: (text, usage). Stub mode answers without a call."""
    if stub_mode():
        return _stub(kind, items), {"in": 0, "cached": 0, "out": 0}
    r = _openai().responses.create(model=model, input=items)
    u = r.usage
    cached = getattr(getattr(u, "input_tokens_details", None), "cached_tokens", 0) or 0
    return r.output_text or "", {"in": u.input_tokens, "cached": cached, "out": u.output_tokens}


def _last_teacher_text(items):
    for item in reversed(items):
        if item["role"] == "user":
            content = item["content"]
            return content[0]["text"] if isinstance(content, list) else str(content)
    return ""


def _stub(kind, items):
    said = _last_teacher_text(items)
    if kind == IdeaMessage.CHAT:
        return json.dumps({
            "message": "מצב הדגמה, בלי מודל בשרת הזה: זו תשובה קבועה. הנה הצעה ראשונה, ותגידו מה לשנות.",
            "brief": {"title": "מסע בזמן", "theme": said[:120] or "מסע בזמן בין שלוש תקופות",
                      "audience_from": 6, "audience_to": 8, "station_count": 3, "duration_minutes": 45,
                      "story_line": "מכונת הזמן נתקעה, וכל תקופה מחזיקה ספרה אחת מהקוד שמחזיר אותה לפעול.",
                      "stations_plan": ["מצרים העתיקה: פענוח כתב חרטומים, נותן 4",
                                        "יוון: חידת היגיון של פילוסופים, נותן 2",
                                        "ימי הביניים: גזירה והרכבה של מגן, נותן 7"],
                      "open_questions": ["כמה זמן יש לכם בשיעור?"]},
            "ready": True,
        }, ensure_ascii=False)
    if kind == IdeaMessage.BUILD:
        names = list(Material.objects.filter(is_active=True).values_list("name", flat=True)[:2])
        materials = [{"name": n, "quantity": 1, "note": ""} for n in names]

        def station(name, piece, mechanic):
            return {"name": name, "story_text": f"הגעתם ל{name}.", "puzzle_text": f"החידה של {name}: מה הספרה?",
                    "solution": piece, "solution_explained": f"התשובה היא {piece}.", "contribution": piece,
                    "mechanic": mechanic, "estimated_minutes": 10, "setup_notes": "מדפיסים את דף התחנה.",
                    "hints": ["הסתכלו שוב על הדף.", f"הספרה קטנה מ-{int(piece) + 1}."], "materials": materials}

        return json.dumps({
            "title": "מסע בזמן", "tagline": "מכונת הזמן נתקעה, ושלוש תקופות מחזיקות את הקוד.",
            "story": "מכונת הזמן של בית הספר נתקעה. כדי להחזיר אותה צריך שלוש ספרות.",
            "teacher_notes": "מניחים כל תחנה בפינה אחרת של החדר.",
            "audience_from": 6, "audience_to": 8, "group_size_min": 4, "group_size_max": 6,
            "duration_minutes": 45, "prep_minutes": 20, "difficulty": "medium", "subjects": [],
            "stations": [station("מצרים העתיקה", "4", "decode"), station("יוון", "2", "logic"),
                         station("ימי הביניים", "7", "assemble")],
            "lock": {"description": "מעטפה סגורה במנעול נייר", "code_rule": "הספרות של התחנות לפי הסדר",
                     "final_code": "427", "final_message": "המכונה חוזרת לפעול!", "setup_notes": ""},
        }, ensure_ascii=False)
    return json.dumps({
        "message": "מצב הדגמה: הנה הצעה לשינוי אחד, אפשר להחיל או לוותר.",
        "changes": [{"target": "experience", "field": "tagline", "value": ("גרסה מעודכנת: " + said)[:150]}],
    }, ensure_ascii=False)


def parse(raw):
    try:
        data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _clip(value, n, one_line=False):
    return text_tools.tidy(str(value or ""), one_line=one_line)[:n]


def _grade(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= 12 else None


def _small(value, lo, hi):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if lo <= n <= hi else None


# ---------------------------------------------------------------- turns


def say(idea, teacher_text, picture_bytes=None):
    """The teacher's message, and the AI's answer started (inline in stub
    mode, in a thread otherwise). Returns the AI message, or None when a cap
    stops it (the reason is then an AI message too)."""
    kind = IdeaMessage.EDIT if idea.experience_id else IdeaMessage.CHAT
    msg = IdeaMessage.objects.create(idea=idea, role=IdeaMessage.TEACHER, kind=kind, text=teacher_text)
    if picture_bytes:
        from django.core.files.base import ContentFile

        msg.picture.save("sketch.jpg", ContentFile(picture_bytes), save=True)
    Idea.objects.filter(pk=idea.pk).update(updated_at=timezone.now())
    return _answer(idea, kind)


def build(idea):
    return _answer(idea, IdeaMessage.BUILD)


def _answer(idea, kind):
    stop = over_cap(idea.author)
    if stop:
        IdeaMessage.objects.create(idea=idea, role=IdeaMessage.AI, kind=kind, text=stop, state=IdeaMessage.DONE)
        return None
    answer = IdeaMessage.objects.create(idea=idea, role=IdeaMessage.AI, kind=kind, state=IdeaMessage.THINKING,
                                        model=build_model() if kind == IdeaMessage.BUILD else chat_model())
    if stub_mode() or getattr(settings, "BREAKOUT_AI_INLINE", False):
        run(answer.pk)
        idea.refresh_from_db()  # run() wrote through its own copy; the caller's must not go stale
    else:
        threading.Thread(target=_thread, args=(answer.pk,), daemon=True, name=f"breakout-idea-{answer.pk}").start()
    return answer


def _thread(pk):
    try:
        run(pk)
    finally:
        close_old_connections()


def busy(idea):
    """True while an answer is being written. A stale one (a restart killed
    its thread) is marked failed, so the conversation never stays stuck."""
    thinking = idea.messages.filter(state=IdeaMessage.THINKING)
    thinking.filter(created_at__lt=timezone.now() - STALE).update(
        state=IdeaMessage.FAILED, text="התשובה לא הגיעה. נסו לשלוח שוב.")
    return thinking.exists()


def _log_usage(msg, model, usage):
    msg.model = "stub" if stub_mode() else model
    msg.tokens_in += usage["in"]
    msg.tokens_cached += usage["cached"]
    msg.tokens_out += usage["out"]
    msg.cost_usd += cost(model, usage["in"], usage["cached"], usage["out"])


def run(pk):
    msg = IdeaMessage.objects.select_related("idea", "idea__author").get(pk=pk)
    idea = msg.idea
    try:
        if msg.kind == IdeaMessage.CHAT:
            _chat_turn(msg, idea)
        elif msg.kind == IdeaMessage.BUILD:
            _build_turn(msg, idea)
        else:
            _edit_turn(msg, idea)
        msg.state = IdeaMessage.DONE
    except Exception:
        log.exception("breakout idea turn %s failed", pk)
        msg.state = IdeaMessage.FAILED
        msg.text = msg.text or "משהו השתבש בדרך. נסו לשלוח שוב."
    msg.save()
    Idea.objects.filter(pk=idea.pk).update(updated_at=timezone.now())


def _chat_turn(msg, idea):
    raw, usage = _call(IdeaMessage.CHAT, msg.model, history(idea, CHAT_SYSTEM + "\n\nThe card so far: " + brief_text(idea), upto=msg))
    _log_usage(msg, msg.model, usage)
    data = parse(raw)
    if data is None:
        msg.text = _clip(raw, 4000) or "לא הבנתי את עצמי. נסו לנסח שוב."
        return
    msg.text = _clip(data.get("message"), 4000) or "..."
    b = data.get("brief") if isinstance(data.get("brief"), dict) else {}
    if b:
        idea.title = _clip(b.get("title"), 120, True) or idea.title
        idea.theme = _clip(b.get("theme"), 300, True) or idea.theme
        idea.audience_from = _grade(b.get("audience_from")) or idea.audience_from
        idea.audience_to = _grade(b.get("audience_to")) or idea.audience_to
        idea.station_count = _small(b.get("station_count"), 1, 12) or idea.station_count
        idea.duration_minutes = _small(b.get("duration_minutes"), 10, 240) or idea.duration_minutes
        idea.story_line = _clip(b.get("story_line"), 1000) or idea.story_line
        plan = b.get("stations_plan")
        if isinstance(plan, list):
            idea.stations_plan = "\n".join(_clip(p, 300, True) for p in plan if str(p).strip())[:4000]
        questions = b.get("open_questions")
        if isinstance(questions, list):
            idea.open_questions = "\n".join(_clip(q, 300, True) for q in questions if str(q).strip())[:2000]
        idea.save()


def findings(data, idea):
    """What cannot be right in a built challenge: the model gets these back once."""
    out = []
    stations = data.get("stations") if isinstance(data.get("stations"), list) else []
    stations = [s for s in stations if isinstance(s, dict)]
    if not stations:
        return ["There are no stations."]
    if idea.station_count and len(stations) != idea.station_count:
        out.append(f"The brief agreed on {idea.station_count} stations; you wrote {len(stations)}.")
    for i, s in enumerate(stations, start=1):
        if not str(s.get("puzzle_text") or "").strip() or not str(s.get("solution") or "").strip():
            out.append(f"Station {i} has no puzzle or no solution.")
    lock = data.get("lock") if isinstance(data.get("lock"), dict) else {}
    code = "".join(str(lock.get("final_code") or "").split())
    pieces = "".join("".join(str(s.get("contribution") or "").split()) for s in stations)
    if not code:
        out.append("The lock has no final code.")
    elif pieces != code:
        out.append(f"The stations' contributions joined in order give {pieces!r}, but the final code is {code!r}.")
    return out


def _build_turn(msg, idea):
    items = history(idea, build_system(), upto=msg)
    items.append({"role": "user", "content": [{"type": "input_text", "text": "Build the challenge now. The agreed brief: " + brief_text(idea)}]})
    raw, usage = _call(IdeaMessage.BUILD, msg.model, items)
    _log_usage(msg, msg.model, usage)
    data = parse(raw)
    found = findings(data, idea) if data else ["The answer was not JSON."]
    if found:
        items += [{"role": "assistant", "content": raw},
                  {"role": "user", "content": [{"type": "input_text", "text": "Fix these and answer the whole JSON again:\n- " + "\n- ".join(found)}]}]
        raw2, usage = _call(IdeaMessage.BUILD, msg.model, items)
        _log_usage(msg, msg.model, usage)
        data2 = parse(raw2)
        if data2 is not None:
            data, found = data2, findings(data2, idea)
    if data is None or not isinstance(data.get("stations"), list) or not data["stations"]:
        msg.text = "לא הצלחתי לבנות את האתגר הפעם. נסו שוב, ואם זה חוזר, ספרו לי עוד על התחנות."
        return
    exp, missing = _save_experience(idea, data)
    lines = [f"האתגר \"{exp.title}\" נבנה כטיוטה עם {exp.stations.count()} תחנות. רק אתם רואים אותו עד שתפרסמו.",
             "אפשר לערוך בטפסים, או לבקש כאן שינויים ואני אציע אותם."]
    if missing:
        lines.append("חומרים שלא מצאתי בקטלוג, ולכן לא הוספתי: " + ", ".join(missing) + ". אפשר לבקש אותם מהעורך.")
    if found:
        lines.append("שימו לב, נשאר משהו שלא הצלחתי ליישר: " + _hebrew_findings(found))
    msg.text = "\n".join(lines)


def _hebrew_findings(found):
    out = []
    for f in found:
        if "contributions joined" in f:
            out.append("הקוד הסופי לא יוצא בדיוק מהחלקים של התחנות")
        elif "no puzzle" in f:
            out.append("לתחנה חסרים חידה או פתרון")
        elif "agreed on" in f:
            out.append("מספר התחנות שונה ממה שסיכמנו")
        elif "no final code" in f:
            out.append("למנעול אין קוד")
    return "; ".join(dict.fromkeys(out)) + ". כדאי לבדוק בעורך."


@transaction.atomic
def _save_experience(idea, data):
    title = _clip(data.get("title"), 120, True) or idea.title or "אתגר חדש"
    difficulty = data.get("difficulty") if data.get("difficulty") in dict(Experience.DIFFICULTIES) else Experience.MEDIUM
    a_from = _grade(data.get("audience_from")) or idea.audience_from or 7
    a_to = _grade(data.get("audience_to")) or idea.audience_to or a_from
    exp = Experience.objects.create(
        author=idea.author, status=Experience.DRAFT, title=title,
        slug=text_tools.slug_for(title, lambda s: Experience.objects.filter(slug=s).exists()),
        tagline=_clip(data.get("tagline"), 160, True), story=_clip(data.get("story"), 6000),
        teacher_notes=_clip(data.get("teacher_notes"), 6000),
        audience_from=min(a_from, a_to), audience_to=max(a_from, a_to),
        group_size_min=_small(data.get("group_size_min"), 1, 40) or 4,
        group_size_max=_small(data.get("group_size_max"), 1, 40) or 6,
        duration_minutes=_small(data.get("duration_minutes"), 10, 240) or idea.duration_minutes or 45,
        prep_minutes=_small(data.get("prep_minutes"), 0, 600) or 30, difficulty=difficulty,
    )
    slugs = [s for s in (data.get("subjects") or []) if isinstance(s, str)]
    exp.subjects.set(Subject.objects.filter(slug__in=slugs))
    mechanics = dict(Station.MECHANICS)
    catalogue = {m.name: m for m in Material.objects.filter(is_active=True)}
    missing = []
    for order, s in enumerate([s for s in data["stations"] if isinstance(s, dict)], start=1):
        station = Station.objects.create(
            experience=exp, order=order, name=_clip(s.get("name"), 80, True) or f"תחנה {order}",
            story_text=_clip(s.get("story_text"), 4000), puzzle_text=_clip(s.get("puzzle_text"), 6000),
            solution=_clip(s.get("solution"), 2000), solution_explained=_clip(s.get("solution_explained"), 4000),
            contribution=_clip(s.get("contribution"), 200, True),
            mechanic=s.get("mechanic") if s.get("mechanic") in mechanics else "other",
            estimated_minutes=_small(s.get("estimated_minutes"), 1, 120) or 8, setup_notes=_clip(s.get("setup_notes"), 4000),
        )
        for i, h in enumerate([h for h in (s.get("hints") or []) if str(h).strip()][:5], start=1):
            Hint.objects.create(station=station, order=i, text=_clip(h, 1000))
        for use in s.get("materials") or []:
            if not isinstance(use, dict):
                continue
            name = _clip(use.get("name"), 80, True)
            material = catalogue.get(name)
            if material is None:
                if name and name not in missing:
                    missing.append(name)
                continue
            try:
                quantity = max(Decimal("0.25"), min(Decimal("999"), Decimal(str(use.get("quantity", 1)))))
            except Exception:
                quantity = Decimal("1")
            StationMaterial.objects.create(station=station, material=material, quantity=quantity, note=_clip(use.get("note"), 200, True))
    lock = data.get("lock") if isinstance(data.get("lock"), dict) else {}
    FinalLock.objects.create(experience=exp, **{f: _clip(lock.get(f), 200 if one else 4000, one) for f, one in LOCK_FIELDS.items()})
    idea.experience = exp
    idea.state = Idea.BUILT
    idea.title = title
    idea.save()
    return exp, missing


def _edit_turn(msg, idea):
    exp = idea.experience
    system = EDIT_SYSTEM.replace("{current}", current_json(exp))
    raw, usage = _call(IdeaMessage.EDIT, msg.model, history(idea, system, upto=msg))
    _log_usage(msg, msg.model, usage)
    data = parse(raw)
    if data is None:
        msg.text = _clip(raw, 4000) or "לא הבנתי את עצמי. נסו לנסח שוב."
        return
    msg.text = _clip(data.get("message"), 4000) or "..."
    changes = [c for c in (clean_change(c, exp) for c in (data.get("changes") or [])) if c]
    if changes:
        msg.changes = changes
        msg.changes_state = IdeaMessage.PENDING


def clean_change(c, exp):
    """A proposed change the app knows how to apply, with its label and
    the value it replaces; anything else is dropped."""
    if not isinstance(c, dict):
        return None
    target, n = c.get("target"), _small(c.get("station"), 1, 50)
    stations = list(exp.stations.all())
    station = stations[n - 1] if n and n <= len(stations) else None
    if target == "experience" and c.get("field") in EXPERIENCE_FIELDS:
        f = c["field"]
        return {"target": target, "field": f, "label": FIELD_LABELS[f], "before": getattr(exp, f),
                "value": _clip(c.get("value"), 160 if f == "tagline" else 6000, EXPERIENCE_FIELDS[f])}
    if target == "station" and station and c.get("field") in STATION_FIELDS:
        f = c["field"]
        return {"target": target, "station": n, "field": f, "label": f"תחנה {n}: {FIELD_LABELS[f]}",
                "before": getattr(station, f), "value": _clip(c.get("value"), 200 if STATION_FIELDS[f] else 6000, STATION_FIELDS[f])}
    if target == "hints" and station and isinstance(c.get("value"), list):
        return {"target": target, "station": n, "label": f"תחנה {n}: רמזים",
                "before": "\n".join(h.text for h in station.hints.all()),
                "value": [_clip(h, 1000) for h in c["value"] if str(h).strip()][:5]}
    if target == "lock" and c.get("field") in LOCK_FIELDS:
        f = c["field"]
        lock = FinalLock.objects.filter(experience=exp).first()
        return {"target": target, "field": f, "label": f"המנעול: {FIELD_LABELS[f]}",
                "before": getattr(lock, f) if lock else "", "value": _clip(c.get("value"), 200 if LOCK_FIELDS[f] else 4000, LOCK_FIELDS[f])}
    return None


@transaction.atomic
def apply_changes(msg):
    """The teacher's click: every proposed change written to the rows, and a
    published challenge's version bumped once (edit_views.touch)."""
    from .edit_views import touch

    exp = msg.idea.experience
    stations = list(exp.stations.all())
    for c in msg.changes or []:
        c = clean_change(c, exp)  # the rows may have moved since the proposal
        if c is None:
            continue
        if c["target"] == "experience":
            setattr(exp, c["field"], c["value"])
            exp.save(update_fields=[c["field"]])
        elif c["target"] == "station":
            s = stations[c["station"] - 1]
            setattr(s, c["field"], c["value"])
            s.save(update_fields=[c["field"]])
        elif c["target"] == "hints":
            s = stations[c["station"] - 1]
            s.hints.all().delete()
            for i, h in enumerate(c["value"], start=1):
                Hint.objects.create(station=s, order=i, text=h)
        elif c["target"] == "lock":
            lock, _made = FinalLock.objects.get_or_create(experience=exp)
            setattr(lock, c["field"], c["value"])
            lock.save(update_fields=[c["field"]])
    msg.changes_state = IdeaMessage.APPLIED
    msg.save(update_fields=["changes_state"])
    touch(exp)


def decline_changes(msg):
    msg.changes_state = IdeaMessage.DECLINED
    msg.save(update_fields=["changes_state"])


# -------------------------------------------------------------- pictures


def prepared_picture(uploaded):
    """(jpeg_bytes, error): checked like any upload, turned upright,
    downscaled, and passed through the site's image moderation."""
    from django import forms
    from PIL import Image

    from .edit_forms import checked_image

    try:
        data, _ext, _w, _h = checked_image(uploaded)
    except forms.ValidationError as exc:
        return None, " ".join(exc.messages)
    img = Image.open(io.BytesIO(data))
    img.thumbnail((MAX_PICTURE_SIDE, MAX_PICTURE_SIDE))
    out = io.BytesIO()
    img.convert("RGB").save(out, "JPEG", quality=85)
    jpeg = out.getvalue()
    img.close()
    from app.safety import image_is_safe

    ok, _reason = image_is_safe(io.BytesIO(jpeg), label="breakout-idea")
    if not ok:
        return None, "התמונה לא עברה את בדיקת התוכן של האתר."
    return jpeg, ""
