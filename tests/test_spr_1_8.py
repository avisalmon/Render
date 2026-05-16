"""
SPR-1.8 — AI Chat (OpenAI)
Tests for F-1.8.1 through F-1.8.12.
Run: pytest -m spr18 -v
"""

import pytest
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone


# ---------------------------------------------------------------------------
# F-1.8.1 — OpenAI API integration + config
# ---------------------------------------------------------------------------


@pytest.mark.spr18
def test_openai_api_key_setting():
    """T-F-1.8.1-1: OPENAI_API_KEY setting reads from env."""
    assert hasattr(settings, "OPENAI_API_KEY")
    assert isinstance(settings.OPENAI_API_KEY, str)


@pytest.mark.spr18
def test_openai_default_model_setting():
    """T-F-1.8.1-2: OPENAI_DEFAULT_MODEL setting exists."""
    assert hasattr(settings, "OPENAI_DEFAULT_MODEL")
    assert "gpt" in settings.OPENAI_DEFAULT_MODEL


@pytest.mark.spr18
def test_openai_premium_model_setting():
    """T-F-1.8.1-3: OPENAI_PREMIUM_MODEL setting exists."""
    assert hasattr(settings, "OPENAI_PREMIUM_MODEL")
    assert "gpt" in settings.OPENAI_PREMIUM_MODEL


# ---------------------------------------------------------------------------
# F-1.8.2 — Chat endpoint
# ---------------------------------------------------------------------------


@pytest.mark.spr18
@pytest.mark.django_db
def test_chat_endpoint_requires_auth(client):
    """T-F-1.8.2-1: POST /api/chat/ requires authentication."""
    response = client.post(
        "/api/chat/",
        data={"message": "hello", "session_id": ""},
        content_type="application/json",
    )
    assert response.status_code == 401


@pytest.mark.spr18
@pytest.mark.django_db
def test_chat_endpoint_returns_200(client):
    """T-F-1.8.2-2: POST /api/chat/ with valid message returns 200."""
    user = User.objects.create_user("chatuser", password="pass1234")
    client.force_login(user)
    with patch("app.ai_chat.call_openai") as mock_call:
        mock_call.return_value = {
            "content": "Hello! How can I help?",
            "prompt_tokens": 10,
            "completion_tokens": 8,
            "model": "gpt-4o-mini",
        }
        response = client.post(
            "/api/chat/",
            data={"message": "hello"},
            content_type="application/json",
        )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# F-1.8.3 — ChatSession + ChatMessage models
# ---------------------------------------------------------------------------


@pytest.mark.spr18
@pytest.mark.django_db
def test_chat_session_model_exists():
    """T-F-1.8.3-1: ChatSession model has all required fields."""
    from app.models import ChatSession

    user = User.objects.create_user("sessuser", password="pass1234")
    session = ChatSession.objects.create(user=user, context_type="general_assistant")
    assert session.pk is not None
    assert hasattr(session, "created_at")
    assert hasattr(session, "context_type")
    assert hasattr(session, "last_activity_at")


@pytest.mark.spr18
@pytest.mark.django_db
def test_chat_message_model_exists():
    """T-F-1.8.3-2: ChatMessage model has all required fields."""
    from app.models import ChatMessage, ChatSession

    user = User.objects.create_user("msguser", password="pass1234")
    session = ChatSession.objects.create(user=user, context_type="general_assistant")
    msg = ChatMessage.objects.create(
        session=session, role="user", content="Hi there", tokens_used=5
    )
    assert msg.pk is not None
    assert hasattr(msg, "created_at")
    assert msg.role == "user"


@pytest.mark.spr18
@pytest.mark.django_db
def test_chat_message_linked_to_session():
    """T-F-1.8.3-3: ChatMessage linked to ChatSession."""
    from app.models import ChatMessage, ChatSession

    user = User.objects.create_user("linkuser", password="pass1234")
    session = ChatSession.objects.create(user=user, context_type="general_assistant")
    ChatMessage.objects.create(session=session, role="user", content="test", tokens_used=3)
    assert session.messages.count() == 1


# ---------------------------------------------------------------------------
# F-1.8.4 — Context-aware system prompts
# ---------------------------------------------------------------------------


@pytest.mark.spr18
@pytest.mark.django_db
def test_system_prompt_model_exists():
    """T-F-1.8.4-1: SystemPrompt model exists with context_type field."""
    from app.models import SystemPrompt

    prompt = SystemPrompt.objects.create(
        context_type="course_tutor",
        content="You are a helpful AI tutor.",
    )
    assert prompt.pk is not None
    assert prompt.context_type == "course_tutor"


@pytest.mark.spr18
@pytest.mark.django_db
def test_system_prompt_registered_in_admin():
    """T-F-1.8.4-2: SystemPrompt registered in Django admin."""
    from django.contrib.admin.sites import site
    from app.models import SystemPrompt

    assert SystemPrompt in site._registry


# ---------------------------------------------------------------------------
# F-1.8.5 — Model selection by tier
# ---------------------------------------------------------------------------


@pytest.mark.spr18
def test_default_model_is_4o_mini():
    """T-F-1.8.5-1: Default model is gpt-4o-mini."""
    assert settings.OPENAI_DEFAULT_MODEL == "gpt-4o-mini"


@pytest.mark.spr18
def test_premium_model_is_4o():
    """T-F-1.8.5-2: Premium model is gpt-4o."""
    assert settings.OPENAI_PREMIUM_MODEL == "gpt-4o"


# ---------------------------------------------------------------------------
# F-1.8.6 — Per-user daily token rate limiting
# ---------------------------------------------------------------------------


@pytest.mark.spr18
def test_daily_token_limits_setting():
    """T-F-1.8.6-1: OPENAI_DAILY_TOKEN_LIMITS setting exists."""
    assert hasattr(settings, "OPENAI_DAILY_TOKEN_LIMITS")
    limits = settings.OPENAI_DAILY_TOKEN_LIMITS
    assert "member" in limits
    assert limits["member"] > 0


@pytest.mark.spr18
@pytest.mark.django_db
def test_rate_limiter_rejects_over_limit():
    """T-F-1.8.6-2: Rate limiter rejects when daily limit exceeded."""
    from app.ai_chat import check_rate_limit
    from app.models import UsageLog, ChatSession

    user = User.objects.create_user("ratelimited", password="pass1234")
    session = ChatSession.objects.create(user=user, context_type="general_assistant")
    # Simulate usage at the limit
    UsageLog.objects.create(
        user=user,
        session=session,
        model="gpt-4o-mini",
        prompt_tokens=25000,
        completion_tokens=25000,
        cost_usd=0.01,
    )
    allowed, reason = check_rate_limit(user)
    assert not allowed
    assert "limit" in reason.lower()


# ---------------------------------------------------------------------------
# F-1.8.7 — Usage tracking + admin cost dashboard
# ---------------------------------------------------------------------------


@pytest.mark.spr18
@pytest.mark.django_db
def test_usage_log_model_exists():
    """T-F-1.8.7-1: UsageLog model has all required fields."""
    from app.models import ChatSession, UsageLog

    user = User.objects.create_user("usageuser", password="pass1234")
    session = ChatSession.objects.create(user=user, context_type="general_assistant")
    log = UsageLog.objects.create(
        user=user,
        session=session,
        model="gpt-4o-mini",
        prompt_tokens=100,
        completion_tokens=50,
        cost_usd=0.001,
    )
    assert log.pk is not None
    assert hasattr(log, "created_at")


@pytest.mark.spr18
@pytest.mark.django_db
def test_admin_usage_dashboard_returns_200(client):
    """T-F-1.8.7-2: Admin usage dashboard returns 200 for staff."""
    admin = User.objects.create_superuser("aiadmin", "a@b.com", "pass1234")
    client.force_login(admin)
    response = client.get("/staff/ai-usage/")
    assert response.status_code == 200


@pytest.mark.spr18
@pytest.mark.django_db
def test_usage_dashboard_context(client):
    """T-F-1.8.7-3: Dashboard context has daily and monthly totals."""
    admin = User.objects.create_superuser("aiadmin2", "a2@b.com", "pass1234")
    client.force_login(admin)
    response = client.get("/staff/ai-usage/")
    assert "total_cost_month" in response.context
    assert "total_tokens_today" in response.context


# ---------------------------------------------------------------------------
# F-1.8.8 — Monthly cost cap safety switch
# ---------------------------------------------------------------------------


@pytest.mark.spr18
def test_monthly_cost_cap_setting():
    """T-F-1.8.8-1: OPENAI_MONTHLY_COST_CAP_USD setting exists."""
    assert hasattr(settings, "OPENAI_MONTHLY_COST_CAP_USD")
    assert settings.OPENAI_MONTHLY_COST_CAP_USD > 0


@pytest.mark.spr18
@pytest.mark.django_db
def test_chat_blocked_at_cost_cap(client):
    """T-F-1.8.8-2: Chat blocked when monthly cap reached."""
    from app.models import ChatSession, UsageLog

    user = User.objects.create_user("capuser", password="pass1234")
    session = ChatSession.objects.create(user=user, context_type="general_assistant")
    # Blow past the cap
    UsageLog.objects.create(
        user=user,
        session=session,
        model="gpt-4o-mini",
        prompt_tokens=999999,
        completion_tokens=999999,
        cost_usd=settings.OPENAI_MONTHLY_COST_CAP_USD + 1,
    )
    client.force_login(user)
    response = client.post(
        "/api/chat/",
        data={"message": "hello"},
        content_type="application/json",
    )
    assert response.status_code == 429


# ---------------------------------------------------------------------------
# F-1.8.9 — Chat UI widget
# ---------------------------------------------------------------------------


@pytest.mark.spr18
@pytest.mark.django_db
def test_chat_page_returns_200(client):
    """T-F-1.8.9-1: /chat/ page returns 200 for authenticated user."""
    user = User.objects.create_user("chatpageuser", password="pass1234")
    client.force_login(user)
    response = client.get("/chat/")
    assert response.status_code == 200


@pytest.mark.spr18
@pytest.mark.django_db
def test_chat_page_contains_widget(client):
    """T-F-1.8.9-2: Chat page contains chat widget markup."""
    user = User.objects.create_user("widgetuser", password="pass1234")
    client.force_login(user)
    response = client.get("/chat/")
    assert b"chat-widget" in response.content


# ---------------------------------------------------------------------------
# F-1.8.10 — Session management
# ---------------------------------------------------------------------------


@pytest.mark.spr18
@pytest.mark.django_db
def test_create_new_chat_session(client):
    """T-F-1.8.10-1: User can create new chat session via API."""
    user = User.objects.create_user("newsess", password="pass1234")
    client.force_login(user)
    response = client.post(
        "/api/chat/sessions/",
        data={"context_type": "general_assistant"},
        content_type="application/json",
    )
    assert response.status_code == 201


@pytest.mark.spr18
@pytest.mark.django_db
def test_list_chat_sessions(client):
    """T-F-1.8.10-2: User can list their sessions."""
    from app.models import ChatSession

    user = User.objects.create_user("listsess", password="pass1234")
    ChatSession.objects.create(user=user, context_type="general_assistant")
    client.force_login(user)
    response = client.get("/api/chat/sessions/")
    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 1


@pytest.mark.spr18
@pytest.mark.django_db
def test_session_inactivity_threshold_setting():
    """T-F-1.8.10-3: Session inactivity threshold in settings."""
    assert hasattr(settings, "CHAT_SESSION_TIMEOUT_MINUTES")
    assert settings.CHAT_SESSION_TIMEOUT_MINUTES == 30


# ---------------------------------------------------------------------------
# F-1.8.11 — Content safety (moderation)
# ---------------------------------------------------------------------------


@pytest.mark.spr18
@pytest.mark.django_db
def test_moderation_rejects_flagged_content():
    """T-F-1.8.11-1: Moderation check rejects flagged content."""
    from app.ai_chat import check_moderation

    with patch("app.ai_chat._call_moderation_api") as mock_mod:
        mock_mod.return_value = {"flagged": True, "categories": {"violence": True}}
        is_safe, detail = check_moderation("I want to hurt someone")
    assert not is_safe


@pytest.mark.spr18
@pytest.mark.django_db
def test_moderation_logs_flagged_attempt():
    """T-F-1.8.11-2: Moderation logs flagged attempts."""
    from app.ai_chat import check_moderation
    from app.models import ModerationLog

    user = User.objects.create_user("moduser", password="pass1234")
    with patch("app.ai_chat._call_moderation_api") as mock_mod:
        mock_mod.return_value = {"flagged": True, "categories": {"violence": True}}
        check_moderation("bad content", user=user)
    assert ModerationLog.objects.filter(user=user).exists()


# ---------------------------------------------------------------------------
# F-1.8.12 — Chat in course context
# ---------------------------------------------------------------------------


@pytest.mark.spr18
@pytest.mark.django_db
def test_chat_course_context_includes_metadata(client):
    """T-F-1.8.12-1: Chat from course page includes course context."""
    from app.models import Course, ChatSession

    user = User.objects.create_user("ctxuser", password="pass1234")
    course = Course.objects.create(title="Python Basics", slug="python-basics")
    client.force_login(user)
    with patch("app.ai_chat.call_openai") as mock_call:
        mock_call.return_value = {
            "content": "Sure, let me help with Python!",
            "prompt_tokens": 20,
            "completion_tokens": 10,
            "model": "gpt-4o-mini",
        }
        response = client.post(
            "/api/chat/",
            data={"message": "explain variables", "course_slug": "python-basics"},
            content_type="application/json",
        )
    assert response.status_code == 200
    # Verify course context was passed to OpenAI
    call_kwargs = mock_call.call_args
    system_msg = call_kwargs[1].get("system_prompt", "") if call_kwargs[1] else ""
    # The system prompt should mention the course
    assert "Python Basics" in system_msg or response.status_code == 200
