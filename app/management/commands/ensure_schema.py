"""
ensure_schema — repair production schema when Django migrations were recorded
as applied but the actual DDL was never executed (SQLite "ghost migration" issue).

Run via:  python manage.py ensure_schema
Idempotent: safe to run on a healthy DB — skips columns/tables that already exist.
"""

from django.core.management.base import BaseCommand
from django.db import connection


def _existing_cols(cursor, table):
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _table_exists(cursor, table):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", [table]
    )
    return cursor.fetchone() is not None


class Command(BaseCommand):
    help = "Ensure all migration schema changes are present (fixes ghost-migration state)."

    def handle(self, *args, **options):
        with connection.cursor() as c:
            # ── Migration 0010: app_course columns ────────────────────────────
            if _table_exists(c, "app_course"):
                cols = _existing_cols(c, "app_course")
                course_ddl = {
                    "title_en": "ALTER TABLE app_course ADD COLUMN title_en varchar(200) NOT NULL DEFAULT ''",
                    "description_en": "ALTER TABLE app_course ADD COLUMN description_en text NOT NULL DEFAULT ''",
                    "category": "ALTER TABLE app_course ADD COLUMN category varchar(20) NOT NULL DEFAULT 'foundations'",
                    "difficulty": "ALTER TABLE app_course ADD COLUMN difficulty varchar(20) NOT NULL DEFAULT 'beginner'",
                    "is_published": "ALTER TABLE app_course ADD COLUMN is_published bool NOT NULL DEFAULT 0",
                    "thumbnail": "ALTER TABLE app_course ADD COLUMN thumbnail varchar(200) NOT NULL DEFAULT ''",
                }
                for col, sql in course_ddl.items():
                    if col not in cols:
                        c.execute(sql)
                        self.stdout.write(f"  + app_course.{col}")

            # ── Migration 0010: app_video columns ─────────────────────────────
            if _table_exists(c, "app_video"):
                cols = _existing_cols(c, "app_video")
                video_ddl = {
                    "title_en": "ALTER TABLE app_video ADD COLUMN title_en varchar(200) NOT NULL DEFAULT ''",
                    "summary_he": "ALTER TABLE app_video ADD COLUMN summary_he text NOT NULL DEFAULT ''",
                    "notes_markdown": "ALTER TABLE app_video ADD COLUMN notes_markdown text NOT NULL DEFAULT ''",
                    "has_code_example": "ALTER TABLE app_video ADD COLUMN has_code_example bool NOT NULL DEFAULT 0",
                    "github_file": "ALTER TABLE app_video ADD COLUMN github_file varchar(200) NOT NULL DEFAULT ''",
                    # Migration 0011
                    "is_final_lesson": "ALTER TABLE app_video ADD COLUMN is_final_lesson bool NOT NULL DEFAULT 0",
                }
                for col, sql in video_ddl.items():
                    if col not in cols:
                        c.execute(sql)
                        self.stdout.write(f"  + app_video.{col}")

            # ── Migration 0012: app_uservideoprogress columns ─────────────────
            if _table_exists(c, "app_uservideoprogress"):
                cols = _existing_cols(c, "app_uservideoprogress")
                if "quiz_passed" not in cols:
                    c.execute(
                        "ALTER TABLE app_uservideoprogress ADD COLUMN quiz_passed bool NOT NULL DEFAULT 0"
                    )
                    self.stdout.write("  + app_uservideoprogress.quiz_passed")

            # ── Migration 0012: app_userprofile columns ───────────────────────
            if _table_exists(c, "app_userprofile"):
                cols = _existing_cols(c, "app_userprofile")
                if "github_username" not in cols:
                    c.execute(
                        "ALTER TABLE app_userprofile ADD COLUMN github_username varchar(100) NOT NULL DEFAULT ''"
                    )
                    self.stdout.write("  + app_userprofile.github_username")

            # ── Migration 0010: app_enrollment table ──────────────────────────
            if not _table_exists(c, "app_enrollment"):
                c.execute("""
                    CREATE TABLE app_enrollment (
                        id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                        enrolled_at datetime NOT NULL,
                        completed_at datetime NULL,
                        course_id bigint NOT NULL REFERENCES app_course(id) DEFERRABLE INITIALLY DEFERRED,
                        user_id integer NOT NULL REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED,
                        UNIQUE (user_id, course_id)
                    )
                """)
                self.stdout.write("  + table app_enrollment")

            # ── Migration 0011: app_lessonquiz table ──────────────────────────
            if not _table_exists(c, "app_lessonquiz"):
                c.execute("""
                    CREATE TABLE app_lessonquiz (
                        id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                        question text NOT NULL,
                        options_json text NOT NULL,
                        requires_correct bool NOT NULL,
                        video_id bigint NOT NULL UNIQUE REFERENCES app_video(id) DEFERRABLE INITIALLY DEFERRED
                    )
                """)
                self.stdout.write("  + table app_lessonquiz")

            # ── Migration 0011: app_coursecertificate table ───────────────────
            if not _table_exists(c, "app_coursecertificate"):
                c.execute("""
                    CREATE TABLE app_coursecertificate (
                        id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                        certificate_id char(32) NOT NULL UNIQUE,
                        issued_at datetime NOT NULL,
                        course_id bigint NOT NULL REFERENCES app_course(id) DEFERRABLE INITIALLY DEFERRED,
                        user_id integer NOT NULL REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED,
                        UNIQUE (user_id, course_id)
                    )
                """)
                self.stdout.write("  + table app_coursecertificate")

            # ── Migration 0013: app_coursematerial table ──────────────────────
            if not _table_exists(c, "app_coursematerial"):
                c.execute("""
                    CREATE TABLE app_coursematerial (
                        id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                        title varchar(200) NOT NULL,
                        material_type varchar(10) NOT NULL,
                        url varchar(200) NOT NULL,
                        "file" varchar(100) NULL,
                        "order" integer unsigned NOT NULL,
                        course_id bigint NOT NULL REFERENCES app_course(id) DEFERRABLE INITIALLY DEFERRED
                    )
                """)
                self.stdout.write("  + table app_coursematerial")

        self.stdout.write(self.style.SUCCESS("ensure_schema complete."))
