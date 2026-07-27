"""
Historical crowd data logging service.

Implements Requirement 20: log actual hourly crowd data to the CrowdLog
table so the ML model can later be retrained on real observations.
"""
from datetime import date, datetime, timedelta

from app import db
from app.models.models import CrowdLog, Department, QueueEntry


# Requirement 1.3 / 20.5: crowd level thresholds.
CROWD_THRESHOLDS = (
    (10, "low"),
    (25, "medium"),
    (40, "high"),
)

RETENTION_DAYS = 365  # Requirement 20.6


class CrowdLogger:
    """Aggregates queue activity into hourly CrowdLog rows."""

    @staticmethod
    def classify_crowd_level(patient_count: int) -> str:
        """Map a raw patient count onto a crowd level label."""
        for ceiling, label in CROWD_THRESHOLDS:
            if patient_count <= ceiling:
                return label
        return "critical"

    @staticmethod
    def _window_bounds(log_date: date, hour: int):
        start = datetime.combine(log_date, datetime.min.time()) + timedelta(hours=hour)
        return start, start + timedelta(hours=1)

    @classmethod
    def log_hour(cls, department_id: int, log_date: date, hour: int,
                 temperature: float = 25.0, weather: str = "clear",
                 is_holiday: bool = False) -> CrowdLog:
        """
        Create or update the CrowdLog row for one department-hour.

        Requirement 20.3: patient_count is the number of queue entries
        created during that hour.
        Requirement 20.4: avg_wait_time comes from completed entries.
        """
        start, end = cls._window_bounds(log_date, hour)

        entries = QueueEntry.query.filter(
            QueueEntry.department_id == department_id,
            QueueEntry.queue_date == log_date,
            QueueEntry.entered_at >= start,
            QueueEntry.entered_at < end,
        ).all()

        patient_count = len(entries)

        waits = []
        for entry in entries:
            if entry.status == "completed" and entry.called_at and entry.entered_at:
                minutes = (entry.called_at - entry.entered_at).total_seconds() / 60
                if minutes >= 0:
                    waits.append(minutes)

        avg_wait = round(sum(waits) / len(waits), 2) if waits else 0.0

        log = CrowdLog.query.filter_by(
            department_id=department_id, log_date=log_date, hour=hour
        ).first()

        if log is None:
            log = CrowdLog(
                department_id=department_id,
                log_date=log_date,
                hour=hour,
            )
            db.session.add(log)

        log.day_of_week = log_date.weekday()
        log.month = log_date.month
        log.is_holiday = bool(is_holiday)
        log.patient_count = patient_count
        log.avg_wait_time = avg_wait
        log.crowd_level = cls.classify_crowd_level(patient_count)
        log.weather = weather
        log.temperature = temperature

        return log

    @classmethod
    def log_completed_hours(cls, target_date: date = None) -> int:
        """
        Log every hour that has fully elapsed for the given date.

        Requirement 20.2: crowd data is logged at the end of each hour.
        Returns the number of department-hour rows written.
        """
        explicit_date = target_date is not None
        target_date = target_date or date.today()
        now = datetime.now()

        if target_date > now.date():
            return 0

        # Only log hours that have finished.
        last_hour = 23 if target_date < now.date() else now.hour - 1

        if last_hour < 0:
            # Running just after midnight: no hour of today has completed yet,
            # so close out the previous day instead.
            if explicit_date:
                return 0
            return cls.log_completed_hours(target_date - timedelta(days=1))

        departments = Department.query.all()
        written = 0

        for dept in departments:
            for hour in range(0, last_hour + 1):
                cls.log_hour(dept.id, target_date, hour)
                written += 1

        db.session.commit()
        return written

    @classmethod
    def backfill(cls, days: int = 7) -> int:
        """Populate logs for the last N days from existing queue history."""
        today = date.today()
        written = 0
        for offset in range(days, -1, -1):
            written += cls.log_completed_hours(today - timedelta(days=offset))
        return written

    @classmethod
    def purge_expired(cls) -> int:
        """Delete logs older than the retention window (Requirement 20.6)."""
        cutoff = date.today() - timedelta(days=RETENTION_DAYS)
        deleted = CrowdLog.query.filter(CrowdLog.log_date < cutoff).delete(
            synchronize_session=False
        )
        db.session.commit()
        return deleted
