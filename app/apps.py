import sqlite3

from django.apps import AppConfig


def _repair_schema(db_path: str) -> None:
    """
    Patch missing columns / tables from migrations 0010-0013 that were ghost-applied
    on the production DB (recorded in django_migrations but DDL never ran).

    Uses raw sqlite3 — intentionally bypasses Django's connection/transaction_mode
    so it works even before Django's DB layer is fully initialised.

    Fully idempotent.  Silently no-ops on any error (build phase, fresh install, etc.).
    """
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        c = conn.cursor()

        # Only act on a DB that already has django_migrations (not a brand-new install)
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='django_migrations'")
        if not c.fetchone():
            conn.close()
            return

        # ── app_course columns (migration 0010) ──────────────────────────────
        c.execute("PRAGMA table_info(app_course)")
        existing = {row[1] for row in c.fetchall()}
        if existing:  # table exists
            for col, sql in [
                ("title_en",       "ALTER TABLE app_course ADD COLUMN title_en varchar(200) NOT NULL DEFAULT ''"),
                ("description_en", "ALTER TABLE app_course ADD COLUMN description_en text NOT NULL DEFAULT ''"),
                ("category",       "ALTER TABLE app_course ADD COLUMN category varchar(20) NOT NULL DEFAULT 'foundations'"),
                ("difficulty",     "ALTER TABLE app_course ADD COLUMN difficulty varchar(20) NOT NULL DEFAULT 'beginner'"),
                ("is_published",   "ALTER TABLE app_course ADD COLUMN is_published bool NOT NULL DEFAULT 0"),
                ("thumbnail",      "ALTER TABLE app_course ADD COLUMN thumbnail varchar(200) NOT NULL DEFAULT ''"),
            ]:
                if col not in existing:
                    c.execute(sql)

        # ── app_video columns (migrations 0010 + 0011) ───────────────────────
        c.execute("PRAGMA table_info(app_video)")
        existing = {row[1] for row in c.fetchall()}
        if existing:
            for col, sql in [
                ("title_en",        "ALTER TABLE app_video ADD COLUMN title_en varchar(200) NOT NULL DEFAULT ''"),
                ("summary_he",      "ALTER TABLE app_video ADD COLUMN summary_he text NOT NULL DEFAULT ''"),
                ("notes_markdown",  "ALTER TABLE app_video ADD COLUMN notes_markdown text NOT NULL DEFAULT ''"),
                ("has_code_example","ALTER TABLE app_video ADD COLUMN has_code_example bool NOT NULL DEFAULT 0"),
                ("github_file",     "ALTER TABLE app_video ADD COLUMN github_file varchar(200) NOT NULL DEFAULT ''"),
                ("is_final_lesson", "ALTER TABLE app_video ADD COLUMN is_final_lesson bool NOT NULL DEFAULT 0"),
            ]:
                if col not in existing:
                    c.execute(sql)

        # ── app_uservideoprogress columns (migration 0012) ───────────────────
        c.execute("PRAGMA table_info(app_uservideoprogress)")
        existing = {row[1] for row in c.fetchall()}
        if existing and "quiz_passed" not in existing:
            c.execute("ALTER TABLE app_uservideoprogress ADD COLUMN quiz_passed bool NOT NULL DEFAULT 0")

        # ── app_userprofile columns (migration 0012) ─────────────────────────
        c.execute("PRAGMA table_info(app_userprofile)")
        existing = {row[1] for row in c.fetchall()}
        if existing and "github_username" not in existing:
            c.execute("ALTER TABLE app_userprofile ADD COLUMN github_username varchar(100) NOT NULL DEFAULT ''")

        # ── Missing tables ────────────────────────────────────────────────────
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_enrollment'")
        if not c.fetchone():
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

        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_lessonquiz'")
        if not c.fetchone():
            c.execute("""
                CREATE TABLE app_lessonquiz (
                    id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                    question text NOT NULL,
                    options_json text NOT NULL,
                    requires_correct bool NOT NULL,
                    video_id bigint NOT NULL UNIQUE REFERENCES app_video(id) DEFERRABLE INITIALLY DEFERRED
                )
            """)

        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_coursecertificate'")
        if not c.fetchone():
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

        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_coursematerial'")
        if not c.fetchone():
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

        # ── Migration 0009: app_newslettersubscriber table ───────────────────
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='app_newslettersubscriber'")
        if not c.fetchone():
            c.execute("""
                CREATE TABLE app_newslettersubscriber (
                    id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                    email varchar(254) NOT NULL UNIQUE,
                    name varchar(100) NOT NULL,
                    language varchar(5) NOT NULL,
                    source_page varchar(200) NOT NULL,
                    utm_source varchar(100) NOT NULL,
                    utm_medium varchar(100) NOT NULL,
                    utm_campaign varchar(100) NOT NULL,
                    utm_content varchar(100) NOT NULL,
                    ip_hash varchar(64) NOT NULL,
                    confirmed_at datetime NULL,
                    unsubscribed_at datetime NULL,
                    created_at datetime NOT NULL,
                    updated_at datetime NOT NULL
                )
            """)

        # ── Fake-apply ghost migrations so `migrate` sees them as done ────────
        for mig in [
            "0005_copilot_seats",
            "0006_ai_chat",
            "0007_billing_entitlement",
            "0008_corporate_lead",
            "0009_newslettersubscriber",
            "0010_course_video_enrollment_enhancements",
            "0011_lesson_quiz_certificate",
            "0012_quiz_passed_field",
            "0013_coursematerial",
        ]:
            c.execute("SELECT id FROM django_migrations WHERE app='app' AND name=?", [mig])
            if not c.fetchone():
                c.execute(
                    "INSERT INTO django_migrations (app, name, applied) VALUES (?,?,?)",
                    ["app", mig, "2024-01-01 00:00:00+00:00"],
                )

        conn.commit()
        conn.close()

    except Exception:
        # Build phase (persistent disk not mounted), fresh install, already patched — all fine.
        pass


class AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app"

    def ready(self):
        from django.conf import settings

        db_path = settings.DATABASES.get("default", {}).get("NAME", "")
        if db_path and db_path != ":memory:":
            _repair_schema(db_path)
