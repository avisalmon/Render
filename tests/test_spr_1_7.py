"""
SPR-1.7 — Ops, Quality & BKMs
Tests for F-1.7.1 through F-1.7.8.
Run: pytest -m spr17 -v
"""
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.spr17

BASE_DIR = Path(__file__).resolve().parent.parent


# --- F-1.7.1: pytest-django setup (already working — this test proves it) ---

class TestPytestSetup:
    """F-1.7.1: pytest-django is configured and running."""

    def test_pytest_django_marker_registered(self):
        """T-F-1.7.1-1: spr17 marker is declared in pyproject.toml."""
        import tomllib

        with open(BASE_DIR / "pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        markers = config["tool"]["pytest"]["ini_options"]["markers"]
        assert any("spr17" in m for m in markers)

    def test_django_settings_module_configured(self):
        """T-F-1.7.1-2: DJANGO_SETTINGS_MODULE is set in pyproject.toml."""
        import tomllib

        with open(BASE_DIR / "pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        assert config["tool"]["pytest"]["ini_options"]["DJANGO_SETTINGS_MODULE"] == "mysite.settings"


# --- F-1.7.2: black + ruff + pre-commit ---

class TestCodeQuality:
    """F-1.7.2: black, ruff, and pre-commit are configured."""

    def test_black_config_in_pyproject(self):
        """T-F-1.7.2-1: [tool.black] section exists in pyproject.toml."""
        import tomllib

        with open(BASE_DIR / "pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        assert "black" in config.get("tool", {})

    def test_ruff_config_in_pyproject(self):
        """T-F-1.7.2-2: [tool.ruff] section exists in pyproject.toml."""
        import tomllib

        with open(BASE_DIR / "pyproject.toml", "rb") as f:
            config = tomllib.load(f)
        assert "ruff" in config.get("tool", {})

    def test_pre_commit_config_exists(self):
        """T-F-1.7.2-3: .pre-commit-config.yaml exists."""
        assert (BASE_DIR / ".pre-commit-config.yaml").exists()

    def test_black_is_importable(self):
        """T-F-1.7.2-4: black package is installed."""
        import black  # noqa: F401

    def test_ruff_is_callable(self):
        """T-F-1.7.2-5: ruff command runs without error."""
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "--version"],
            capture_output=True, text=True
        )
        assert result.returncode == 0

    def test_ruff_check_passes(self):
        """T-F-1.7.2-6: ruff check passes on project code (no errors)."""
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "app/", "mysite/"],
            capture_output=True, text=True, cwd=str(BASE_DIR)
        )
        assert result.returncode == 0, f"ruff errors:\n{result.stdout}"


# --- F-1.7.4 through F-1.7.8: BKM docs exist ---

class TestBKMDocs:
    """F-1.7.4 through F-1.7.8: BKM documentation exists."""

    def test_backup_restore_bkm_exists(self):
        """T-F-1.7.4-1: docs/procedures/backup_restore.md exists."""
        assert (BASE_DIR / "docs" / "procedures" / "backup_restore.md").exists()

    def test_rollback_bkm_exists(self):
        """T-F-1.7.5-1: docs/procedures/rollback.md exists."""
        assert (BASE_DIR / "docs" / "procedures" / "rollback.md").exists()

    def test_cicd_bkm_exists(self):
        """T-F-1.7.6-1: docs/procedures/cicd.md exists."""
        assert (BASE_DIR / "docs" / "procedures" / "cicd.md").exists()

    def test_env_vars_bkm_exists(self):
        """T-F-1.7.7-1: docs/procedures/env_vars.md exists."""
        assert (BASE_DIR / "docs" / "procedures" / "env_vars.md").exists()

    def test_roles_doc_exists(self):
        """T-F-1.7.8-1: docs/architecture/roles.md exists."""
        assert (BASE_DIR / "docs" / "architecture" / "roles.md").exists()
