"""Generate the מט״צים entrance-test targets (F-10.12, spec §10.7 / REQ-10.25).

Offline on purpose. This command writes every target once and the output is
committed; the web process only ever *reads* a target and compares an upload
against it. That keeps geometry generation out of the request path entirely and,
just as usefully, means Avi and Litala can look at all of them before a single
applicant is shown one.

    python manage.py generate_matazim_targets            # 120 targets
    python manage.py generate_matazim_targets --count 40
    python manage.py generate_matazim_targets --check    # verify, write nothing

Output:
    static/matazim/targets/<id>.stl    the solid, for the 3D viewer
    static/matazim/targets/<id>.svg    the dimensioned drawing
    app/matazim_assets/targets/<id>.json   parameters + reference measurements

The JSON deliberately lives outside `static/`: it holds the reference volumes
the checker compares against, and there is no reason to serve the answer key.
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from app.matazim_geometry import measure
from app.matazim_targets import brief_lines, build, drawing_svg, sanity_check_all, stl_bytes

STATIC_DIR = Path(settings.BASE_DIR) / "static" / "matazim" / "targets"
DATA_DIR = Path(settings.BASE_DIR) / "app" / "matazim_assets" / "targets"


class Command(BaseCommand):
    help = "Generate the entrance-test target objects (STL + drawing + parameters)."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=120,
                            help="How many targets to generate (default 120).")
        parser.add_argument("--check", action="store_true",
                            help="Verify the generator without writing anything.")
        parser.add_argument("--force", action="store_true",
                            help="Rewrite targets that already exist.")

    def handle(self, *args, **opts):
        count = opts["count"]

        # Never ship a target that is not a sane closed solid: a broken one
        # would fail applicants who did nothing wrong.
        problems = sanity_check_all(count)
        if problems:
            for p in problems[:20]:
                self.stderr.write(f"  {p}")
            self.stderr.write(self.style.ERROR(
                f"{len(problems)} target(s) failed the sanity check. Nothing written."))
            return
        self.stdout.write(f"sanity check passed for {count} targets")

        if opts["check"]:
            self.stdout.write(self.style.SUCCESS("check only, nothing written"))
            return

        STATIC_DIR.mkdir(parents=True, exist_ok=True)
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        written = skipped = 0
        by_shape = {}
        for seed in range(count):
            target_id = f"t{seed:04d}"
            stl_path = STATIC_DIR / f"{target_id}.stl"
            if stl_path.exists() and not opts["force"]:
                skipped += 1
                continue

            tris, facts = build(seed)
            facts["id"] = target_id
            facts["brief"] = brief_lines(facts)
            by_shape[facts["shape"]] = by_shape.get(facts["shape"], 0) + 1

            stl_path.write_bytes(stl_bytes(tris, facts))
            (STATIC_DIR / f"{target_id}.svg").write_text(
                drawing_svg(facts), encoding="utf-8")
            (DATA_DIR / f"{target_id}.json").write_text(
                json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
            written += 1

        self.stdout.write(f"written: {written}   skipped (already there): {skipped}")
        for shape, n in sorted(by_shape.items()):
            self.stdout.write(f"  {shape}: {n}")

        # Report the spread, because a set where every target is a 30mm cube
        # would defeat the point of generating them at all.
        sizes = set()
        for seed in range(count):
            _, f = build(seed)
            sizes.add((f["shape"], f["width"], f["depth"], f["height"],
                       tuple(h["diameter"] for h in f["holes"])))
        self.stdout.write(f"distinct briefs: {len(sizes)} of {count}")

        sample = build(0)
        m = measure(sample[0])
        self.stdout.write(
            f"sample t0000: {sample[1]['title']} "
            f"{sample[1]['width']}x{sample[1]['depth']}x{sample[1]['height']}mm, "
            f"{m['triangles']} triangles, genus {m['genus']}")
        self.stdout.write(self.style.SUCCESS("generate_matazim_targets done"))
