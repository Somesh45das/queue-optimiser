"""
Public health-probe endpoints for uptime monitoring.

External uptime services (UptimeRobot, StatusCake, Pingdom, or a
Prometheus blackbox exporter) poll these endpoints to compute the 99.5%
availability target from Requirement 21.4.

- GET /health          fast liveness ping; 200 when alive
- GET /health/ready    subsystem readiness (DB + ML); persists a sample
- GET /health/uptime   30-day uptime summary (JSON)
"""
from flask import Blueprint, current_app, jsonify

from app.services.health_monitor import HealthMonitor

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def liveness():
    """Cheap liveness probe. Returns 200 as long as the process serves HTTP."""
    return jsonify({
        "status": "ok",
        "service": "smartcare",
        "process_uptime_seconds": HealthMonitor.process_uptime_seconds(),
    })


@health_bp.route("/health/ready")
def readiness():
    """
    Full readiness check: probes DB and ML availability, persists the
    result, and returns 200/503 accordingly.
    """
    result = HealthMonitor.probe(persist=True)
    status_code = 200 if result["status"] != "down" else 503
    return jsonify(result), status_code


@health_bp.route("/health/uptime")
def uptime_json():
    """Uptime summary for the last 30 days (JSON)."""
    return jsonify(HealthMonitor.uptime_report(days=30))


@health_bp.errorhandler(Exception)
def _health_error(exc):
    current_app.logger.exception("Health probe failed: %s", exc)
    return jsonify({"status": "down", "error": str(exc)[:200]}), 503
