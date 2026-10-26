"""Avi's BKMs, managed from the chat (REQ-B.20, B.21). Nobody adds BKMs
through a screen.

    manage.py bkm list
    manage.py bkm add <repo-url> [--slug S] [--name N] [--tagline T] [--page-url U] [--picture FILE]
    manage.py bkm set <slug> <field> <value>      (name, tagline, repo_url, page_url, position)
    manage.py bkm picture <slug> <file>
    manage.py bkm hide <slug> | show <slug> | remove <slug>

`add` fills name, tagline and the Pages address from GitHub once; after
that the row is the truth. For production a new BKM goes in by a data
migration plus its picture in bkm/seed_assets/<slug>.jpg (seed_bkm attaches
it), so the deploy carries it.
"""

import json
import re
import urllib.request
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Max
from django.utils.text import slugify

from bkm.models import Bkm
from bkm.seed import RESERVED

FIELDS = {"name", "tagline", "repo_url", "page_url", "position"}


def github_facts(repo_url):
    """name, description and Pages address of a public GitHub repo."""
    m = re.match(r"https?://github\.com/([^/]+)/([^/#?]+)", repo_url.strip())
    if not m:
        raise CommandError("That is not a GitHub repository link.")
    owner, repo = m.group(1), m.group(2).removesuffix(".git")
    req = urllib.request.Request(f"https://api.github.com/repos/{owner}/{repo}", headers={"User-Agent": "babook-bkm"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.load(r)
    page = d.get("homepage") or (f"https://{owner}.github.io/{repo}/" if d.get("has_pages") else "")
    return {"name": d.get("name") or repo, "tagline": (d.get("description") or "")[:160],
            "page_url": page, "repo_url": d.get("html_url") or repo_url}


class Command(BaseCommand):
    help = "List, add and change the BKMs on the wall."

    def add_arguments(self, parser):
        parser.add_argument("verb", choices=["list", "add", "set", "picture", "hide", "show", "remove"])
        parser.add_argument("rest", nargs="*")
        parser.add_argument("--slug")
        parser.add_argument("--name")
        parser.add_argument("--tagline")
        parser.add_argument("--page-url")
        parser.add_argument("--picture")

    def handle(self, verb, rest, **o):
        getattr(self, f"do_{verb}")(rest, o)

    def _get(self, slug):
        try:
            return Bkm.objects.get(slug=slug)
        except Bkm.DoesNotExist:
            raise CommandError(f"No BKM called {slug}.")

    def _picture(self, bkm, path):
        p = Path(path)
        if not p.exists():
            raise CommandError(f"No file at {path}.")
        with p.open("rb") as fh:
            bkm.picture.save(f"{bkm.slug}.jpg", File(fh), save=True)

    def do_list(self, rest, o):
        for b in Bkm.objects.all():
            self.stdout.write(f"{b.position:>4}  {b.slug:<24} {'on ' if b.is_published else 'off'}  {b.name}  {b.page_url}")

    def do_add(self, rest, o):
        if len(rest) != 1:
            raise CommandError("bkm add <repo-url>")
        facts = github_facts(rest[0])
        slug = o["slug"] or slugify(facts["name"].removesuffix("BKM")) or slugify(facts["name"])
        if slug in RESERVED:
            raise CommandError(f"{slug} is a reserved address; pass --slug.")
        if Bkm.objects.filter(slug=slug).exists():
            raise CommandError(f"There is already a BKM called {slug}.")
        page = o["page_url"] or facts["page_url"]
        if not page:
            raise CommandError("This repo has no GitHub Pages page yet; pass --page-url.")
        top = Bkm.objects.aggregate(m=Max("position"))["m"] or 0
        b = Bkm.objects.create(slug=slug, name=o["name"] or facts["name"], tagline=o["tagline"] or facts["tagline"],
                               repo_url=facts["repo_url"], page_url=page, position=top + 10)
        if o["picture"]:
            self._picture(b, o["picture"])
        self.stdout.write(f"Added {b.slug}: {b.name}")

    def do_set(self, rest, o):
        if len(rest) != 3 or rest[1] not in FIELDS:
            raise CommandError(f"bkm set <slug> <{'|'.join(sorted(FIELDS))}> <value>")
        b = self._get(rest[0])
        setattr(b, rest[1], int(rest[2]) if rest[1] == "position" else rest[2])
        b.full_clean()
        b.save()
        self.stdout.write(f"{b.slug}: {rest[1]} set")

    def do_picture(self, rest, o):
        if len(rest) != 2:
            raise CommandError("bkm picture <slug> <file>")
        self._picture(self._get(rest[0]), rest[1])
        self.stdout.write("Picture set")

    def do_hide(self, rest, o):
        self._published(rest, False)

    def do_show(self, rest, o):
        self._published(rest, True)

    def _published(self, rest, on):
        if len(rest) != 1:
            raise CommandError("bkm hide|show <slug>")
        b = self._get(rest[0])
        b.is_published = on
        b.save(update_fields=["is_published", "updated_at"])
        self.stdout.write(f"{b.slug} is {'on the wall' if on else 'hidden'}")

    def do_remove(self, rest, o):
        if len(rest) != 1:
            raise CommandError("bkm remove <slug>")
        self._get(rest[0]).delete()
        self.stdout.write("Removed")
