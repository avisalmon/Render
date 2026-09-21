"""Day-one content for exo — imported ONCE, never re-imported.

This runs on **every deploy** (render.yaml), which is only safe because of the
rule it follows: *check whether the row exists, and if it does, leave it
completely alone and say so.*

That rule is not caution, it is the scar from ustrip (building_an_app.md,
"Data: everything real becomes a model"). A seed command wired into the start
command was wholesale-deleting and recreating rows from a static file on every
push. The moment a real person edited one of those rows, the next deploy would
silently destroy their edit and restore a stale snapshot. Here, Avi edits a
principle's summary in admin and it survives every deploy after, forever.

`tests/test_exo_foundation.py` runs this command twice with an edit in
between and asserts the edit is still there. A test that only checks the first
run would not catch the bug this rule exists to prevent.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from exo.models import ExoAttribute, LearnResource, NewspaperStyle
from exo.seed.content import ATTRIBUTES, LEARN_PAGES, STYLES
from exo.seed.handout import ATTRIBUTE_BODIES


class Command(BaseCommand):
    help = "Seed exo's reference content once. Never overwrites existing rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--quiet", action="store_true",
            help="only report totals, not every row left alone",
        )

    def handle(self, *args, **options):
        quiet = options.get("quiet")
        created, left = 0, 0

        def note(message):
            if not quiet:
                self.stdout.write(message)

        with transaction.atomic():
            for spec in ATTRIBUTES:
                _, was_created = self._ensure(ExoAttribute, spec["key"], spec)
                if was_created:
                    created += 1
                    note(f"  + attribute {spec['key']}")
                else:
                    left += 1
                    note(f"  = attribute {spec['key']} already exists — left alone")

            # One editable summary page per attribute, so the handout has a row
            # Avi can rewrite without touching code. Seeded from the attribute's
            # own definition purely as a starting point.
            for spec in ATTRIBUTES:
                attribute = ExoAttribute.objects.filter(key=spec["key"]).first()
                if attribute is None:
                    continue
                # The handout copy, with the attribute's own definition as
                # the fallback: a new attribute added later still gets a page
                # that says something rather than an empty one.
                body = ATTRIBUTE_BODIES.get(spec["key"], {})
                page = {
                    "attribute": attribute,
                    "order": spec["order"],
                    "title_en": spec["name_en"],
                    "title_he": spec["name_he"],
                    "body_en": body.get("body_en") or spec["short_def_en"],
                    "body_he": body.get("body_he") or spec["short_def_he"],
                }
                _, was_created = self._ensure(
                    LearnResource, f"attr-{spec['key']}", page,
                )
                if was_created:
                    created += 1
                    note(f"  + learn page attr-{spec['key']}")
                else:
                    left += 1
                    note(f"  = learn page attr-{spec['key']} already exists — left alone")

            for spec in LEARN_PAGES:
                _, was_created = self._ensure(LearnResource, spec["key"], spec)
                if was_created:
                    created += 1
                    note(f"  + learn page {spec['key']}")
                else:
                    left += 1
                    note(f"  = learn page {spec['key']} already exists — left alone")

            for spec in STYLES:
                _, was_created = self._ensure(NewspaperStyle, spec["key"], spec)
                if was_created:
                    created += 1
                    note(f"  + style {spec['key']}")
                else:
                    left += 1
                    note(f"  = style {spec['key']} already exists — left alone")

        self.stdout.write(self.style.SUCCESS(
            f"exo seed: {created} created, {left} left untouched."
        ))

    @staticmethod
    def _ensure(model, key, spec):
        """Create the row if its key is absent; otherwise touch nothing.

        Deliberately not `update_or_create`: that is exactly the call that
        destroys a person's edit on the next deploy.
        """
        existing = model.objects.filter(key=key).first()
        if existing is not None:
            return existing, False
        fields = {k: v for k, v in spec.items() if k != "key"}
        return model.objects.create(key=key, **fields), True
