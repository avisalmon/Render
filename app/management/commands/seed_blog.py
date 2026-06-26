"""Seed the personal blog (Avi Salmon Blog) on a fresh environment.

Runs on deploy (see render.yaml). Two idempotent steps:

1. Copy the committed blog media assets (covers, inline diagrams, the research
   PDF) from app/seed_assets/blog/ onto MEDIA_ROOT, because media/ lives on the
   persistent disk and is not in git.
2. Create the posts from app/seed_assets/blog_posts.json - but ONLY if the blog
   has no posts yet, so later edits made in prod (admin) are never clobbered.
"""
import json
import os
import shutil

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from app.models import BlogImage, BlogPost


class Command(BaseCommand):
    help = "Restore blog media assets and seed posts if the blog is empty."

    def handle(self, *args, **options):
        seed = os.path.join(settings.BASE_DIR, "app", "seed_assets")

        # 1) Ensure media assets are on the media disk.
        src_blog = os.path.join(seed, "blog")
        copied = 0
        if os.path.isdir(src_blog):
            for root, _dirs, files in os.walk(src_blog):
                for fn in files:
                    src = os.path.join(root, fn)
                    rel = os.path.relpath(src, seed)  # e.g. blog/gallery/x.svg
                    dst = os.path.join(settings.MEDIA_ROOT, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    if (not os.path.exists(dst)
                            or os.path.getsize(dst) != os.path.getsize(src)):
                        shutil.copy2(src, dst)
                        copied += 1
        self.stdout.write(f"blog assets ensured ({copied} copied)")

        # 2) Create any missing posts (matched by slug). Existing posts are left
        #    untouched, so edits made in prod are never overwritten; only posts
        #    that do not exist yet are added. To add a new post to prod, add it
        #    to blog_posts.json (+ its assets) and deploy.
        path = os.path.join(seed, "blog_posts.json")
        if not os.path.exists(path):
            self.stdout.write("no blog_posts.json; nothing to seed")
            return
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        author = (User.objects.filter(is_superuser=True).order_by("id").first()
                  or User.objects.order_by("id").first())

        created = 0
        for d in data:
            if BlogPost.objects.filter(slug=d["slug"]).exists():
                continue
            post = BlogPost(
                title=d["title"],
                subtitle=d.get("subtitle", ""),
                slug=d["slug"],
                excerpt=d.get("excerpt", ""),
                body=d.get("body", ""),
                tags=d.get("tags", []),
                cover=(d.get("cover") or None),
                status=d.get("status", "draft"),
                is_featured=d.get("is_featured", False),
                feature_order=d.get("feature_order", 0),
                author=author,
            )
            pub = d.get("published_at")
            if pub:
                post.published_at = parse_datetime(pub)
            post.save()
            for im in d.get("images", []):
                BlogImage.objects.create(
                    post=post,
                    image=im["image"],
                    key=im.get("key", ""),
                    alt=im.get("alt", ""),
                    caption=im.get("caption", ""),
                    order=im.get("order", 0),
                )
            created += 1
        self.stdout.write(f"seeded {created} blog posts")
