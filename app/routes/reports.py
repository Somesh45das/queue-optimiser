"""
Admin reporting and CSV export routes.

Implements Requirement 25 (analytics export) and the crowd-log export
and manual logging triggers from Requirement 20.
"""
from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from app.models.models import Department, Doctor
from app.services.auth_service import admin_required
from app.services.crowd_logger import CrowdLogger
from app.services.report_exporter import ReportExporter, build_filename

reports_bp = Blueprint("reports", __name__)


def _csv_response(payload: str, report_type: str) -> Response:
    """Wrap CSV text in a download response."""
    filename = build_filename(report_type)
    return Response(
        payload,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@reports_bp.route("/")
@admin_required
def index():
    """Reporting hub with export filters."""
    departments = Department.query.order_by(Department.name).all()
    doctors = Doctor.query.order_by(Doctor.name).all()
    return render_template(
        "admin/reports.html",
        departments=departments,
        doctors=doctors,
    )


@reports_bp.route("/uptime")
@admin_required
def uptime():
    """Show 7/30/90 day availability against the 99.5% target (Req 21.4)."""
    from app.services.health_monitor import HealthMonitor

    reports = {days: HealthMonitor.uptime_report(days=days)
               for days in (7, 30, 90)}
    latest_probe = HealthMonitor.probe(persist=False)

    return render_template(
        "admin/uptime.html",
        reports=reports,
        latest_probe=latest_probe,
    )


@reports_bp.route("/export/appointments.csv")
@admin_required
def export_appointments():
    """Requirement 25.1: appointment export with filters."""
    payload = ReportExporter.appointments_csv(
        date_from=request.args.get("date_from"),
        date_to=request.args.get("date_to"),
        department_id=request.args.get("department_id") or None,
        doctor_id=request.args.get("doctor_id") or None,
        status=request.args.get("status") or None,
    )
    return _csv_response(payload, "appointments")


@reports_bp.route("/export/queue-stats.csv")
@admin_required
def export_queue_stats():
    """Requirement 25.2: queue statistics export."""
    payload = ReportExporter.queue_stats_csv(
        date_from=request.args.get("date_from"),
        date_to=request.args.get("date_to"),
        department_id=request.args.get("department_id") or None,
    )
    return _csv_response(payload, "queue_stats")


@reports_bp.route("/export/crowd-predictions.csv")
@admin_required
def export_crowd_predictions():
    """Requirement 25.3: crowd prediction export."""
    payload = ReportExporter.crowd_predictions_csv(
        target_date=request.args.get("date"),
        department_id=request.args.get("department_id") or None,
    )
    return _csv_response(payload, "crowd_predictions")


@reports_bp.route("/export/crowd-logs.csv")
@admin_required
def export_crowd_logs():
    """Requirement 20.7: historical crowd log export."""
    payload = ReportExporter.crowd_logs_csv(
        date_from=request.args.get("date_from"),
        date_to=request.args.get("date_to"),
        department_id=request.args.get("department_id") or None,
    )
    return _csv_response(payload, "crowd_logs")


@reports_bp.route("/crowd-logs/run", methods=["POST"])
@admin_required
def run_crowd_logging():
    """Manually trigger hourly crowd aggregation (Requirement 20.2)."""
    try:
        written = CrowdLogger.log_completed_hours()
        flash(f"Crowd logging complete. {written} department-hour records updated.", "success")
    except Exception as exc:
        flash(f"Crowd logging failed: {exc}", "danger")
    return redirect(url_for("reports.index"))


@reports_bp.route("/crowd-logs/backfill", methods=["POST"])
@admin_required
def backfill_crowd_logs():
    """Backfill crowd logs from existing queue history."""
    days = request.form.get("days", type=int) or 7
    days = max(1, min(days, 365))
    try:
        written = CrowdLogger.backfill(days)
        flash(f"Backfilled {written} department-hour records over {days} day(s).", "success")
    except Exception as exc:
        flash(f"Backfill failed: {exc}", "danger")
    return redirect(url_for("reports.index"))
