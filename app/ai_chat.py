"""
AI Chat service layer - OpenAI integration (STUBBED for testing).

All OpenAI API calls go through this module. When OPENAI_API_KEY is empty,
calls return stub responses. No money is spent.
"""

import logging

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from .models import (
    ChatMessage,
    ChatSession,
    ModerationLog,
    SystemPrompt,
    UsageLog,
)

logger = logging.getLogger(__name__)


def _is_stub_mode():
    """Return True if no real API key is configured."""
    return not settings.OPENAI_API_KEY


def call_openai(messages, model=None, system_prompt=""):
    """
    Call OpenAI chat completions API (or return stub).
    Returns dict: {content, prompt_tokens, completion_tokens, model}
    """
    model = model or settings.OPENAI_DEFAULT_MODEL

    if _is_stub_mode():
        logger.info("STUB: Would call OpenAI %s with %d messages", model, len(messages))
        return {
            "content": "[AI Chat is in stub mode. Set OPENAI_API_KEY to enable.]",
            "prompt_tokens": 10,
            "completion_tokens": 15,
            "model": model,
        }

    # Real API call
    try:
        import openai

        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        api_messages = []
        if system_prompt:
            api_messages.append({"role": "system", "content": system_prompt})
        api_messages.extend(messages)

        response = client.chat.completions.create(
            model=model,
            messages=api_messages,
            max_tokens=2048,
        )
        choice = response.choices[0]
        usage = response.usage
        return {
            "content": choice.message.content,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "model": model,
        }
    except Exception as e:
        logger.error("OpenAI API error: %s", e)
        return {
            "content": "Sorry, I encountered an error. Please try again.",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "model": model,
        }


def _call_moderation_api(text):
    """
    Call OpenAI moderation endpoint (or return stub).
    Returns dict: {flagged: bool, categories: dict}
    """
    if _is_stub_mode():
        logger.info("STUB: Would call OpenAI moderation API")
        return {"flagged": False, "categories": {}}

    try:
        import openai

        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.moderations.create(input=text)
        result = response.results[0]
        return {
            "flagged": result.flagged,
            "categories": {k: v for k, v in result.categories.model_dump().items() if v},
        }
    except Exception as e:
        logger.error("Moderation API error: %s", e)
        return {"flagged": False, "categories": {}}


def check_moderation(text, user=None):
    """
    Check text against moderation API. Logs if flagged.
    Returns (is_safe, detail_dict).
    """
    result = _call_moderation_api(text)
    if result["flagged"]:
        ModerationLog.objects.create(
            user=user,
            content=text[:500],
            flagged_categories=result["categories"],
        )
        return False, result
    return True, result


def _call_image_moderation_api(image_bytes, mime="image/jpeg"):
    """
    Run an image through OpenAI's omni-moderation endpoint (FREE, same as text).
    `omni-moderation-latest` accepts image input and scores the same safety
    categories (sexual, violence, hate, harassment, self-harm, illicit).
    Returns dict: {flagged: bool, categories: dict}. Fails open.
    """
    if _is_stub_mode():
        logger.info("STUB: Would call OpenAI image moderation API")
        return {"flagged": False, "categories": {}}

    try:
        import base64

        import openai

        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        b64 = base64.b64encode(image_bytes).decode("ascii")
        response = client.moderations.create(
            model="omni-moderation-latest",
            input=[{"type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"}}],
        )
        result = response.results[0]
        return {
            "flagged": result.flagged,
            "categories": {k: v for k, v in result.categories.model_dump().items() if v},
        }
    except Exception as e:
        logger.error("Image moderation API error: %s", e)
        return {"flagged": False, "categories": {}}


def check_image_moderation(image_bytes, mime="image/jpeg", user=None, label=""):
    """
    Check an image against the (free) moderation API. Logs if flagged.
    Returns (is_safe, detail_dict).
    """
    result = _call_image_moderation_api(image_bytes, mime)
    if result["flagged"]:
        ModerationLog.objects.create(
            user=user,
            content=f"[image] {label}"[:500],
            flagged_categories=result["categories"],
        )
        return False, result
    return True, result


# Categories the free moderation API does NOT cover but we still want to block.
RELEVANCE_BLOCK_CATEGORIES = [
    "political", "off_topic", "sexual", "violent", "hate", "profanity", "spam",
]


def classify_relevance(text, context_label=""):
    """
    Cheap LLM gate for what the free moderation API misses: political/partisan
    content and off-topic chatter (e.g. a pizza recipe in a coding channel).
    Uses the cheapest configured model (OPENAI_SEARCH_MODEL, gpt-4o-mini) with a
    tiny token budget. Returns {allowed: bool, categories: [str], reason: str}.
    Fails OPEN (allowed=True) when stubbed or on any error.
    """
    text = (text or "").strip()
    if _is_stub_mode() or not text:
        return {"allowed": True, "categories": [], "reason": "stub"}

    try:
        import json

        import openai

        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        system = (
            "You are a lenient content gate for babook, an educational "
            "coding/technology community used by students (including minors). "
            "Default to ALLOW. Set allowed=false ONLY for a clear, unambiguous "
            "violation: sexual content; graphic violence; hateful or abusive "
            "language; strong profanity; partisan political campaigning; spam or "
            "advertising; or a message that is obviously and entirely unrelated "
            "to learning (e.g. a cooking recipe). ALWAYS ALLOW: greetings, thanks, "
            "short messages, emojis, code, questions, project/lesson talk, "
            "encouragement, and anything plausibly about learning. When in doubt, "
            "ALLOW. Hebrew and English are both fine. "
            f"Conversation context: {context_label or 'general learning chat'}. "
            'Respond ONLY as compact JSON: '
            '{"allowed": true|false, "categories": [..], "reason": "short"}. '
            f"categories must be a subset of {RELEVANCE_BLOCK_CATEGORIES}."
        )
        response = client.chat.completions.create(
            model=settings.OPENAI_SEARCH_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": text[:2000]},
            ],
            max_tokens=120,
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content or "{}")
        return {
            "allowed": bool(data.get("allowed", True)),
            "categories": [c for c in (data.get("categories") or []) if isinstance(c, str)],
            "reason": str(data.get("reason", ""))[:200],
        }
    except Exception as e:
        logger.error("Relevance classifier error: %s", e)
        return {"allowed": True, "categories": [], "reason": "error"}


def grade_image_submission(image_bytes, task_text, model="gpt-4o", detail="high"):
    """Vision grade: does the screenshot satisfy `task_text`? Advisory only.
    Returns {ok, score, reason, model, prompt_tokens, completion_tokens} or None
    (stub mode / error - caller leaves the submission ungraded). Short timeout so
    a slow API never hangs the upload request."""
    if _is_stub_mode() or not image_bytes:
        return None
    try:
        import base64
        import json

        import openai

        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        b64 = base64.b64encode(image_bytes).decode("ascii")
        system = (
            "You grade whether a student's submitted screenshot satisfies a given "
            "task on an educational coding/technology platform. Be encouraging but "
            "honest; partial credit is fine. The goal is to confirm the screenshot "
            "plausibly shows the asked-for work (not pixel-perfect). "
            'Respond ONLY as JSON: {"ok": true|false, "score": 0-100, '
            '"reason": "one short sentence"}.'
        )
        response = client.chat.completions.create(
            model=model,
            max_tokens=150,
            temperature=0,
            response_format={"type": "json_object"},
            timeout=25,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": [
                    {"type": "text", "text": (task_text or "")[:1500]},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": detail}},
                ]},
            ],
        )
        data = json.loads(response.choices[0].message.content or "{}")
        u = response.usage
        score = data.get("score")
        return {
            "ok": bool(data.get("ok")),
            "score": int(score) if isinstance(score, (int, float)) else None,
            "reason": str(data.get("reason", ""))[:300],
            "model": model,
            "prompt_tokens": u.prompt_tokens,
            "completion_tokens": u.completion_tokens,
        }
    except Exception as e:
        logger.error("Grader error: %s", e)
        return None


def check_rate_limit(user):
    """
    Check if user has exceeded daily token limit.
    Returns (allowed: bool, reason: str).
    """
    role = "member"
    try:
        role = user.profile.role
    except Exception:
        pass

    limit = settings.OPENAI_DAILY_TOKEN_LIMITS.get(role, 0)
    if limit == 0:
        return False, "Chat not available for your account tier. Rate limit: 0 tokens."

    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_usage = UsageLog.objects.filter(
        user=user,
        created_at__gte=today_start,
    ).aggregate(
        total=Sum("prompt_tokens") + Sum("completion_tokens")
    )
    used = today_usage["total"] or 0
    if used >= limit:
        return False, f"Daily token limit reached ({used}/{limit}). Resets at midnight UTC."
    return True, ""


def check_cost_cap():
    """
    Check if monthly cost cap has been reached.
    Returns (under_cap: bool, total_cost: float).
    """
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_cost = UsageLog.objects.filter(
        created_at__gte=month_start,
    ).aggregate(total=Sum("cost_usd"))
    total = month_cost["total"] or 0.0
    return total < settings.OPENAI_MONTHLY_COST_CAP_USD, total


def get_system_prompt(context_type, course=None):
    """
    Get the system prompt for a context type. Falls back to default.
    If course is provided, appends course metadata.
    """
    try:
        prompt_obj = SystemPrompt.objects.get(context_type=context_type)
        prompt = prompt_obj.content
    except SystemPrompt.DoesNotExist:
        prompt = "You are a helpful AI assistant for babook.co.il, an AI training platform."

    if course:
        prompt += f"\n\nThe student is currently studying: {course.title}."
        if course.description:
            prompt += f"\nCourse description: {course.description}"
    return prompt


def handle_chat_message(user, message_text, session_id=None, course_slug=None):
    """
    Main entry point for processing a chat message.
    Returns (response_dict, status_code).
    """
    # Cost cap check
    under_cap, total_cost = check_cost_cap()
    if not under_cap:
        return {"error": "Monthly AI budget reached. Chat is temporarily disabled."}, 429

    # Rate limit check
    allowed, reason = check_rate_limit(user)
    if not allowed:
        return {"error": reason}, 429

    # Moderation check
    is_safe, mod_detail = check_moderation(message_text, user=user)
    if not is_safe:
        return {"error": "Your message was flagged by our content filter. Please rephrase."}, 400

    # Topicality: keep the tutor on subject - block political / off-topic / abusive
    # messages the free filter doesn't cover. Cached + fails open.
    from .safety import text_relevance_ok
    ctx = f"AI tutor for course {course_slug}" if course_slug else "AI learning tutor"
    if not text_relevance_ok(message_text, context_label=ctx, user=user)[0]:
        return {"error": "Let's keep our chat about the course and your learning. "
                         "Please rephrase your question."}, 400

    # Get or create session
    session = None
    if session_id:
        session = ChatSession.objects.filter(id=session_id, user=user).first()
    if not session:
        context = "general_assistant"
        course = None
        if course_slug:
            from .models import Course

            course = Course.objects.filter(slug=course_slug).first()
            if course:
                context = "course_tutor"
        session = ChatSession.objects.create(
            user=user, context_type=context, course=course
        )

    # Build system prompt
    system_prompt = get_system_prompt(session.context_type, session.course)

    # Save user message
    ChatMessage.objects.create(
        session=session, role="user", content=message_text, tokens_used=0
    )

    # Build message history (last N messages)
    recent_messages = list(
        session.messages.order_by("-created_at")[:20]
    )
    recent_messages.reverse()
    messages = [{"role": m.role, "content": m.content} for m in recent_messages]

    # Call OpenAI
    result = call_openai(messages, system_prompt=system_prompt)

    # Save assistant message
    ChatMessage.objects.create(
        session=session,
        role="assistant",
        content=result["content"],
        tokens_used=result["completion_tokens"],
    )

    # Log usage
    UsageLog.objects.create(
        user=user,
        session=session,
        model=result["model"],
        prompt_tokens=result["prompt_tokens"],
        completion_tokens=result["completion_tokens"],
        cost_usd=_estimate_cost(result["model"], result["prompt_tokens"], result["completion_tokens"]),
    )

    return {
        "content": result["content"],
        "session_id": session.id,
        "model": result["model"],
    }, 200


def _estimate_cost(model, prompt_tokens, completion_tokens):
    """Rough cost estimate per OpenAI pricing."""
    rates = {
        "gpt-4o-mini": {"prompt": 0.15 / 1_000_000, "completion": 0.60 / 1_000_000},
        "gpt-4o": {"prompt": 2.50 / 1_000_000, "completion": 10.00 / 1_000_000},
    }
    r = rates.get(model, rates["gpt-4o-mini"])
    return prompt_tokens * r["prompt"] + completion_tokens * r["completion"]


def _lesson_tutor_system_prompt(video):
    """System prompt for the per-lesson 'Explain more' tutor: the lesson content
    plus instructions to stay focused and explain it further."""
    notes = (video.notes_markdown or "")[:6000]
    course = video.course
    return (
        "You are a patient, encouraging tutor sitting next to a single lesson of an "
        "online course. The student is reading this lesson and wants you to explain it "
        "further: go deeper, give small examples, or talk it through. Stay focused on "
        "THIS lesson and the course's subject. Be concise and clear, build on the "
        "lesson's own wording, and prefer short concrete examples. If the student asks "
        "something unrelated, gently steer back to the lesson. Answer in the student's "
        "language (the lesson itself is in English). Do not invent course facts beyond "
        "the lesson; if something is outside it, say so briefly.\n\n"
        f"Course: {course.title}\n"
        f"Lesson: {video.title}\n\n"
        "Lesson content (markdown):\n-----\n"
        f"{notes}\n-----"
    )


def handle_lesson_explain(user, video, message_text):
    """Per-lesson 'Explain more' tutor.  Keeps ONE persistent ChatSession per
    (user, lesson) so the whole thread is resent every turn and reads like an
    ongoing consultation.  Returns (response_dict, status_code)."""
    message_text = (message_text or "").strip()
    if not message_text:
        return {"error": "Empty question."}, 400

    under_cap, _ = check_cost_cap()
    if not under_cap:
        return {"error": "Monthly AI budget reached. The tutor is temporarily disabled."}, 429

    # Staff (course authors) bypass the per-tier daily token limit while building.
    if not getattr(user, "is_staff", False):
        allowed, reason = check_rate_limit(user)
        if not allowed:
            return {"error": reason}, 429

    is_safe, _ = check_moderation(message_text, user=user)
    if not is_safe:
        return {"error": "Your message was flagged by our content filter. Please rephrase."}, 400

    from .safety import text_relevance_ok
    ctx = f"AI tutor for lesson '{video.title}' in course {video.course.slug}"
    if not text_relevance_ok(message_text, context_label=ctx, user=user)[0]:
        return {"error": "Let's keep this about the lesson. Please rephrase your question."}, 400

    session, _ = ChatSession.objects.get_or_create(
        user=user, video=video, context_type="lesson_tutor",
        defaults={"course": video.course},
    )

    user_msg = ChatMessage.objects.create(session=session, role="user", content=message_text, tokens_used=0)

    # Resend the whole thread (capped) so the tutor remembers the discussion.
    history = list(session.messages.order_by("created_at").values("role", "content"))
    messages = [{"role": m["role"], "content": m["content"]} for m in history][-40:]

    result = call_openai(
        messages, model=settings.OPENAI_DEFAULT_MODEL,
        system_prompt=_lesson_tutor_system_prompt(video),
    )

    # A failed real API call returns 0 tokens.  Don't persist the turn, so the
    # student can retry cleanly instead of seeing an error stuck in the thread.
    if not _is_stub_mode() and result["prompt_tokens"] == 0 and result["completion_tokens"] == 0:
        user_msg.delete()
        return {"error": "The tutor is unavailable right now. Please try again in a moment."}, 503

    ChatMessage.objects.create(
        session=session, role="assistant",
        content=result["content"], tokens_used=result["completion_tokens"],
    )
    UsageLog.objects.create(
        user=user, session=session, model=result["model"],
        prompt_tokens=result["prompt_tokens"], completion_tokens=result["completion_tokens"],
        cost_usd=_estimate_cost(result["model"], result["prompt_tokens"], result["completion_tokens"]),
    )
    return {"content": result["content"]}, 200


def _cell_src(cell):
    s = cell.get("source", "")
    return "".join(s) if isinstance(s, list) else (s or "")


def _cell_outputs(cell):
    """Text (stream / execute_result / error) outputs of a code cell; images skipped."""
    outs = []
    for o in cell.get("outputs", []):
        ot = o.get("output_type")
        if ot == "stream":
            t = o.get("text", "")
        elif ot in ("execute_result", "display_data"):
            t = (o.get("data", {}) or {}).get("text/plain", "")
        elif ot == "error":
            t = "ERROR: {}: {}".format(o.get("ename", ""), o.get("evalue", ""))
        else:
            t = ""
        if isinstance(t, list):
            t = "".join(t)
        if t:
            outs.append(t)
    return "\n".join(outs).strip()


def _split_answer(src):
    """Split an exercise cell into (provided, student_answer): everything AFTER a
    'YOUR CODE HERE' marker line is the student's own work.  Without a marker,
    non-comment lines are treated as the answer.  This keeps provided setup lines
    from being counted as the student's work."""
    lines = src.splitlines()
    marker = None
    for i, ln in enumerate(lines):
        if "your code here" in ln.lower():
            marker = i
            break
    if marker is not None:
        provided = "\n".join(lines[:marker]).strip()
        student = "\n".join(lines[marker + 1:]).strip()
    else:
        provided = "\n".join(ln for ln in lines if ln.strip().startswith("#")).strip()
        student = "\n".join(ln for ln in lines if ln.strip() and not ln.strip().startswith("#")).strip()
    return provided, student


def _extract_exercise_cells(nb, limit=12000):
    """Return (text, n_exercises, n_attempted) for ONLY the student's task cells:
    code cells tagged 'exercise' (or, when untagged, placeholder cells before a
    Solutions header).  Cells tagged 'solution' are always excluded.  Each cell's
    ANSWER (code after 'YOUR CODE HERE') is separated from the provided setup, so the
    grader judges only the student's own work."""
    cells = nb.get("cells", [])
    picked = []
    for c in cells:
        if c.get("cell_type") != "code":
            continue
        tags = (c.get("metadata", {}) or {}).get("tags", []) or []
        if "solution" in tags:
            continue
        if "exercise" in tags:
            picked.append(c)
    if not picked:
        # Fallback for untagged notebooks: placeholder cells before a Solutions
        # header.  Match the "## Solutions" HEADER, not prose that merely mentions it.
        sol_at = None
        for i, c in enumerate(cells):
            if c.get("cell_type") == "markdown" and _cell_src(c).strip().lower().startswith("## solution"):
                sol_at = i
                break
        for i, c in enumerate(cells):
            if c.get("cell_type") != "code" or (sol_at is not None and i > sol_at):
                continue
            low = _cell_src(c).lower()
            if "your code here" in low or "# todo" in low or "your answer" in low:
                picked.append(c)
    parts, attempted = [], 0
    for n, c in enumerate(picked, 1):
        provided, student = _split_answer(_cell_src(c))
        out = _cell_outputs(c)
        if student or out:
            attempted += 1
        block = "EXERCISE {}:\n[task/provided]\n{}\n[student answer]\n{}".format(
            n, provided or "(none)", student or "(EMPTY - not attempted)")
        if out:
            block += "\n[output]\n" + out
        parts.append(block)
    return "\n\n".join(parts)[:limit], len(picked), attempted


def grade_notebook(user, video, notebook_bytes):
    """Grade an uploaded .ipynb against its lesson with a cheap model.  Reads the
    code and its saved outputs (never executes anything).  Returns
    (result_dict, status_code); result = {grade, feedback, recommendation, model}."""
    import json

    under_cap, _ = check_cost_cap()
    if not under_cap:
        return {"error": "Monthly AI budget reached. Grading is temporarily disabled."}, 429
    if not getattr(user, "is_staff", False):
        allowed, reason = check_rate_limit(user)
        if not allowed:
            return {"error": reason}, 429

    try:
        nb = json.loads(notebook_bytes.decode("utf-8", "ignore"))
    except Exception:
        return {"error": "That file is not a valid Jupyter notebook (.ipynb)."}, 400
    extracted, n_ex, n_attempted = _extract_exercise_cells(nb)
    if n_ex == 0:
        return {"error": "No exercises found in this notebook. Make sure you uploaded the "
                         "right lesson's notebook (the one with the tasks to complete)."}, 400

    model = settings.OPENAI_DEFAULT_MODEL
    # Deterministic: nothing attempted -> 0, without spending a model call.
    if n_attempted == 0:
        return {"grade": 0, "model": "rule",
                "feedback": "None of the {} exercises are done yet - every task cell is still "
                            "empty.".format(n_ex),
                "recommendation": "Write your answer under each 'YOUR CODE HERE' line, run the "
                                  "cells, then upload again."}, 200

    if _is_stub_mode():
        return {"grade": 80, "model": model,
                "feedback": "[Stub] Grades only the student's answers. Set OPENAI_API_KEY for real grading.",
                "recommendation": "[Stub] Enable the API key."}, 200

    system = (
        "You grade a student's answers to a lesson's exercises. For each exercise you get the "
        "[task/provided] (given to the student, NOT their work), the [student answer] (their "
        "own code), and any [output]. Grade ONLY the [student answer] parts. An answer shown "
        "as '(EMPTY - not attempted)' scores 0 for that exercise. The overall grade is the "
        "percentage of exercises the student both attempted AND got correct. Be specific and "
        "constructive. Respond ONLY as JSON: "
        '{"grade": <int 0-100>, "feedback": "<what is right, what is missing or wrong>", '
        '"recommendation": "<concrete next steps>"}.'
    )
    user_msg = (
        f"LESSON: {video.title}\n\n{(video.notes_markdown or '')[:2500]}\n\n"
        f"There are {n_ex} exercises; the student attempted {n_attempted}.\n\n"
        f"EXERCISES:\n{extracted}"
    )
    try:
        import openai

        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY, max_retries=1)
        resp = client.chat.completions.create(
            model=model, temperature=0, max_tokens=500,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user_msg}],
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        u = resp.usage
        UsageLog.objects.create(
            user=user, session=None, model=model,
            prompt_tokens=u.prompt_tokens, completion_tokens=u.completion_tokens,
            cost_usd=_estimate_cost(model, u.prompt_tokens, u.completion_tokens),
        )
        g = data.get("grade")
        g = int(g) if isinstance(g, (int, float)) else 0
        return {
            "grade": max(0, min(100, g)),
            "feedback": str(data.get("feedback", ""))[:2000],
            "recommendation": str(data.get("recommendation", ""))[:2000],
            "model": model,
        }, 200
    except Exception as e:
        logger.error("Notebook grader error: %s", e)
        return {"error": "The grader is unavailable right now. Please try again in a moment."}, 503
