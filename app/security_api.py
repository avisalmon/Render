"""
Home Security Relay - machine API  (Chapter 11 / EPIC-12, REQ-11.3 / REQ-11.4)
==============================================================================
Five endpoints under /api/v1/security/. The house is the only writer. Plain
Django JSON views with a bearer token, the same shape as app/course_api.py.

The contract is owned by the home system (C:\\Projects\\Security\\docs\\relay_api.md);
the hand-off copy is docs/security_relay_spec.md. Four rules from it drive most
of the code below, and getting any of them wrong breaks the house rather than
babook:

  * Idempotent upsert on event_id. The same event WILL arrive twice - the house
    retries on failure and flushes its queue after being offline.
  * Partial success. One bad event in a batch of 40 must not cost the other 39,
    because the house would retry the whole batch forever and none would land.
  * 4xx means "this will never work, drop it"; 5xx means "retry forever". So bad
    input must never answer 5xx, or a single malformed event jams the queue.
  * Unknown fields are ignored, never rejected, so the two sides can deploy
    independently.
"""

import base64
import binascii
import hmac
import json
import os
import time
from functools import wraps
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .security_models import SecurityCommand, SecurityEvent, SecurityState

REQUIRED_EVENT_FIELDS = ("event_id", "ts", "channel", "camera", "type", "severity")


# ---------------------------------------------------------------------------
# Errors  (relay_api.md §8)
# ---------------------------------------------------------------------------

def _err(error, detail, status):
    return JsonResponse({"error": error, "detail": detail}, status=status)


# ---------------------------------------------------------------------------
# Auth  (REQ-11.3)
# ---------------------------------------------------------------------------

def require_relay_token(view_fn):
    """Bearer token, compared in constant time.

    `==` on a secret leaks its length and prefix through timing, which is the
    whole reason the contract names hmac.compare_digest explicitly. A missing
    token and a wrong token give the same 401 with no hint as to which.
    """
    @wraps(view_fn)
    def _wrapper(request, *args, **kwargs):
        expected = getattr(settings, "SECURITY_RELAY_TOKEN", "")
        if not expected:
            # Not configured is babook's problem, not the caller's, so it is a
            # 5xx: the house should keep retrying until the env var is set.
            return _err("not_configured", "relay token not configured", 503)
        header = request.headers.get("Authorization", "")
        presented = header[7:] if header.startswith("Bearer ") else ""
        if not hmac.compare_digest(presented, expected):
            return _err("unauthorized", "invalid or missing token", 401)
        return view_fn(request, *args, **kwargs)
    return _wrapper


# ---------------------------------------------------------------------------
# Body handling
# ---------------------------------------------------------------------------

def _read_json(request):
    """Return (payload, error_response). Size limits answer 413, malformed 400.

    Never 5xx: both are permanent conditions and the house must drop, not retry.
    """
    declared = request.META.get("CONTENT_LENGTH") or 0
    try:
        declared = int(declared)
    except (TypeError, ValueError):
        declared = 0
    if declared > settings.SECURITY_MAX_BODY_BYTES:
        return None, _err("payload_too_large", "body exceeds 10 MB", 413)
    try:
        raw = request.body
    except RequestDataTooBig:
        return None, _err("payload_too_large", "body exceeds 10 MB", 413)
    if len(raw) > settings.SECURITY_MAX_BODY_BYTES:
        return None, _err("payload_too_large", "body exceeds 10 MB", 413)
    try:
        return json.loads(raw or b"{}"), None
    except (ValueError, UnicodeDecodeError) as exc:
        return None, _err("bad_request", f"malformed JSON: {exc}", 400)


# ---------------------------------------------------------------------------
# Snapshot storage  (REQ-11.7)
# ---------------------------------------------------------------------------

_usage_cache = {"bytes": 0, "checked": 0.0}


def _snapshot_dir():
    path = settings.SECURITY_SNAPSHOT_DIR
    os.makedirs(path, exist_ok=True)
    return path


def _snapshot_bytes_used(force=False):
    """Total size of the snapshot directory, re-scanned at most once a minute.

    A scan per event would be O(files) on every one of 200 events in a batch;
    the budget only needs to be roughly right, so a stale-by-a-minute number is
    the correct trade.
    """
    now = time.monotonic()
    if not force and now - _usage_cache["checked"] < 60:
        return _usage_cache["bytes"]
    total = 0
    try:
        with os.scandir(_snapshot_dir()) as it:
            for entry in it:
                if entry.is_file():
                    total += entry.stat().st_size
    except OSError:
        total = 0
    _usage_cache["bytes"] = total
    _usage_cache["checked"] = now
    return total


def _over_budget():
    return _snapshot_bytes_used() >= settings.SECURITY_SNAPSHOT_BUDGET_MB * 1024 * 1024


def _store_snapshot(event_id, b64):
    """Write the JPEG and return (relative_path, warning).

    Every failure path returns a warning and no path: an unusable snapshot must
    never cost us the event, which is the part that actually matters
    (see Chapter 11 §11.9.2).
    """
    if not settings.SECURITY_SNAPSHOTS_ENABLED:
        return "", None
    try:
        blob = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError, TypeError):
        return "", "snapshot is not valid base64, event stored without it"
    if len(blob) > settings.SECURITY_SNAPSHOT_MAX_BYTES:
        return "", (
            f"snapshot {len(blob)}B exceeds the "
            f"{settings.SECURITY_SNAPSHOT_MAX_BYTES}B cap, event stored without it"
        )
    if _over_budget():
        return "", "snapshot disk budget reached, event stored without it"
    name = f"{event_id}.jpg"
    try:
        with open(os.path.join(_snapshot_dir(), name), "wb") as fh:
            fh.write(blob)
    except OSError as exc:
        return "", f"snapshot could not be written ({exc}), event stored without it"
    _usage_cache["bytes"] += len(blob)
    return name, None


def delete_snapshot_file(relative_path):
    if not relative_path:
        return
    try:
        os.remove(os.path.join(settings.SECURITY_SNAPSHOT_DIR, relative_path))
    except OSError:
        pass  # already gone is the desired end state


# ---------------------------------------------------------------------------
# Event parsing
# ---------------------------------------------------------------------------

def _parse_ts(value):
    """ISO 8601 to an aware datetime, or None.

    A naive timestamp is accepted and read as Israel local time rather than
    rejected. The contract says every timestamp carries an offset, but 4xx
    means the house drops the event permanently - and silently losing a real
    security event is a worse outcome than assuming the house's own timezone.
    Unparseable is still a rejection.
    """
    if not isinstance(value, str):
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=ZoneInfo(settings.SECURITY_DISPLAY_TZ))
    return parsed


def _clean_event(raw):
    """Return (defaults, event_id, error_reason). Unknown keys are ignored."""
    if not isinstance(raw, dict):
        return None, None, "event is not an object"

    missing = [f for f in REQUIRED_EVENT_FIELDS if raw.get(f) in (None, "")]
    if missing:
        return None, raw.get("event_id"), f"missing required field(s): {', '.join(missing)}"

    try:
        event_id = int(raw["event_id"])
    except (TypeError, ValueError):
        return None, raw.get("event_id"), "event_id is not an integer"

    ts = _parse_ts(raw["ts"])
    if ts is None:
        return None, event_id, "bad ts"

    names = raw.get("names") or []
    if not isinstance(names, list):
        names = []
    names = [str(n) for n in names]

    try:
        unidentified = int(raw.get("unidentified") or 0)
    except (TypeError, ValueError):
        unidentified = 0

    defaults = {
        "ts": ts,
        "ts_raw": str(raw["ts"])[:64],
        "channel": str(raw["channel"])[:32],
        "camera": str(raw["camera"])[:120],
        "event_type": str(raw["type"])[:32],
        "severity": str(raw["severity"])[:16],
        "names": names,
        "unidentified": unidentified,
    }
    return defaults, event_id, None


# Optional fields are only written when the push actually carries a value.
# The house sends an event the moment it detects, then re-sends the same
# event_id later once the clip has reached Drive - so treating an absent or
# null drive_url as "clear it" would throw away the link it just gave us.
_ENRICHABLE = ("incident_key", "drive_url", "drive_file_id")


# ---------------------------------------------------------------------------
# POST /api/v1/security/events   (REQ-11.4.1)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
@require_relay_token
def push_events(request):
    payload, error = _read_json(request)
    if error:
        return error

    events = payload.get("events")
    if not isinstance(events, list):
        return _err("bad_request", "'events' must be a list", 400)
    if len(events) > settings.SECURITY_MAX_EVENTS_PER_REQUEST:
        return _err(
            "payload_too_large",
            f"{len(events)} events exceeds the "
            f"{settings.SECURITY_MAX_EVENTS_PER_REQUEST} per-request limit",
            413,
        )

    accepted = updated = 0
    rejected, warnings = [], []

    for index, raw in enumerate(events):
        defaults, event_id, reason = _clean_event(raw)
        if reason:
            rejected.append({"event_id": event_id, "reason": reason})
            continue

        for field in _ENRICHABLE:
            if raw.get(field) is not None:
                defaults[field] = str(raw[field])[:500]

        snapshot = raw.get("snapshot_b64")
        if snapshot:
            path, warning = _store_snapshot(event_id, snapshot)
            if path:
                defaults["snapshot_path"] = path
            if warning:
                warnings.append({"event_id": event_id, "warning": warning})

        try:
            _, created = SecurityEvent.objects.update_or_create(
                event_id=event_id, defaults=defaults
            )
        except Exception as exc:  # noqa: BLE001 - one bad row must not fail the batch
            rejected.append({"event_id": event_id, "reason": f"could not store: {exc}"})
            continue

        if created:
            accepted += 1
        else:
            updated += 1

    body = {"accepted": accepted, "updated": updated, "rejected": rejected}
    if warnings:
        # Not in the contract. Their §8.4 lets the house ignore it safely, and
        # it beats silently discarding an oversized snapshot.
        body["warnings"] = warnings
    return JsonResponse(body)


# ---------------------------------------------------------------------------
# GET /api/v1/security/commands   (REQ-11.4.2)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_GET
@require_relay_token
def get_commands(request):
    """The only channel toward the house. Idle is 200 with an empty list, never
    204 and never an error - the house polls this every 5-15 seconds forever."""
    pending = list(SecurityCommand.objects.filter(acked_at__isnull=True).order_by("id")[:20])
    now = timezone.now()
    undelivered = [c.pk for c in pending if c.delivered_at is None]
    if undelivered:
        SecurityCommand.objects.filter(pk__in=undelivered).update(delivered_at=now)
    return JsonResponse({
        "commands": [
            {
                "id": c.pk,
                "kind": c.kind,
                "params": c.params or {},
                "created_at": c.created_at.isoformat(),
            }
            for c in pending
        ]
    })


# ---------------------------------------------------------------------------
# POST /api/v1/security/commands/<id>/ack   (REQ-11.4.3)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
@require_relay_token
def ack_command(request, command_id):
    """Idempotent by contract: the house retries acks whose response it never
    received, so an unknown or already-acked id is a 200, not an error."""
    payload, error = _read_json(request)
    if error:
        return error
    status = str(payload.get("status") or "done")[:16]
    detail = str(payload.get("detail") or "")

    command = SecurityCommand.objects.filter(pk=command_id).first()
    if command and command.acked_at is None:
        command.acked_at = timezone.now()
        command.ack_status = status
        command.ack_detail = detail
        command.save(update_fields=["acked_at", "ack_status", "ack_detail"])
    return JsonResponse({"ok": True, "id": command_id})


# ---------------------------------------------------------------------------
# POST /api/v1/security/state   (REQ-11.4.4)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
@require_relay_token
def push_state(request):
    """One row, overwritten. The value is in its freshness, not its content."""
    payload, error = _read_json(request)
    if error:
        return error

    def _int(key):
        try:
            return int(payload.get(key) or 0)
        except (TypeError, ValueError):
            return 0

    try:
        disk_free = float(payload["disk_free_gb"]) if payload.get("disk_free_gb") is not None else None
    except (TypeError, ValueError):
        disk_free = None

    SecurityState.objects.update_or_create(
        pk=1,
        defaults={
            "ok": bool(payload.get("ok", True)),
            "cameras_online": _int("cameras_online"),
            "cameras_total": _int("cameras_total"),
            "last_event_ts": _parse_ts(payload.get("last_event_ts")),
            "disk_free_gb": disk_free,
            "notes": str(payload.get("notes") or "")[:2000],
        },
    )
    return JsonResponse({"ok": True})


# ---------------------------------------------------------------------------
# POST /api/v1/security/deletions   (REQ-11.4.5)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
@require_relay_token
def push_deletions(request):
    """Retention removed these at the house, so babook forgets them too.

    This is the ONLY way a row dies here. babook never expires anything on its
    own schedule (REQ-11.1.3). The Drive video is deleted by the house directly.
    """
    payload, error = _read_json(request)
    if error:
        return error

    ids = payload.get("event_ids")
    if not isinstance(ids, list):
        return _err("bad_request", "'event_ids' must be a list", 400)

    clean = []
    for value in ids:
        try:
            clean.append(int(value))
        except (TypeError, ValueError):
            continue  # unknown / unparseable ids are not an error

    rows = list(SecurityEvent.objects.filter(event_id__in=clean))
    for row in rows:
        delete_snapshot_file(row.snapshot_path)
    deleted = SecurityEvent.objects.filter(event_id__in=clean).delete()[0]
    _snapshot_bytes_used(force=True)
    return JsonResponse({"deleted": deleted})
