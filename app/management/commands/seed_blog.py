"""Seed the personal blog (Avi Salmon Blog) on a fresh environment.

Runs on deploy (see render.yaml). Two idempotent steps:

1. Copy the committed blog media assets (covers, inline diagrams, the research
   PDF) from app/seed_assets/blog/ onto MEDIA_ROOT, because media/ lives on the
   persistent disk and is not in git.
2. Sync posts from app/seed_assets/blog_posts.json: create missing slugs, leave
   existing ones untouched so prod-admin edits are never clobbered, EXCEPT posts
   flagged "managed": true, whose content is refreshed from JSON on every deploy
   (dev/JSON is the source of truth for them).
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

        # 2) Sync posts from blog_posts.json.
        #    - Missing slug: created.
        #    - Existing slug WITHOUT "managed": true: left untouched, so edits
        #      made in prod admin are never overwritten (the original design).
        #    - Existing slug WITH "managed": true: content fields are refreshed
        #      from JSON on every deploy (dev/JSON is the source of truth for it),
        #      while view_count and created_at are preserved. Mark a post managed
        #      when you want to keep editing it in dev and push those edits live.
        path = os.path.join(seed, "blog_posts.json")
        if not os.path.exists(path):
            self.stdout.write("no blog_posts.json; nothing to seed")
            return
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        author = (User.objects.filter(is_superuser=True).order_by("id").first()
                  or User.objects.order_by("id").first())

        created = 0
        updated = 0
        for d in data:
            existing = BlogPost.objects.filter(slug=d["slug"]).first()
            if existing and not d.get("managed"):
                continue  # never clobber a post edited in prod

            post = existing or BlogPost(slug=d["slug"], author=author)
            post.title = d["title"]
            post.subtitle = d.get("subtitle", "")
            post.excerpt = d.get("excerpt", "")
            post.body = d.get("body", "")
            post.tags = d.get("tags", [])
            post.cover = (d.get("cover") or None)
            post.status = d.get("status", "draft")
            post.is_featured = d.get("is_featured", False)
            post.feature_order = d.get("feature_order", 0)
            pub = d.get("published_at")
            if pub:
                post.published_at = parse_datetime(pub)
            if not post.author_id:
                post.author = author
            post.save()

            # Rebuild the gallery from JSON (safe: images are re-copied in step 1).
            post.images.all().delete()
            for im in d.get("images", []):
                BlogImage.objects.create(
                    post=post,
                    image=im["image"],
                    key=im.get("key", ""),
                    alt=im.get("alt", ""),
                    caption=im.get("caption", ""),
                    order=im.get("order", 0),
                )

            if existing:
                updated += 1
            else:
                created += 1
        self.stdout.write(f"seeded {created} blog posts, updated {updated} managed")
