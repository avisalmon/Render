"""SensorLab's REST API.

Rule 6: every app here gets a full, documented CRUD API as standard
infrastructure, not as an add-on for the screens that happen to need one.
SensorLab leans on that harder than the older apps did — its screens are
the API's first consumer by design.

This sprint (SL-A3) builds the platform: the router everything registers
onto, the conventions, the schema that documents them, and `profile/me/`
to prove the stack end to end. The curriculum resources register here in
SL-B2, at which point the schema starts listing them with no edit.
"""

from rest_framework.routers import DefaultRouter

#: Everything SensorLab exposes hangs off this. Empty until SL-B2 — the
#: honest state of an app with one table, not a gap.
router = DefaultRouter()
