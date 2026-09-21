"""Replace the Free Fall Learn step with the derivation (SL-M1).

SL-B3's seed is a one-time import: once the lab exists, it belongs to the
database and the seed never touches it again. That rule protects an author's
edits — and it means **rewriting the seed rewrites nothing already
installed**, including production, where the old three-paragraph Learn step
is what a student reads today.

So this migration does it, under the same condition `0007` used: it only
replaces blocks whose text is still character-for-character what the seed
wrote. If anybody has edited a block, theirs stands and this leaves it
alone. The seed's promise and this repair have to agree, or the promise is
worth less than it looks.

Unlike `0007`, which fixed a typo in place, this **restructures** the step:
three blocks become six, and the old ones are removed. That is a bigger
intervention, so the condition is stricter — every one of the three original
blocks must be untouched. If even one has been edited, the whole rewrite is
skipped and the step is left as it stands, because a course half in one
voice and half in another is worse than an old explanation.
"""

from django.db import migrations

LAB = "measuring-g"

#: Exactly what SL-B3 seeded, as of migration 0007. Matched in full.
OLD_TEXT_EN = (
    "The accelerometer reports **proper acceleration**: what its own "
    "springs feel.\n\n"
    "Lying still on a table, your phone is not accelerating anywhere "
    "— and yet the table is pushing up on it hard enough to hold it "
    "against gravity. The springs feel that push. So a phone at rest "
    "reads the full strength of gravity, pointing up.\n\n"
    "Now take the table away."
)
OLD_FORMULA_EN = "|a| = √(a_x² + a_y² + a_z²)"
OLD_CALLOUT_START = "Your phone does not know which way up it is being held"


def rewrite(apps, schema_editor):
    ContentBlock = apps.get_model("sensorlab", "ContentBlock")
    Lab = apps.get_model("sensorlab", "Lab")

    lab = Lab.objects.filter(slug=LAB).first()
    if lab is None:
        return  # Nothing seeded here yet; the seed itself will write the new text.

    blocks = list(ContentBlock.objects.filter(lab=lab, step="learn").order_by("order"))
    untouched = (
        len(blocks) == 3
        and blocks[0].body_en == OLD_TEXT_EN
        and blocks[1].body_en == OLD_FORMULA_EN
        and blocks[2].body_en.startswith(OLD_CALLOUT_START)
    )
    if not untouched:
        return  # Somebody has been editing. Theirs stands.

    from sensorlab.management.commands.seed_sensorlab import BLOCKS

    ContentBlock.objects.filter(lab=lab, step="learn").delete()
    for block in BLOCKS:
        if block["step"] != "learn":
            continue
        ContentBlock.objects.create(lab=lab, **block)


def unrewrite(apps, schema_editor):
    """A no-op, deliberately.

    Reversing this would put a thinner explanation back into somebody's
    course. There is nothing to restore — the old text was not a decision
    anybody wants back.
    """


class Migration(migrations.Migration):
    dependencies = [("sensorlab", "0010_analysisresult")]
    operations = [migrations.RunPython(rewrite, unrewrite)]
