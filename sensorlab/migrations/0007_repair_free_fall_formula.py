"""Repair the Free Fall formula — but only where nobody has touched it.

SL-B3's seed is a one-time import: once the lab exists it belongs to the
database, not to the seed file. That rule is what protects an author's edits
from being flattened on every deploy, and it also means **fixing the seed
source fixes nothing that is already installed**.

SL-D2 found such a thing by looking at the rendered Learn step. The formula
read `aₓ² + a_y² + a_z²`: a Unicode subscript for x and plain underscores for
y and z, because Unicode has no subscript y or z. Formula blocks are literal
by design (Markdown would read `_` as emphasis), so that mixture is exactly
what a student saw, and it is visibly wrong to anyone reading the physics.

So this migration repairs it — **conditionally**. It rewrites the block only
if the body is still character-for-character what the seed wrote. If anybody
has edited it, theirs is the version that stands and this does nothing. The
seed's promise and this repair have to agree, or the promise is worth less
than it looks.
"""

from django.db import migrations

BROKEN = "|a| = √(aₓ² + a_y² + a_z²)"
FIXED = "|a| = √(a_x² + a_y² + a_z²)"


def repair(apps, schema_editor):
    ContentBlock = apps.get_model("sensorlab", "ContentBlock")
    for field in ("body_en", "body_he"):
        ContentBlock.objects.filter(
            kind="formula", lab__slug="measuring-g", **{field: BROKEN}
        ).update(**{field: FIXED})


def unrepair(apps, schema_editor):
    """Deliberately a no-op.

    Reversing a migration should not put a known-wrong string back into
    somebody's course. There is nothing to restore here — the old text was
    a typo, not a decision.
    """


class Migration(migrations.Migration):
    dependencies = [("sensorlab", "0006_labattempt")]
    operations = [migrations.RunPython(repair, unrepair)]
