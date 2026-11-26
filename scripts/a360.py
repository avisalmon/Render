"""a360: the chat's hands on Academia360 (spec chapter 3.5).

A thin client of the app's REST API. It has no logic of its own: whatever it
can do, the API can do, with the same permissions and the same ChangeLog.

    python scripts/a360.py [--prod|--dev|--base URL] <command> [args]

    a360 routes                              every route the API offers
    a360 list institutions [--q k=v ...]     rows of a route (paged through)
    a360 get institutions 12                 one row
    a360 create researchers --data '{...}'   a row from JSON (or --file f.json)
    a360 update researchers 12 --data '{...}'
    a360 delete researchers 12
    a360 run start "deep research: Technion" [--sources "url1,url2"]   an AgentRun; prints its id
    a360 run finish 7 [--notes "..."]
    a360 grant committee someone@example.com / a360 grant leader someone@example.com --institution 3 [--title "..."]
    a360 revoke committee someone@example.com
    a360 import-json researchers --file rows.json --institution 3 [--run 7]   many rows, one per JSON object

Every write may carry --run <id> (lands in that AgentRun) and --reason "..."
(the source, kept in the ChangeLog). The token comes from the environment:
ACADEMIA360_AGENT_TOKEN. The base URL: --prod is https://babook.co.il,
--dev is http://127.0.0.1:8000, or --base.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

PROD = "https://babook.co.il"
DEV = "http://127.0.0.1:8000"


class Client:
    def __init__(self, base, token, run=None, reason=""):
        self.base = base.rstrip("/") + "/academia360/api/"
        self.token = token
        self.run = run
        self.reason = reason

    def call(self, method, path, data=None, params=None):
        url = self.base + path.lstrip("/")
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Accept", "application/json")
        if body is not None:
            req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        if self.run:
            req.add_header("X-A360-Run", str(self.run))
        if self.reason:
            req.add_header("X-A360-Reason", self.reason[:300].encode("ascii", "backslashreplace").decode("ascii"))
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
                return resp.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace")
            try:
                return exc.code, json.loads(raw)
            except json.JSONDecodeError:
                return exc.code, raw[:500]


def out(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def main(argv=None):
    p = argparse.ArgumentParser(prog="a360", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    where = p.add_mutually_exclusive_group()
    where.add_argument("--prod", action="store_true")
    where.add_argument("--dev", action="store_true")
    where.add_argument("--base")
    p.add_argument("--token", default=os.environ.get("ACADEMIA360_AGENT_TOKEN", ""))
    p.add_argument("--run", type=int)
    p.add_argument("--reason", default="")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("routes")

    def cmd(name, *positional, **options):
        s = sub.add_parser(name)
        for arg in positional:
            s.add_argument(arg)
        for flag, kwargs in options.items():
            s.add_argument("--" + flag.replace("_", "-"), **kwargs)
        return s

    cmd("list", "route", q={"nargs": "*", "default": []}, all={"action": "store_true"})
    cmd("get", "route", "pk")
    cmd("create", "route", data={}, file={})
    cmd("update", "route", "pk", data={}, file={})
    cmd("delete", "route", "pk")
    s = cmd("run", sources={"default": ""}, notes={"default": ""})
    s.add_argument("action", choices=["start", "finish"])
    s.add_argument("what")
    for name in ("grant", "revoke"):
        s = cmd(name, institution={"type": int}, title={"default": ""})
        s.add_argument("kind", choices=["committee", "leader", "admin", "chair", "reviewer"])
        s.add_argument("email")
    cmd("import-json", "route", file={"required": True}, institution={"type": int})
    a = p.parse_args(argv)

    base = PROD if a.prod else DEV if a.dev else (a.base or DEV)
    c = Client(base, a.token, run=a.run, reason=a.reason)

    def payload():
        if a.file:
            with open(a.file, encoding="utf-8") as fh:
                return json.load(fh)
        return json.loads(a.data or "{}")

    if a.cmd == "routes":
        status, data = c.call("GET", "")
        out(sorted(data) if isinstance(data, dict) else data)
    elif a.cmd == "list":
        params = dict(kv.split("=", 1) for kv in a.q)
        status, data = c.call("GET", f"{a.route}/", params=params)
        out(data)
    elif a.cmd == "get":
        status, data = c.call("GET", f"{a.route}/{a.pk}/")
        out(data)
    elif a.cmd == "create":
        status, data = c.call("POST", f"{a.route}/", data=payload())
        out({"status": status, "row": data})
    elif a.cmd == "update":
        status, data = c.call("PATCH", f"{a.route}/{a.pk}/", data=payload())
        out({"status": status, "row": data})
    elif a.cmd == "delete":
        status, data = c.call("DELETE", f"{a.route}/{a.pk}/")
        out({"status": status})
    elif a.cmd == "run":
        if a.action == "start":
            status, data = c.call("POST", "agentruns/", data={"purpose": a.what, "sources": a.sources.replace(",", "\n")})
            out({"status": status, "run": data.get("id") if isinstance(data, dict) else data})
        else:
            from datetime import datetime, timezone
            status, data = c.call("PATCH", f"agentruns/{a.what}/", data={
                "finished_at": datetime.now(timezone.utc).isoformat(), "notes": a.notes})
            out({"status": status, "run": data})
    elif a.cmd in ("grant", "revoke"):
        status, data = c.call("POST", "roles/grant/", data={
            "action": a.cmd, "kind": a.kind, "email": a.email, "institution": a.institution, "title": a.title})
        out({"status": status, "result": data})
    elif a.cmd == "import-json":
        with open(a.file, encoding="utf-8") as fh:
            rows = json.load(fh)
        results = []
        for row in rows:
            if a.institution and "institution" not in row:
                row["institution"] = a.institution
            status, data = c.call("POST", f"{a.route}/", data=row)
            results.append({"status": status, "id": data.get("id") if isinstance(data, dict) else None,
                            "error": None if status < 300 else data})
        ok = sum(1 for r in results if r["status"] < 300)
        out({"created": ok, "failed": len(results) - ok, "rows": results})
    return 0


if __name__ == "__main__":
    sys.exit(main())
