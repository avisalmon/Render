"""
ensure_schema - repair production schema when Django migrations were recorded
as applied but the actual DDL was never executed (SQLite "ghost migration" issue).

Also fake-applies any missing migration records so `migrate` doesn't try to
re-run operations that ensure_schema already performed.

Run via:  python manage.py ensure_schema
Idempotent: safe to run on a healthy DB - skips columns/tables that already exist.
"""

import datetime

from django.core.management.base import BaseCommand
from django.db import connection


def _existing_cols(cursor, table):
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _table_exists(cursor, table):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=%s", [table]
    )
    return cursor.fetchone() is not None


def _migration_applied(cursor, name):
    cursor.execute(
        "SELECT id FROM django_migrations WHERE app=%s AND name=%s",
        ["app", name],
    )
    return cursor.fetchone() is not None


class Command(BaseCommand):
    help = "Ensure all migration schema changes are present (fixes ghost-migration state)."

    def handle(self, *args, **options):
        with connection.cursor() as c:
            # Fresh install - django_migrations doesn't exist yet; let migrate handle everything
            if not _table_exists(c, "django_migrations"):
                self.stdout.write("Fresh install - skipping ensure_schema.")
                return

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

            # ── Fake-apply migrations whose schema is now in place ────────────
            # Prevents `migrate` from re-running DDL we just applied above.
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            for mig_name in [
                "0010_course_video_enrollment_enhancements",
                "0011_lesson_quiz_certificate",
                "0012_quiz_passed_field",
                "0013_coursematerial",
            ]:
                if not _migration_applied(c, mig_name):
                    c.execute(
                        "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
                        ["app", mig_name, now],
                    )
                    self.stdout.write(f"  ~ faked {mig_name}")

        # ── Generic repair: rebuild any 'app' table that migrations recorded as
        #    applied but whose DDL is missing (SQLite ghost-migration drift, e.g.
        #    after a partial backup/restore). Run AFTER migrate in the deploy, so
        #    genuinely-pending migrations have already created their tables and
        #    only true ghosts remain to rebuild here - no "table already exists"
        #    clash with migrate. Covers app_corporatelead, app_newslettersubscriber,
        #    the dashboard tables, etc. without hand-written DDL per table.
        from django.apps import apps

        existing = set(connection.introspection.table_names())
        remaining = [
            m for m in apps.get_app_config("app").get_models()
            if m._meta.managed and not m._meta.proxy and m._meta.db_table not in existing
        ]
        # Loop so FK dependencies between several missing tables resolve in order.
        last_err = None
        for _ in range(len(remaining) + 1):
            if not remaining:
                break
            still = []
            for model in remaining:
                try:
                    with connection.schema_editor() as se:
                        se.create_model(model)
                    self.stdout.write(f"  + table {model._meta.db_table} (rebuilt from model)")
                except Exception as e:  # noqa: BLE001
                    last_err = e
                    still.append(model)
            if len(still) == len(remaining):
                for model in still:
                    self.stderr.write(f"  ! could not rebuild {model._meta.db_table}: {last_err}")
                break
            remaining = still

        self.stdout.write(self.style.SUCCESS("ensure_schema complete."))
