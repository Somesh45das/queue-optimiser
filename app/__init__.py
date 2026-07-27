"""
Flask application factory.
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
import os

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)

    if config_class is None:
        from config import Config
        config_class = Config

    app.config.from_object(config_class)

    # Secret key for sessions and CSRF
    app.secret_key = app.config['SECRET_KEY']

    # Ensure instance folder exists. Serverless filesystems (Vercel, AWS
    # Lambda) are read-only, so treat failure as non-fatal.
    try:
        os.makedirs(os.path.join(app.root_path, "..", "instance"), exist_ok=True)
    except OSError:
        pass

    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)
    
    # Initialize Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please login to access this page.'
    login_manager.login_message_category = 'warning'
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return User.query.get(int(user_id))

    # Register blueprints
    from app.routes.auth import auth_bp
    from app.routes.landing import landing_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.appointments import appointments_bp
    from app.routes.queue_routes import queue_bp
    from app.routes.doctors import doctors_bp
    from app.routes.api import api_bp
    from app.routes.chatbot import chatbot_bp
    from app.routes.patient_portal import patient_portal_bp
    from app.routes.doctor_portal import doctor_portal_bp
    from app.routes.admin_management import admin_mgmt_bp

    # Authentication routes (public)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    
    # Landing page
    app.register_blueprint(landing_bp)
    
    # Patient Portal (requires user login)
    app.register_blueprint(patient_portal_bp, url_prefix="/patient")
    
    # Doctor Portal (requires doctor login)
    app.register_blueprint(doctor_portal_bp)
    
    # Admin Portal (requires admin login)
    app.register_blueprint(dashboard_bp, url_prefix="/admin")
    app.register_blueprint(appointments_bp, url_prefix="/admin/appointments")
    app.register_blueprint(queue_bp, url_prefix="/admin/queue")
    app.register_blueprint(doctors_bp, url_prefix="/admin/doctors")
    app.register_blueprint(admin_mgmt_bp, url_prefix="/admin/manage")
    
    # API routes
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(chatbot_bp, url_prefix="/chatbot")
    
    # Notification routes
    from app.routes.notifications import notifications_bp
    app.register_blueprint(notifications_bp, url_prefix="/admin/notifications")

    # Reporting / CSV exports (Requirement 25)
    from app.routes.reports import reports_bp
    app.register_blueprint(reports_bp, url_prefix="/admin/reports")

    # Public health probes (Requirement 21.4)
    from app.routes.health import health_bp
    app.register_blueprint(health_bp)

    # The chatbot endpoint is a JSON API called via fetch(); it sends the
    # CSRF token in the X-CSRFToken header, which CSRFProtect validates.

    _configure_logging(app)
    _register_error_handlers(app)
    _configure_session_timeout(app)

    # Create database tables
    with app.app_context():
        from app.models import models  # noqa: F401
        from app.models import user  # noqa: F401
        db.create_all()

    _start_crowd_log_scheduler(app)
    _start_backup_scheduler(app)
    _start_health_scheduler(app)

    return app


def _start_health_scheduler(app):
    """
    Sample subsystem health every 5 minutes so uptime can be computed
    (Requirement 21.4).
    """
    if not app.config.get("ENABLE_HEALTH_SCHEDULER", True):
        return

    if os.environ.get("WERKZEUG_RUN_MAIN") != "true" and app.debug:
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        app.logger.warning("APScheduler unavailable - health sampling disabled")
        return

    from app.services.health_monitor import HealthMonitor

    def _sample():
        with app.app_context():
            try:
                HealthMonitor.probe(persist=True)
            except Exception as exc:
                app.logger.error("Health probe crashed: %s", exc, exc_info=True)

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(_sample, "interval", minutes=5, id="health_probe",
                      replace_existing=True, next_run_time=None)
    scheduler.start()
    app.extensions["health_scheduler"] = scheduler


def _configure_logging(app):
    """
    Requirement 21.6: log errors with timestamp, type and stack trace.

    Falls back to stdout when the filesystem is read-only (serverless
    hosts like Vercel), where the platform captures stdout automatically.
    """
    import logging
    from logging.handlers import RotatingFileHandler

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    )

    handler = None
    log_dir = os.path.join(app.root_path, "..", "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        handler = RotatingFileHandler(
            os.path.join(log_dir, "smartcare.log"),
            maxBytes=1_000_000,
            backupCount=5,
            encoding="utf-8",
        )
    except OSError:
        # Serverless / read-only filesystem: log to stdout so the platform
        # log stream captures it.
        handler = logging.StreamHandler()

    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)

    already_present = any(
        isinstance(h, type(handler)) and h is not handler
        for h in app.logger.handlers
    )
    if not already_present:
        app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def _register_error_handlers(app):
    """
    Requirement 23.5 / 23.7: friendly messages plus correct status codes.
    """
    from flask import jsonify, render_template, request

    def _wants_json():
        return (
            request.path.startswith("/api")
            or request.path.startswith("/chatbot")
            or request.accept_mimetypes.best == "application/json"
        )

    @app.errorhandler(400)
    def bad_request(error):
        if _wants_json():
            return jsonify({"error": "Bad request"}), 400
        return render_template("errors/error.html", code=400,
                               title="Bad request",
                               message="Please check your input and try again."), 400

    @app.errorhandler(403)
    def forbidden(error):
        if _wants_json():
            return jsonify({"error": "Forbidden"}), 403
        return render_template("errors/error.html", code=403,
                               title="Access denied",
                               message="You do not have permission to view this page."), 403

    @app.errorhandler(404)
    def not_found(error):
        if _wants_json():
            return jsonify({"error": "Not found"}), 404
        return render_template("errors/error.html", code=404,
                               title="Page not found",
                               message="The page you requested does not exist."), 404

    @app.errorhandler(500)
    @app.errorhandler(Exception)
    def server_error(error):
        from werkzeug.exceptions import HTTPException

        if isinstance(error, HTTPException):
            return error

        # Requirement 21.6: record type and stack trace.
        app.logger.error("Unhandled %s: %s", type(error).__name__, error,
                         exc_info=True)
        try:
            db.session.rollback()
        except Exception:
            pass

        if _wants_json():
            return jsonify({"error": "An error occurred. Please try again later."}), 500
        return render_template("errors/error.html", code=500,
                               title="Something went wrong",
                               message="An error occurred. Please try again later."), 500


def _configure_session_timeout(app):
    """
    Requirement 22.6: expire sessions after 60 minutes of inactivity.

    Refreshing on each request turns the fixed lifetime into an idle timeout.
    """
    from datetime import timedelta
    from flask import session

    app.permanent_session_lifetime = timedelta(
        seconds=app.config.get("PERMANENT_SESSION_LIFETIME", 3600)
        if isinstance(app.config.get("PERMANENT_SESSION_LIFETIME"), int)
        else 3600
    )

    @app.before_request
    def _refresh_session():
        session.permanent = True
        session.modified = True


def _start_backup_scheduler(app):
    """
    Requirement 21.7: back up the database daily at midnight.

    Supported for SQLite (file copy via the sqlite backup API). For
    PostgreSQL this logs a notice, since backups belong to the managed
    service / pg_dump in that deployment.
    """
    if not app.config.get("ENABLE_BACKUP_SCHEDULER", True):
        return

    if os.environ.get("WERKZEUG_RUN_MAIN") != "true" and app.debug:
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        app.logger.warning("APScheduler unavailable - daily backups disabled")
        return

    from app.services.backup_service import BackupService

    def _run_backup():
        with app.app_context():
            try:
                path = BackupService.create_backup()
                if path:
                    app.logger.info("Database backup written to %s", path)
            except Exception as exc:
                app.logger.error("Database backup failed: %s", exc, exc_info=True)

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(_run_backup, "cron", hour=0, minute=0, id="daily_backup",
                      replace_existing=True)
    scheduler.start()
    app.extensions["backup_scheduler"] = scheduler


def _start_crowd_log_scheduler(app):
    """
    Schedule hourly crowd logging (Requirement 20.2).

    Runs only in the main process and can be disabled via the
    ENABLE_CROWD_LOG_SCHEDULER environment variable.
    """
    if not app.config.get("ENABLE_CROWD_LOG_SCHEDULER", False):
        return

    # Avoid double-scheduling under the Werkzeug reloader.
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        pass
    else:
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        app.logger.warning("APScheduler unavailable - hourly crowd logging disabled")
        return

    from app.services.crowd_logger import CrowdLogger

    def _log_hourly():
        with app.app_context():
            try:
                CrowdLogger.log_completed_hours()
            except Exception as exc:
                app.logger.error("Hourly crowd logging failed: %s", exc)

    scheduler = BackgroundScheduler(daemon=True)
    # Fire a few minutes past each hour so the previous hour is complete.
    scheduler.add_job(_log_hourly, "cron", minute=2, id="crowd_log_hourly",
                      replace_existing=True)
    scheduler.start()
    app.extensions["crowd_log_scheduler"] = scheduler
