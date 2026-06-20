"""
Management command: import_youtube_course

Downloads a YouTube playlist (that you own) and imports it as a babook Course.

Steps per video:
  1. yt-dlp fetches playlist metadata (titles, durations, IDs)
  2. yt-dlp downloads each video as MP4 to a temp dir
  3. Bunny Stream API creates a video slot (returns GUID)
  4. MP4 is uploaded to Bunny
  5. Video model record is created in DB

Usage:
  python manage.py import_youtube_course <playlist_url> \\
      --title "Course Title" \\
      --slug "course-slug" \\
      [--description "..."] \\
      [--free-previews 1] \\
      [--dry-run]
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from app.models import Course, Video

BUNNY_API_BASE = "https://video.bunnycdn.com/library"


class Command(BaseCommand):
    help = "Import a YouTube playlist you own as a babook Course via Bunny Stream."

    def add_arguments(self, parser):
        parser.add_argument("playlist_url", help="YouTube playlist URL")
        parser.add_argument("--title", required=True, help="Course title (Hebrew or English)")
        parser.add_argument("--slug", help="URL slug (auto-generated from title if omitted)")
        parser.add_argument("--description", default="", help="Course description")
        parser.add_argument(
            "--free-previews",
            type=int,
            default=1,
            dest="free_previews",
            help="Number of lessons (from lesson 1) to mark as free preview (default: 1)",
        )
        parser.add_argument(
            "--order-offset",
            type=int,
            default=0,
            dest="order_offset",
            help="Add this to each playlist index so several playlists concatenate "
            "into one course with continuous numbering (e.g. 0, then 10, then 15).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch metadata only - no downloads, no uploads, no DB writes",
        )

    def handle(self, *args, **options):
        playlist_url = options["playlist_url"]
        title = options["title"]
        slug = options["slug"] or slugify(title)
        description = options["description"]
        free_previews = options["free_previews"]
        order_offset = options["order_offset"]
        dry_run = options["dry_run"]

        api_key = getattr(settings, "BUNNY_API_KEY", "")
        library_id = getattr(settings, "BUNNY_STREAM_LIBRARY_ID", "")
        if not api_key or not library_id:
            raise CommandError("BUNNY_API_KEY or BUNNY_STREAM_LIBRARY_ID not set.")

        # Only route through a proxy if one is actually configured. (On the Intel
        # network HTTP_PROXY is set; off it, going direct is correct and the old
        # hard-coded proxy fallback would break Bunny uploads.)
        http_proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
        self._proxies = {"http": http_proxy, "https": http_proxy} if http_proxy else None

        self.stdout.write(self.style.MIGRATE_HEADING("Fetching playlist metadata…"))
        videos = self._fetch_playlist_metadata(playlist_url)
        if not videos:
            raise CommandError("No videos found in playlist.")

        # Absolute lesson number = playlist index + offset (lets several
        # playlists concatenate into one continuously-numbered course).
        for v in videos:
            v["order"] = v["index"] + order_offset

        self.stdout.write(f"Found {len(videos)} videos:\n")
        for v in videos:
            free_tag = " [FREE PREVIEW]" if v["order"] <= free_previews else ""
            self.stdout.write(f"  {v['order']:>3}. {v['title']} ({v['duration_str']}){free_tag}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run - stopping here. No data written."))
            return

        # Create or get Course
        course, created = Course.objects.get_or_create(
            slug=slug,
            defaults={"title": title, "description": description},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"\nCreated Course: '{course.title}' (slug={slug})"))
        else:
            self.stdout.write(self.style.WARNING(f"\nCourse already exists: '{course.title}' - adding/skipping videos."))

        with tempfile.TemporaryDirectory() as tmpdir:
            for video_meta in videos:
                idx = video_meta["order"]
                yt_id = video_meta["id"]
                yt_title = video_meta["title"]
                duration = video_meta["duration_seconds"]
                is_free = idx <= free_previews

                self.stdout.write(f"\n[{idx}/{len(videos)}] {yt_title}")

                # Skip if a Video record already exists for this course/order
                if Video.objects.filter(course=course, lesson_order=idx).exists():
                    self.stdout.write(self.style.WARNING(f"  Already imported (lesson {idx}) - skipping."))
                    continue

                # Download video
                mp4_path = self._download_video(yt_id, tmpdir, idx)
                if not mp4_path:
                    self.stdout.write(self.style.ERROR("  Download failed - skipping."))
                    continue

                # Upload to Bunny
                bunny_guid = self._upload_to_bunny(mp4_path, yt_title, api_key, library_id)
                if not bunny_guid:
                    self.stdout.write(self.style.ERROR("  Bunny upload failed - skipping."))
                    os.remove(mp4_path)
                    continue

                # Create DB record
                Video.objects.create(
                    course=course,
                    bunny_video_id=bunny_guid,
                    title=yt_title,
                    duration_seconds=duration,
                    lesson_order=idx,
                    is_free_preview=is_free,
                )
                self.stdout.write(
                    self.style.SUCCESS(f"  Done - bunny_guid={bunny_guid}, free_preview={is_free}")
                )

                # Clean up local MP4 immediately to save disk
                try:
                    os.remove(mp4_path)
                except OSError:
                    pass

        count = Video.objects.filter(course=course).count()
        self.stdout.write(
            self.style.SUCCESS(f"\nImport complete. Course '{title}' has {count} lessons.")
        )
        self.stdout.write(f"  URL: /courses/{slug}/")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fetch_playlist_metadata(self, url):
        """Use yt-dlp to list all videos in a playlist (no download)."""
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--flat-playlist",
            "--print", "%(playlist_index)s\t%(id)s\t%(title)s\t%(duration)s",
            url,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise CommandError(f"yt-dlp metadata fetch failed:\n{e.stderr}")

        videos = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            idx_str, yt_id, title, dur_str = parts[0], parts[1], parts[2], parts[3]
            try:
                idx = int(idx_str)
            except ValueError:
                continue
            try:
                duration = int(float(dur_str))
            except (ValueError, TypeError):
                duration = 0
            minutes, seconds = divmod(duration, 60)
            duration_str = f"{minutes}:{seconds:02d}" if duration else "?"
            videos.append({
                "index": idx,
                "id": yt_id,
                "title": title,
                "duration_seconds": duration,
                "duration_str": duration_str,
            })

        return videos

    def _download_video(self, yt_id, tmpdir, idx):
        """Download a single YouTube video as MP4. Returns the local file path or None."""
        out_template = os.path.join(tmpdir, f"{idx:03d}_%(id)s.%(ext)s")
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", out_template,
            f"https://www.youtube.com/watch?v={yt_id}",
        ]
        self.stdout.write("  Downloading…")
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            self.stderr.write(e.stderr.decode(errors="replace"))
            return None

        for fname in sorted(os.listdir(tmpdir)):
            if fname.startswith(f"{idx:03d}_") and fname.endswith(".mp4"):
                return os.path.join(tmpdir, fname)
        return None

    def _upload_to_bunny(self, mp4_path, title, api_key, library_id):
        """Create a Bunny video slot and upload the MP4. Returns GUID or None."""
        base_url = f"{BUNNY_API_BASE}/{library_id}/videos"
        headers = {"AccessKey": api_key, "Content-Type": "application/json"}

        # Step 1: create video slot
        self.stdout.write("  Creating Bunny video slot…")
        try:
            resp = requests.post(base_url, json={"title": title}, headers=headers, proxies=self._proxies, timeout=30)
        except requests.RequestException as e:
            self.stderr.write(f"  Bunny API error: {e}")
            return None

        if resp.status_code not in (200, 201):
            self.stderr.write(f"  Bunny create failed: {resp.status_code} {resp.text}")
            return None

        guid = resp.json().get("guid")
        if not guid:
            self.stderr.write("  Bunny response missing GUID.")
            return None

        # Step 2: upload MP4
        file_size_mb = Path(mp4_path).stat().st_size // 1_048_576
        self.stdout.write(f"  Uploading {file_size_mb} MB to Bunny…")
        upload_headers = {"AccessKey": api_key, "Content-Type": "application/octet-stream"}
        try:
            with open(mp4_path, "rb") as f:
                up_resp = requests.put(
                    f"{base_url}/{guid}",
                    data=f,
                    headers=upload_headers,
                    proxies=self._proxies,
                    timeout=3600,  # 1 hour max for large files
                )
        except requests.RequestException as e:
            self.stderr.write(f"  Bunny upload error: {e}")
            return None

        if up_resp.status_code not in (200, 201):
            self.stderr.write(f"  Bunny upload failed: {up_resp.status_code} {up_resp.text}")
            return None

        return guid
