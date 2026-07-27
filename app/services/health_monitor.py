"""
Self-hosted uptime tracking.

Implements Requirement 21.4: 99.5% uptime during operating hours (8 AM to
8 PM). The app probes its own subsystems on a schedule, records the
result, and exposes the calculation to the admin dashboard.

External monitoring services (UptimeRobot, StatusCake, Pingdom, or a
Prometheus blackbox exporter) should call `/health` on top of this so a
process crash is observable from outside the process itself.
"""
import os
import time
from datetime import datetime, timedelta

from app import db
from app.models.models import HealthCheck
from config import Config

RETENTION_DAYS = 90
OPERATING_START = 8    # 8 AM inclusive
OPERATING_END = 20     # 8 PM exclusive (per Requirement 21.4)


class HealthMonitor:
    """Runs health probes and answers uptime questions."""

    _started_at = time.monotonic()

    @staticmethod
    def process_uptime_seconds() -> float:
        """How long this worker process has been alive."""
        return round(time.monotonic() - HealthMonitor._started_at, 1)

    @staticmethod
    def _check_database() -> tuple[bool, str | None]:
        try:
            db.session.execute(db.text("SELECT 1"))
            return True, None
        except Exception as exc:  # pragma: no cover - defensive
            db.session.rollback()
            return False, f"database: {exc}"[:255]

    @staticmethod
    def _check_ml_model() -> tuple[bool, str | None]:
        # Missing model files are treated as degraded, not down, because the
        # predictor falls back to rules (Requirement 3.7).
        try:
            return os.path.exists(Config.ML_MODEL_PATH), None
        except Exception as exc:
            return False, f"ml: {exc}"[:255]

    @classmethod
    def probe(cls, persist: bool = True) -> dict:
        """Run every check and optionally record the result."""
        start = time.perf_counter()

        db_ok, db_reason = cls._check_database()
        ml_ok, ml_reason = cls._check_ml_model()
        latency_ms = int((time.perf_counter() - start) * 1000)

        # DB failure is the only "down" signal; a missing ML model degrades.
        if not db_ok:
            status, reason = "down", db_reason
        elif not ml_ok:
            status, reason = "degraded", ml_reason or "ml model unavailable"
        else:
            status, reason = "up", None

        payload = {
            "status": status,
            "checked_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "latency_ms": latency_ms,
            "checks": {"database": db_ok, "ml_model": ml_ok},
            "process_uptime_seconds": cls.process_uptime_seconds(),
            "reason": reason,
        }

        if persist:
            try:
                db.session.add(HealthCheck(
                    status=status,
                    latency_ms=latency_ms,
                    db_ok=db_ok,
                    ml_ok=ml_ok,
                    failure_reason=reason,
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()

        return payload

    @classmethod
    def uptime_report(cls, days: int = 30) -> dict:
        """
        Compute uptime as (up_samples / total_samples) over the operating
        window (8 AM to 8 PM) for the requested lookback.
        """
        since = datetime.utcnow() - timedelta(days=days)
        rows = HealthCheck.query.filter(HealthCheck.checked_at >= since).all()

        # Requirement 21.4 measures uptime only during operating hours.
        in_window = [
            row for row in rows
            if OPERATING_START <= row.checked_at.hour < OPERATING_END
        ]

        total = len(in_window)
        if total == 0:
            return {
                "days": days,
                "samples": 0,
                "uptime_percent": None,
                "target": 99.5,
                "meets_target": None,
                "up": 0,
                "degraded": 0,
                "down": 0,
                "last_check": None,
                "process_uptime_seconds": cls.process_uptime_seconds(),
            }

        up = sum(1 for r in in_window if r.status == "up")
        degraded = sum(1 for r in in_window if r.status == "degraded")
        down = sum(1 for r in in_window if r.status == "down")

        # Degraded counts as available for Req 21.4 (service still responds).
        uptime_pct = round((up + degraded) / total * 100, 3)
        last = max(in_window, key=lambda r: r.checked_at)

        return {
            "days": days,
            "samples": total,
            "uptime_percent": uptime_pct,
            "target": 99.5,
            "meets_target": uptime_pct >= 99.5,
            "up": up,
            "degraded": degraded,
            "down": down,
            "last_check": {
                "at": last.checked_at.isoformat(timespec="seconds") + "Z",
                "status": last.status,
                "reason": last.failure_reason,
            },
            "process_uptime_seconds": cls.process_uptime_seconds(),
        }

    @classmethod
    def purge_expired(cls) -> int:
        """Delete health samples beyond the retention window."""
        cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
        deleted = HealthCheck.query.filter(
            HealthCheck.checked_at < cutoff
        ).delete(synchronize_session=False)
        db.session.commit()
        return deleted
