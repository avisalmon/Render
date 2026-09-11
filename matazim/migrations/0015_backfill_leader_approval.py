"""Every leader who already exists was already approved.

0014 added `approved_at`, and every existing row has it null. Under REQ-M.93
null means candidate, and `access.leader_of` refuses to return a candidate. So
without this migration the deploy that introduces candidates would turn every
current leader into one: no roster, no invite link, no leader view, and no
error anywhere to explain it.

They were approved. Somebody made them a leader through the staff screen, which
is the only way a `Leader` row could exist before today. The approval simply had
no field to be recorded in, so it is backdated to when they were assigned, which
is the moment it actually happened.

`assigned_by` becomes `approved_by` for the same reason: it is a record of the
same act, under the name that act now has.
"""

from django.db import migrations
from django.utils import timezone


def approve_everyone(apps, schema_editor):
    Leader = apps.get_model("matazim", "Leader")

    waiting = Leader.objects.filter(approved_at__isnull=True)
    count = waiting.count()
    if not count:
        return

    for leader in waiting:
        # assigned_at is when somebody actually made this decision. Falling back
        # to now only when that is missing, which no row created by the staff
        # screen should be.
        leader.approved_at = getattr(leader, "assigned_at", None) or timezone.now()
        leader.approved_by_id = leader.assigned_by_id
        leader.save(update_fields=["approved_at", "approved_by"])

    print(f"  matazim: {count} existing leader(s) marked approved")


def unapprove(apps, schema_editor):
    """Reversible, and harmless: 0014 drops the columns anyway."""
    Leader = apps.get_model("matazim", "Leader")
    Leader.objects.update(approved_at=None, approved_by=None)


class Migration(migrations.Migration):
    dependencies = [("matazim", "0014_leader_approval")]
    operations = [migrations.RunPython(approve_everyone, unapprove)]
