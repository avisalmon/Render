"""Server→client Plausible event bridge (REQ-6.8.1).

Server-side actions can't call Plausible directly (it's client JS), so we stash
event names in the session; base.html fires + clears them on the next render.
Mirrors the §5 entry-event pattern.
"""
_SESSION_KEY = "pending_plausible_events"


def _mark_modified(session):
    try:
        session.modified = True
    except (AttributeError, TypeError):
        pass  # plain-dict sessions (tests) don't track modified


# JSON inside a <script> tag never carries a raw "<", ">" or "&" (security review, 2026-10-24).
_SCRIPT_ESCAPES = {ord("<"): "\\u003c", ord(">"): "\\u003e", ord("&"): "\\u0026"}


def script_json(value):
    import json

    return json.dumps(value, ensure_ascii=False, default=str).translate(_SCRIPT_ESCAPES)


def flash_event(request, name, props=None):
    """Queue a Plausible event to fire on the user's next page load."""
    if not hasattr(request, "session"):
        return
    events = request.session.get(_SESSION_KEY, [])
    events.append({"name": name, "props": props or {}})
    request.session[_SESSION_KEY] = events[-10:]  # cap
    _mark_modified(request.session)


def pop_events(request):
    """Return + clear the queued events (called by the context processor)."""
    if not hasattr(request, "session"):
        return []
    events = request.session.pop(_SESSION_KEY, [])
    if events:
        _mark_modified(request.session)
    return events
