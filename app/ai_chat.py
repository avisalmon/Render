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
