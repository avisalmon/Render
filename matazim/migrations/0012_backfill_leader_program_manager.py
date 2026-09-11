"""Give every existing leader an owner.

0011 added `Leader.program_manager` and every existing row has it null, which
under REQ-M.88 means orphaned: visible to root and to nobody else. In production
that would take נעמי's leaders away from her on the deploy that introduces
tenancy, which is precisely the failure this epic exists to avoid.

So each unowned leader is assigned to whoever already granted them, and failing
that to the earliest program manager in the database. In production those are
the same person, because there is exactly one.

**If there is no program manager at all, this does nothing and says so.** A
fabricated owner would be worse than an orphan: an orphan is visible to root and
obviously wrong, while a wrong owner is invisible to root and looks fine.
"""

from django.db import migrations


def backfill(apps, schema_editor):
    Leader = apps.get_model("matazim", "Leader")
    MemberProfile = apps.get_model("matazim", "MemberProfile")

    unowned = Leader.objects.filter(program_manager__isnull=True)
    if not unowned.exists():
        return

    # The earliest program manager: in production, נעמי, and the only one.
    fallback = (
        MemberProfile.objects.filter(is_program_manager=True)
        .order_by("first_seen_at")
        .values_list("user_id", flat=True)
        .first()
    )

    fixed = orphaned = 0
    for leader in unowned:
        # Whoever appointed them is the best available answer, and it is usually
        # the right one: `assigned_by` is set by the screen that creates leaders.
        owner_id = leader.assigned_by_id or fallback
        if owner_id is None:
            orphaned += 1
            continue
        leader.program_manager_id = owner_id
        leader.save(update_fields=["program_manager"])
        fixed += 1

    if fixed or orphaned:
        print(f"  matazim leaders: {fixed} given an owner, {orphaned} left orphaned")
    if orphaned:
        print("  (no program manager exists yet; grant one and re-run migrate)")


def unbackfill(apps, schema_editor):
    """Reversible, and harmless: 0011 drops the column anyway."""
    Leader = apps.get_model("matazim", "Leader")
    Leader.objects.update(program_manager=None)


class Migration(migrations.Migration):
    dependencies = [("matazim", "0011_leader_program_manager")]
    operations = [migrations.RunPython(backfill, unbackfill)]
