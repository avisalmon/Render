"""Build docs/matazim/dashboard.html from the spec and the backlog.

REQ-M.141, `docs/building_an_app.md` Rule 4's third item.

**Generated, never hand-written, and that is the whole design.** A dashboard
somebody maintains by hand is a third copy of a truth that already lives in two
places, and the copy nobody is looking at is the one that goes wrong. This reads
`spec.md` and `backlog.md` and renders what they already say, so the only way to
change the dashboard is to change the thing it reports on.

`test_the_dashboard_is_current` regenerates it and compares, so a spec change
that nobody re-ran this after fails the suite rather than quietly leaving a
stale page in the repo.

    python manage.py matazim_dashboard          # write it
    python manage.py matazim_dashboard --check  # is it current
"""

import html
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

SPEC = Path(settings.BASE_DIR) / "docs" / "matazim" / "spec.md"
BACKLOG = Path(settings.BASE_DIR) / "docs" / "matazim" / "backlog.md"
OUT = Path(settings.BASE_DIR) / "docs" / "matazim" / "dashboard.html"

REQ_ROW = re.compile(
    r"^\| (REQ-M\.\d+[a-z]?) \| ([^|]+?) \|.*?\| (DONE|WIP|TODO|HELD|DROPPED) \|$",
    re.M,
)
SPRINT = re.compile(r"^## (SPR-M\.\d+) — ([^`]+?)\s+`([^`]+)`$", re.M)
SECTION = re.compile(r"^### (\d+\.\d+[a-z]?) (.+)$", re.M)

ORDER = ["WIP", "TODO", "HELD", "DONE", "DROPPED"]
TONE = {
    "DONE": "done",
    "WIP": "wip",
    "TODO": "todo",
    "HELD": "held",
    "DROPPED": "dropped",
}


def read():
    spec = SPEC.read_text(encoding="utf-8")
    backlog = BACKLOG.read_text(encoding="utf-8")

    # Which section each requirement sits under, so the page groups the way the
    # spec does rather than inventing its own arrangement.
    sections = [(m.start(), m.group(1), m.group(2)) for m in SECTION.finditer(spec)]

    def section_of(pos):
        found = ("", "")
        for start, number, title in sections:
            if start < pos:
                found = (number, title)
        return found

    reqs = []
    for m in REQ_ROW.finditer(spec):
        number, title = section_of(m.start())
        reqs.append(
            {
                "id": m.group(1),
                "title": m.group(2).strip(),
                "status": m.group(3),
                "section": f"{number} {title}".strip(),
                "sort": int(m.group(1).split(".")[1].rstrip("abcdefghij")),
            }
        )

    sprints = [
        {"id": m.group(1), "title": m.group(2).strip(), "state": m.group(3).strip()}
        for m in SPRINT.finditer(backlog)
    ]
    return reqs, sprints


def render(reqs, sprints):
    counts = {s: sum(1 for r in reqs if r["status"] == s) for s in ORDER}
    total = len(reqs)
    done = counts.get("DONE", 0)
    pct = round(done * 100 / total) if total else 0

    by_section = {}
    for r in sorted(reqs, key=lambda r: r["sort"]):
        by_section.setdefault(r["section"], []).append(r)

    def esc(text):
        return html.escape(text, quote=True)

    cards = []
    for section, rows in by_section.items():
        items = "\n".join(
            f'      <li class="{TONE[r["status"]]}">'
            f'<span class="id">{esc(r["id"])}</span> {esc(r["title"])}'
            f'<span class="pill">{r["status"]}</span></li>'
            for r in rows
        )
        cards.append(
            f'    <section class="card">\n'
            f"      <h2>{esc(section)}</h2>\n"
            f'      <ul class="reqs">\n{items}\n      </ul>\n'
            f"    </section>"
        )

    sprint_rows = "\n".join(
        f'      <li><span class="id">{esc(s["id"])}</span> {esc(s["title"])}'
        f'<span class="pill">{esc(s["state"])}</span></li>'
        for s in sprints
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>מט״צים — progress</title>
<style>
  :root {{
    --bg: #0d1117; --card: #161b22; --border: #30363d;
    --text: #e6edf3; --muted: #8b949e;
    --done: #3fb950; --wip: #d29922; --todo: #58a6ff;
    --held: #a371f7; --dropped: #6e7681;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px;
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
    background: var(--bg); color: var(--text);
  }}
  h1 {{ margin: 0 0 4px; font-size: 24px; }}
  .sub {{ color: var(--muted); margin-bottom: 20px; font-size: 14px; }}
  .bar {{
    height: 10px; border-radius: 5px; background: #21262d;
    overflow: hidden; margin-bottom: 8px; max-width: 640px;
  }}
  .bar > span {{ display: block; height: 100%; background: var(--done); width: {pct}%; }}
  .tally {{ color: var(--muted); font-size: 13px; margin-bottom: 24px; }}
  .tally b {{ color: var(--text); }}
  .grid {{
    display: grid; gap: 16px;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  }}
  .card {{
    background: var(--card); border: 1px solid var(--border);
    border-radius: 8px; padding: 16px;
  }}
  .card h2 {{ margin: 0 0 10px; font-size: 15px; color: var(--muted); font-weight: 600; }}
  ul {{ list-style: none; margin: 0; padding: 0; }}
  li {{
    display: flex; align-items: baseline; gap: 8px;
    padding: 5px 0; font-size: 13px; line-height: 1.4;
    border-top: 1px solid var(--border);
  }}
  li:first-child {{ border-top: 0; }}
  .id {{
    font-family: ui-monospace, monospace; font-size: 11px;
    color: var(--muted); flex: none;
  }}
  .pill {{
    margin-inline-start: auto; flex: none; font-size: 10px;
    letter-spacing: .04em; padding: 1px 6px; border-radius: 9px;
    border: 1px solid currentColor;
  }}
  li.done .pill {{ color: var(--done); }}
  li.wip .pill {{ color: var(--wip); }}
  li.todo .pill {{ color: var(--todo); }}
  li.held .pill {{ color: var(--held); }}
  li.dropped .pill, li.dropped {{ color: var(--dropped); }}
  footer {{ margin-top: 28px; color: var(--muted); font-size: 12px; max-width: 640px; }}
</style>
</head>
<body>

<h1>מט״צים</h1>
<p class="sub">
  Generated from <code>spec.md</code> and <code>backlog.md</code> by
  <code>manage.py matazim_dashboard</code>. Do not edit this file.
</p>

<div class="bar"><span></span></div>
<p class="tally">
  <b>{done}</b> of <b>{total}</b> requirements done ({pct}%) &middot;
  {counts.get("WIP", 0)} in progress &middot;
  {counts.get("TODO", 0)} to do &middot;
  {counts.get("HELD", 0)} held &middot;
  {counts.get("DROPPED", 0)} dropped
</p>

<div class="grid">
{chr(10).join(cards)}
    <section class="card">
      <h2>Sprints</h2>
      <ul>
{sprint_rows}
      </ul>
    </section>
</div>

<footer>
  A held requirement is waiting on a decision, not on work. A dropped one was
  deliberately retired and the spec says why. This page reports; it never
  decides. If a status here looks wrong, the spec is where to change it.
</footer>

</body>
</html>
"""


class Command(BaseCommand):
    help = "Build docs/matazim/dashboard.html from the spec and backlog (REQ-M.141)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Exit non-zero if the file on disk is not what would be written.",
        )

    def handle(self, *args, **options):
        reqs, sprints = read()
        page = render(reqs, sprints)

        if options["check"]:
            current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
            if current != page:
                self.stderr.write("dashboard is stale: run manage.py matazim_dashboard")
                raise SystemExit(1)
            self.stdout.write("dashboard is current")
            return

        OUT.write_text(page, encoding="utf-8", newline="\n")
        self.stdout.write(
            self.style.SUCCESS(
                f"wrote {OUT.name}: {len(reqs)} requirements, {len(sprints)} sprints"
            )
        )
