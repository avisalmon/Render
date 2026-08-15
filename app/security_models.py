"""
Home Security Relay - data model  (Chapter 11 / EPIC-12, REQ-11.8.1)
====================================================================
Three tables. babook is a *projection* of the home system, never a source of
truth: if this data vanished the house could rebuild all of it. Nothing here is
authoritative, so nothing here needs to be defended as if it were.

  SecurityEvent    one detection on one camera at one moment. `event_id` is the
                   home system's own id and the natural key - upserts key on it.
  SecurityCommand  the only channel *toward* the house. It is behind CGNAT, so
                   babook cannot call it; commands sit here until the house
                   collects them on its next poll.
  SecurityState    a single row (pk=1), overwritten every ~5 minutes. Its real
                   job is detecting silence - see REQ-11.6.1.
"""

from django.db import models


class SecurityEvent(models.Model):
    """One event pushed by the house. Severity, names and grouping arrive
    already decided; babook displays them and never recomputes (REQ-11.1.4)."""

    # The home system's own id. Unique and permanent over there, so it is the
    # natural key here and the thing upserts collide on (REQ-11.5.1).
    event_id = models.BigIntegerField(unique=True, db_index=True)

    # Aware datetime parsed from the wire. `ts_raw` keeps the string exactly as
    # sent so an offset/DST dispute can be settled against what actually arrived.
    ts = models.DateTimeField(db_index=True)
    ts_raw = models.CharField(max_length=64, blank=True)

    channel = models.CharField(max_length=32)
    camera = models.CharField(max_length=120, db_index=True)
    # `type` on the wire; renamed here only because it shadows the builtin.
    event_type = models.CharField(max_length=32)
    # Open string on purpose: an unknown severity must render, not fail
    # (REQ-11.5.4). Known values are info / warning / critical.
    severity = models.CharField(max_length=16)

    names = models.JSONField(default=list, blank=True)
    unidentified = models.IntegerField(default=0)
    incident_key = models.CharField(max_length=64, blank=True, null=True, db_index=True)

    # A link, never a file. babook stores no video in any form (REQ-11.1.1).
    drive_url = models.URLField(max_length=500, blank=True, null=True)
    drive_file_id = models.CharField(max_length=128, blank=True, null=True)

    # Relative filename under SECURITY_SNAPSHOT_DIR, which is deliberately not
    # under MEDIA_ROOT - that path is served publicly with no auth (REQ-11.7.2).
    snapshot_path = models.CharField(max_length=255, blank=True)

    # babook's own receipt time, for debugging clock skew against `ts`.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Display is always newest-first by `ts`, never by arrival: events come
        # in late and out of order when the house flushes a queue (REQ-11.5.6).
        ordering = ["-ts", "-event_id"]
        indexes = [
            models.Index(fields=["-ts"], name="secev_ts_desc_idx"),
            models.Index(fields=["camera", "-ts"], name="secev_cam_ts_idx"),
        ]

    def __str__(self):
        return f"{self.event_id} {self.camera} {self.severity}"


class SecurityCommand(models.Model):
    """Queued instruction for the house to collect on its next poll.

    This exists because the house is behind carrier-grade NAT: no inbound
    connection is possible, so there is no other way to reach it (REQ-11.4.2).
    """

    # Open string. Phase 1 uses "snapshot" and "resync"; babook passes through
    # any value without needing to understand it.
    kind = models.CharField(max_length=64)
    params = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    delivered_at = models.DateTimeField(null=True, blank=True)
    acked_at = models.DateTimeField(null=True, blank=True)
    ack_status = models.CharField(max_length=16, blank=True)  # done | failed
    ack_detail = models.TextField(blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"cmd {self.pk} {self.kind}"


class SecurityState(models.Model):
    """Health of the house. Exactly one row, pk=1, overwritten in place.

    Deliberately not a log. What matters is the age of the last update: an
    absent event stream looks exactly like a quiet afternoon, so silence here
    is the only thing that can tell the owner the system has stopped
    (REQ-11.6.1).
    """

    ok = models.BooleanField(default=True)
    cameras_online = models.IntegerField(default=0)
    cameras_total = models.IntegerField(default=0)
    last_event_ts = models.DateTimeField(null=True, blank=True)
    disk_free_gb = models.FloatField(null=True, blank=True)
    notes = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now=True)

    @classmethod
    def current(cls):
        return cls.objects.filter(pk=1).first()

    def __str__(self):
        return f"state ok={self.ok} at {self.received_at}"


class SecurityViewLog(models.Model):
    """Who opened the page, and when (REQ-11.2.4).

    It is the owner's house. Being able to answer "who looked, and when" is
    part of the deal for delegating access to anyone at all.
    """

    email = models.CharField(max_length=254)
    path = models.CharField(max_length=120)
    viewed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-viewed_at"]

    def __str__(self):
        return f"{self.email} {self.viewed_at:%Y-%m-%d %H:%M}"
