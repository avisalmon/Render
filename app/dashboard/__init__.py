"""EPIC-8 — Admin / Management Control Dashboard.

A superuser-only cockpit at ``/admin-dashboard/``. Logic lives here so the
views stay thin and the collectors/adapters are independently testable and
reusable by the ``capture_dashboard_snapshot`` command.
"""
