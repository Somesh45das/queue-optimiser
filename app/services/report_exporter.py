"""
CSV report generation service.

Implements Requirement 25: export appointments, queue statistics, crowd
predictions and crowd logs as CSV with headers, filters and row limits.
"""
import csv
import io
from datetime import date, datetime, timedelta

from app.models.models import (
    Appointment,
    CrowdLog,
    Department,
    Doctor,
    QueueEntry,
)

MAX_ROWS = 10_000  # Requirement 25.7


def build_filename(report_type: str) -> str:
    """Requirement 25.6: report_type_YYYYMMDD_HHMMSS.csv"""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{report_type}_{stamp}.csv"


def _write_csv(header: list, rows: list) -> str:
    """Serialize rows to CSV text, always including the header row."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)  # Requirement 25.5
    writer.writerows(rows)
    return buffer.getvalue()


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


class ReportExporter:
    """Produces CSV payloads for the admin reporting screens."""

    @staticmethod
    def appointments_csv(date_from=None, date_to=None, department_id=None,
                         doctor_id=None, status=None) -> str:
        """Requirement 25.1 / 25.4: appointments export with filters."""
        query = Appointment.query

        start = _parse_date(date_from)
        end = _parse_date(date_to)
        if start:
            query = query.filter(Appointment.appointment_date >= start)
        if end:
            query = query.filter(Appointment.appointment_date <= end)
        if department_id:
            query = query.filter(Appointment.department_id == int(department_id))
        if doctor_id:
            query = query.filter(Appointment.doctor_id == int(doctor_id))
        if status:
            query = query.filter(Appointment.status == status)

        appointments = (
            query.order_by(
                Appointment.appointment_date.desc(),
                Appointment.appointment_time.asc(),
            )
            .limit(MAX_ROWS)
            .all()
        )

        header = [
            "appointment_number", "appointment_date", "appointment_time",
            "status", "patient_id", "patient_name", "patient_age",
            "patient_phone", "is_emergency", "doctor_name", "department",
            "priority_score", "estimated_wait_min", "actual_wait_min",
            "symptoms", "created_at",
        ]

        rows = []
        for appt in appointments:
            patient = appt.patient
            rows.append([
                appt.appointment_number,
                appt.appointment_date.isoformat() if appt.appointment_date else "",
                appt.appointment_time.strftime("%H:%M") if appt.appointment_time else "",
                appt.status,
                patient.patient_id if patient else "",
                patient.name if patient else "",
                patient.age if patient else "",
                patient.phone if patient else "",
                "yes" if patient and patient.is_emergency else "no",
                appt.doctor.name if appt.doctor else "",
                appt.department.name if appt.department else "",
                appt.priority_score,
                appt.estimated_wait_min,
                appt.actual_wait_min if appt.actual_wait_min is not None else "",
                (appt.symptoms or "").replace("\n", " ").strip(),
                appt.created_at.isoformat(timespec="seconds") if appt.created_at else "",
            ])

        return _write_csv(header, rows)

    @staticmethod
    def queue_stats_csv(date_from=None, date_to=None, department_id=None) -> str:
        """Requirement 25.2: queue statistics export, one row per department-day."""
        start = _parse_date(date_from) or date.today()
        end = _parse_date(date_to) or start
        if end < start:
            start, end = end, start

        departments = Department.query.order_by(Department.name).all()
        if department_id:
            departments = [d for d in departments if d.id == int(department_id)]

        header = [
            "queue_date", "department", "total_today", "waiting", "in_progress",
            "completed", "skipped", "avg_wait_minutes", "completion_rate_pct",
        ]

        rows = []
        current = start
        while current <= end and len(rows) < MAX_ROWS:
            for dept in departments:
                entries = QueueEntry.query.filter(
                    QueueEntry.department_id == dept.id,
                    QueueEntry.queue_date == current,
                ).all()

                if not entries:
                    continue

                total = len(entries)
                waiting = sum(1 for e in entries if e.status == "waiting")
                in_progress = sum(1 for e in entries if e.status == "in_progress")
                completed = sum(1 for e in entries if e.status == "completed")
                skipped = sum(1 for e in entries if e.status == "skipped")

                waits = [
                    (e.called_at - e.entered_at).total_seconds() / 60
                    for e in entries
                    if e.status == "completed" and e.called_at and e.entered_at
                ]
                avg_wait = round(sum(waits) / len(waits), 2) if waits else 0.0
                completion = round((completed / total) * 100, 2) if total else 0.0

                rows.append([
                    current.isoformat(), dept.name, total, waiting, in_progress,
                    completed, skipped, avg_wait, completion,
                ])
            current += timedelta(days=1)

        return _write_csv(header, rows)

    @staticmethod
    def crowd_predictions_csv(target_date=None, department_id=None) -> str:
        """Requirement 25.3: crowd prediction export for the OPD day."""
        from app.services.crowd_predictor import CrowdPredictor

        target = _parse_date(target_date) or date.today()
        predictor = CrowdPredictor()

        departments = Department.query.filter_by(is_active=True).order_by(
            Department.name
        ).all()
        if department_id:
            departments = [d for d in departments if d.id == int(department_id)]

        header = [
            "date", "department", "hour", "time_label", "crowd_level",
            "level_code", "confidence_pct", "patient_estimate",
        ]

        rows = []
        for dept in departments:
            for entry in predictor.predict_day_timeline(dept.id, target):
                if len(rows) >= MAX_ROWS:
                    break
                rows.append([
                    target.isoformat(), dept.name, entry["hour"],
                    entry.get("time_label", f"{entry['hour']:02d}:00"),
                    entry["level"], entry["level_code"], entry["confidence"],
                    entry["patient_estimate"],
                ])

        return _write_csv(header, rows)

    @staticmethod
    def crowd_logs_csv(date_from=None, date_to=None, department_id=None) -> str:
        """Requirement 20.7: export historical crowd logs as CSV."""
        query = CrowdLog.query

        start = _parse_date(date_from)
        end = _parse_date(date_to)
        if start:
            query = query.filter(CrowdLog.log_date >= start)
        if end:
            query = query.filter(CrowdLog.log_date <= end)
        if department_id:
            query = query.filter(CrowdLog.department_id == int(department_id))

        logs = (
            query.order_by(CrowdLog.log_date.desc(), CrowdLog.hour.asc())
            .limit(MAX_ROWS)
            .all()
        )

        header = [
            "log_date", "hour", "department", "day_of_week", "month",
            "is_holiday", "patient_count", "avg_wait_time", "crowd_level",
            "weather", "temperature",
        ]

        rows = [
            [
                log.log_date.isoformat() if log.log_date else "",
                log.hour,
                log.department.name if log.department else log.department_id,
                log.day_of_week,
                log.month,
                "yes" if log.is_holiday else "no",
                log.patient_count,
                log.avg_wait_time,
                log.crowd_level,
                log.weather,
                log.temperature,
            ]
            for log in logs
        ]

        return _write_csv(header, rows)
