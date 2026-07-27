"""
Database backup service.

Implements Requirement 21.7: perform database backups daily at midnight.
Retains a rolling window of recent backups.
"""
import os
import shutil
import sqlite3
import subprocess
from datetime import datetime, timedelta
from urllib.parse import urlparse

from flask import current_app

RETENTION_DAYS = 14


class BackupService:
    """Creates and prunes database backups."""

    @staticmethod
    def backup_dir() -> str:
        path = os.path.join(current_app.root_path, "..", "backups")
        os.makedirs(path, exist_ok=True)
        return os.path.abspath(path)

    @staticmethod
    def _sqlite_path() -> str | None:
        uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if not uri.startswith("sqlite:///"):
            return None
        return uri.replace("sqlite:///", "", 1)

    @classmethod
    def _postgres_dump(cls) -> str | None:
        """
        Run pg_dump against the configured database.

        Returns the dump path, or None if the backend is not Postgres or
        pg_dump is not installed on PATH.
        """
        uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
        if not uri.startswith(("postgresql://", "postgres://")):
            return None

        pg_dump = shutil.which("pg_dump")
        if not pg_dump:
            current_app.logger.info(
                "Postgres detected but pg_dump not on PATH; skipping backup. "
                "Install PostgreSQL client tools or rely on your managed "
                "provider's backup facility."
            )
            return None

        parsed = urlparse(uri.replace("postgres://", "postgresql://", 1))
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = os.path.join(cls.backup_dir(), f"hospital_{stamp}.dump")

        env = os.environ.copy()
        if parsed.password:
            env["PGPASSWORD"] = parsed.password

        cmd = [
            pg_dump,
            "--format=custom",
            f"--file={target}",
            "--host", parsed.hostname or "localhost",
            "--port", str(parsed.port or 5432),
            "--username", parsed.username or "postgres",
            (parsed.path or "/postgres").lstrip("/"),
        ]

        try:
            subprocess.run(cmd, check=True, env=env, capture_output=True, timeout=300)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            current_app.logger.error("pg_dump failed: %s", exc)
            if os.path.exists(target):
                try:
                    os.remove(target)
                except OSError:
                    pass
            return None

        cls.prune_old_backups()
        return target

    @classmethod
    def create_backup(cls) -> str | None:
        """
        Create a timestamped backup of the current database.

        SQLite uses its online backup API; Postgres uses pg_dump when
        available. Returns the backup path, or None when the engine cannot
        be backed up locally (managed providers should be relied on then).
        """
        source = cls._sqlite_path()
        if not source:
            # Try pg_dump for Postgres; if that isn't possible, defer to the
            # provider (Vercel / Railway / RDS all handle this themselves).
            return cls._postgres_dump()

        if not os.path.exists(source):
            current_app.logger.warning("Backup skipped: %s not found", source)
            return None

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = os.path.join(cls.backup_dir(), f"hospital_{stamp}.db")

        # Use SQLite's online backup API so the copy is consistent even if
        # another connection is writing. Note: sqlite3 connections used as
        # context managers commit but do NOT close, so close explicitly to
        # avoid holding a file handle on the backup.
        src = dst = None
        try:
            src = sqlite3.connect(source)
            dst = sqlite3.connect(target)
            src.backup(dst)
        finally:
            if dst is not None:
                dst.close()
            if src is not None:
                src.close()

        cls.prune_old_backups()
        return target

    @classmethod
    def prune_old_backups(cls) -> int:
        """Delete backups older than the retention window."""
        cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
        removed = 0

        for name in os.listdir(cls.backup_dir()):
            if not name.startswith("hospital_") or not name.endswith(".db"):
                continue
            path = os.path.join(cls.backup_dir(), name)
            try:
                if datetime.fromtimestamp(os.path.getmtime(path)) < cutoff:
                    os.remove(path)
                    removed += 1
            except OSError:
                continue

        return removed

    @classmethod
    def list_backups(cls) -> list:
        """Return known backups, newest first."""
        entries = []
        for name in sorted(os.listdir(cls.backup_dir()), reverse=True):
            if name.startswith("hospital_") and name.endswith(".db"):
                path = os.path.join(cls.backup_dir(), name)
                entries.append({
                    "name": name,
                    "size_kb": round(os.path.getsize(path) / 1024, 1),
                    "created_at": datetime.fromtimestamp(os.path.getmtime(path)),
                })
        return entries
