"""What this repo knows that FullStackBKM does not (CLAUDE.md, "Every lesson
goes back to FullStackBKM").

Run it at every sprint end, and the pre-push hook runs it with --gate:

    .\\env\\Scripts\\python.exe scripts\\bkm_drift.py          # report
    .\\env\\Scripts\\python.exe scripts\\bkm_drift.py --gate   # exit 1 if blocked

It exists because the drift was invisible until somebody counted lines: on
2026-10-16 this repo's methodology document was 627 lines and
FullStackBKM's 198 (docs/postmortems.md, PM-12).

Four checks, from hard to soft:

1. **Post-mortems not landed.** Any `BKM: pending` in docs/postmortems.md.
   This is the only check that blocks a push.
2. **FullStackBKM not pushed.** Uncommitted changes, or commits not on
   GitHub. A lesson sitting on this laptop is not shared with anybody.
3. **Skills here and not there**, by folder name.
4. **Methodology headings here and not there.** Fuzzy on purpose: FullStackBKM
   words things in general terms, so a missing heading is a prompt to look,
   not proof of a gap.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
BKM = Path(r"C:\Projects\FullStuckBKM")  # old spelling on disk; GitHub is FullStackBKM
LEDGER = HERE / "docs" / "postmortems.md"


def pending_postmortems():
    if not LEDGER.exists():
        return []
    text = LEDGER.read_text(encoding="utf-8")
    out = []
    for block in re.split(r"\n(?=## PM-)", text):
        title = block.splitlines()[0].strip() if block.strip() else ""
        if not title.startswith("## PM-"):
            continue
        if re.search(r"^BKM:\s*pending\b", block, re.M):
            out.append(title[3:])
    return out


def _git(*args):
    return subprocess.run(
        ["git", "-C", str(BKM), *args], capture_output=True, text=True,
    ).stdout.strip()


def unpushed_bkm():
    if not (BKM / ".git").exists():
        return [f"FullStackBKM is not at {BKM}"]
    problems = []
    dirty = [l for l in _git("status", "--porcelain").splitlines() if l.strip()]
    if dirty:
        problems.append(f"{len(dirty)} uncommitted change(s) in FullStackBKM")
    _git("fetch", "--quiet", "origin")
    ahead = _git("rev-list", "--count", "origin/main..HEAD")
    if ahead and ahead != "0":
        problems.append(f"{ahead} FullStackBKM commit(s) not pushed")
    return problems


def missing_skills():
    here = {p.name for p in (HERE / ".claude" / "skills").iterdir() if p.is_dir()}
    there = {p.name for p in (BKM / ".claude" / "skills").iterdir() if p.is_dir()}
    return sorted(here - there)


def _norm(title):
    title = re.sub(r"^\d+\.\s*", "", title.strip())
    return re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()


def _headings(path):
    """Section titles, in either of the two shapes the documents use.

    FullStackBKM writes the lessons as a compact numbered list
    (`1. **A substring is not an assertion.**`) where this repo gives each
    one a heading. The first version of this check read only headings and
    reported all sixteen as missing when every one was there.
    """
    if not path.exists():
        return set()
    words = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## ") or line.startswith("### "):
            words.add(_norm(line.lstrip("#")))
        match = re.match(r"^\s*\d+\.\s+\*\*(.+?)\*\*", line)
        if match:
            words.add(_norm(match.group(1)))
    return {w for w in words if w}


def _close(title, others):
    """A title counts as present if most of its words are in one of the
    other document's titles, since FullStackBKM rewords for beginners."""
    mine = set(title.split())
    for other in others:
        theirs = set(other.split())
        if mine and len(mine & theirs) / len(mine) >= 0.6:
            return True
    return False


# Read by hand on 2026-10-16 and found in FullStackBKM under other words.
# Recorded with where they live, so they stop being reported: a report
# that repeats the same six non-problems every run stops being read.
ALREADY_THERE = {
    "data everything real becomes a model seeding is onetime only": "Rule 1 + 'Data: seeding is one-time only'",
    "interactivity a json api and fetch not fullpage form posts": "superseded by Rule 6 in both documents",
    "log every use with who and how": "'giving an agent a key', point 7",
    "namespace component classes or they will collide": "mistake 7",
    "testing exercise the real thing not just fixtures": "'Data: seeding is one-time only', the real-seed test",
    "the isolatedapp pattern": "Rules 2 and 3, kickoff scaffold, 'Error pages stay inside the app's walls'",
}


def missing_headings():
    here = _headings(HERE / "docs" / "building_an_app.md")
    there = _headings(BKM / "docs" / "building_an_app.md")
    return sorted(
        h for h in here
        if h not in there and not _close(h, there) and h not in ALREADY_THERE
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", action="store_true",
                        help="exit 1 if a post-mortem is pending (used by the pre-push hook)")
    args = parser.parse_args()

    pending = pending_postmortems()
    unpushed = unpushed_bkm()
    skills = missing_skills()
    headings = missing_headings()

    print("FullStackBKM drift")
    print("==================")
    print(f"\nPost-mortems not yet in FullStackBKM: {len(pending)}")
    for item in pending:
        print(f"  - {item}")
    print(f"\nFullStackBKM not pushed: {'no problems' if not unpushed else ''}")
    for item in unpushed:
        print(f"  - {item}")
    print(f"\nSkills here and not in FullStackBKM: {len(skills)}")
    for item in skills:
        print(f"  - {item}")
    print(f"\nMethodology headings here and not in FullStackBKM (look, may be worded differently): {len(headings)}")
    for item in headings:
        print(f"  - {item}")

    if args.gate and pending:
        print(
            "\nPush refused: post-mortems are pending. Land them in FullStackBKM and "
            "push it, then write the commit into each entry, or mark one "
            "'BKM: deferred - <reason>'."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
