"""Builds docs/improv/dashboard.html from docs/improv/backlog.md.

    env/Scripts/python.exe docs/improv/build_dashboard.py

The dashboard is never edited by hand. tests/test_spri_1_5.py fails when the file
on disk differs from what this script makes from the backlog, so a backlog change
without a regenerated dashboard is a red test, not a stale page.

Standard library only, and nothing in the page depends on anything off the page.
"""

import html
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
BACKLOG = HERE / "backlog.md"
DASHBOARD = HERE / "dashboard.html"

EPIC = re.compile(r"^## (EPIC-I\.\d+): (.+?)\s+`([A-Z ]+)`\s*$")
SPRINT = re.compile(r"^\| (SPR-I\.\d+\.\d+) \|")
CELL_SPLIT = re.compile(r"(?<!\\)\|")


def parse(text):
    epics = []
    epic = None
    goal = None
    for line in text.splitlines():
        match = EPIC.match(line)
        if match:
            epic = {"id": match.group(1), "title": match.group(2), "header_status": match.group(3), "goal": "", "sprints": []}
            epics.append(epic)
            goal = None
            continue
        if epic is None:
            continue
        if line.startswith("**Goal:**"):
            goal = [line[len("**Goal:**"):].strip()]
            continue
        if goal is not None:
            if line.strip():
                goal.append(line.strip())
                continue
            epic["goal"] = " ".join(goal)
            goal = None
        if SPRINT.match(line):
            cells = [c.strip().replace("\\|", "|") for c in CELL_SPLIT.split(line.strip().strip("|"))]
            sprint_id, what, traces, status = cells[0], cells[1], cells[2], cells[3]
            epic["sprints"].append(
                {
                    "id": sprint_id,
                    "what": what,
                    "traces": traces,
                    "status": status,
                    "at_piano": bool(re.match(r"\*\*[^*]*at the piano", what, flags=re.I)),
                }
            )
    for epic in epics:
        epic["status"] = _epic_status(epic["sprints"])
    return epics


def _epic_status(sprints):
    states = [s["status"].startswith("DONE") for s in sprints]
    if sprints and all(states):
        return "DONE"
    if any(states) or any(s["status"] == "IN PROGRESS" for s in sprints):
        return "IN PROGRESS"
    return "TODO"


def summarise(epics):
    sprints = [s for e in epics for s in e["sprints"]]
    done = sum(1 for s in sprints if s["status"].startswith("DONE"))
    return {
        "total": len(sprints),
        "done": done,
        "in_progress": sum(1 for s in sprints if s["status"] == "IN PROGRESS"),
        "at_piano_left": sum(1 for s in sprints if s["at_piano"] and not s["status"].startswith("DONE")),
        "epics_done": sum(1 for e in epics if e["status"] == "DONE"),
        "epics": len(epics),
    }


def inline(text):
    out = html.escape(text, quote=False)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", out)
    return out


def _badge(status):
    kind = "done" if status.startswith("DONE") else "wip" if status == "IN PROGRESS" else "todo"
    return f'<span class="badge {kind}">{html.escape(status)}</span>'


def _percent(done, total):
    return round(100 * done / total) if total else 0


def render(backlog_text):
    epics = parse(backlog_text)
    total = summarise(epics)
    parts = []
    for epic in epics:
        done = sum(1 for s in epic["sprints"] if s["status"].startswith("DONE"))
        count = len(epic["sprints"])
        rows = []
        for s in epic["sprints"]:
            piano = '<span class="piano">needs Avi at the piano</span>' if s["at_piano"] else ""
            rows.append(
                f'<tr class="{"done" if s["status"].startswith("DONE") else ""}">'
                f'<td class="id">{html.escape(s["id"])}</td>'
                f'<td>{inline(s["what"])}{piano}</td>'
                f'<td class="status">{_badge(s["status"])}</td></tr>'
            )
        goal = f'<p class="goal">{inline(epic["goal"])}</p>' if epic["goal"] else ""
        parts.append(
            f'<section class="epic">'
            f'<h2><span>{html.escape(epic["id"])}</span> {html.escape(epic["title"])} {_badge(epic["status"])}</h2>'
            f'{goal}'
            f'<div class="bar" title="{done} of {count} sprints done"><i style="width:{_percent(done, count)}%"></i></div>'
            f'<div class="table-wrap"><table>{"".join(rows)}</table></div></section>'
        )

    left = total["at_piano_left"]
    piano_note = (
        f'<p class="note">{left} sprint{"s" if left != 1 else ""} still need Avi at his piano: '
        "MIDI and timing cannot be accepted from a chat.</p>"
        if left
        else ""
    )
    return f"""<!doctype html>
<html lang="en" dir="ltr">
<head>
<meta charset="utf-8">
<title>improv dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root {{ --bg:#f7f7f4; --card:#fff; --ink:#1d2330; --soft:#5d6577; --line:#dfe1e6; --done:#1f7a4d; --done-bg:#e3f3ea; --wip:#9a6a00; --wip-bg:#fbefd0; --todo:#5d6577; --todo-bg:#eceef2; --accent:#3b5bdb; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#14171f; --card:#1c212c; --ink:#e8eaf0; --soft:#9aa3b5; --line:#2c3342; --done:#5fcf95; --done-bg:#1b3a2b; --wip:#f0c25a; --wip-bg:#3a3014; --todo:#9aa3b5; --todo-bg:#262c3a; --accent:#7c93f5; }} }}
* {{ box-sizing: border-box; }}
body {{ margin:0; padding:28px 16px 60px; background:var(--bg); color:var(--ink); font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
.wrap {{ max-width:920px; margin:0 auto; }}
h1 {{ font-size:26px; margin:0 0 4px; }}
.sub {{ color:var(--soft); margin:0 0 22px; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:12px; margin-bottom:12px; }}
.stat {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px 14px; }}
.stat b {{ display:block; font-size:24px; font-variant-numeric:tabular-nums; }}
.stat span {{ color:var(--soft); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
.note {{ color:var(--soft); margin:0 0 20px; }}
.epic {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:16px; margin:0 0 16px; }}
.epic h2 {{ font-size:17px; margin:0 0 6px; display:flex; flex-wrap:wrap; gap:8px; align-items:center; }}
.epic h2 span:first-child {{ color:var(--accent); font-size:13px; }}
.goal {{ color:var(--soft); margin:0 0 10px; }}
.bar {{ height:6px; background:var(--todo-bg); border-radius:3px; overflow:hidden; margin:0 0 10px; }}
.bar i {{ display:block; height:100%; background:var(--done); }}
.table-wrap {{ overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; }}
td {{ padding:8px 6px; border-top:1px solid var(--line); vertical-align:top; }}
td.id {{ white-space:nowrap; color:var(--soft); font-variant-numeric:tabular-nums; }}
td.status {{ white-space:nowrap; text-align:right; }}
tr.done td:nth-child(2) {{ color:var(--soft); }}
code {{ background:var(--todo-bg); padding:1px 5px; border-radius:4px; font-size:12.5px; }}
.badge {{ font-size:11px; font-weight:600; padding:2px 8px; border-radius:99px; letter-spacing:.03em; }}
.badge.done {{ background:var(--done-bg); color:var(--done); }}
.badge.wip {{ background:var(--wip-bg); color:var(--wip); }}
.badge.todo {{ background:var(--todo-bg); color:var(--todo); }}
.piano {{ display:inline-block; margin-left:8px; font-size:11px; font-weight:600; color:var(--wip); background:var(--wip-bg); padding:1px 8px; border-radius:99px; }}
.foot {{ color:var(--soft); font-size:12px; margin-top:24px; }}
</style>
</head>
<body>
<div class="wrap">
<h1>improv</h1>
<p class="sub">Piano improvisation practice. Delivery status of the build.</p>
<div class="stats" data-done="{total["done"]}" data-total="{total["total"]}">
<div class="stat"><b>{total["done"]} / {total["total"]}</b><span>sprints done</span></div>
<div class="stat"><b>{_percent(total["done"], total["total"])}%</b><span>of the backlog</span></div>
<div class="stat"><b>{total["epics_done"]} / {total["epics"]}</b><span>epics done</span></div>
<div class="stat"><b>{left}</b><span>need the piano</span></div>
</div>
{piano_note}
{"".join(parts)}
<p class="foot">Generated from backlog.md. Do not edit by hand: run docs/improv/build_dashboard.py. A test fails when this page and the backlog disagree.</p>
</div>
</body>
</html>
"""


def main():
    DASHBOARD.write_text(render(BACKLOG.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    print(f"wrote {DASHBOARD}")


if __name__ == "__main__":
    sys.exit(main())
