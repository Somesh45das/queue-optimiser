"""
Vercel serverless entry point for the SmartCare Flask app.

Vercel invokes this module for every request and expects the WSGI callable
to be exported as `app`. The environment differs from a local dev server in
a few important ways, which this shim handles up-front:

  1. Filesystem is read-only except for /tmp, which is per-invocation only.
     SQLite therefore is not usable for real data - point DATABASE_URL at
     Postgres (Vercel Postgres, Neon, Supabase, etc.).
  2. Background schedulers (APScheduler jobs) cannot run - the process is
     torn down after every request. We disable them via env vars.
  3. Logging goes to stdout so Vercel captures it; file handlers are moot.

Deployment checklist:
  - Set the DATABASE_URL environment variable to a Postgres connection
    string in the Vercel dashboard (Settings > Environment Variables).
  - Set SECRET_KEY to a long random value.
  - Optionally set SMS_ENABLED, TWILIO_*, or AWS_* to enable real SMS.
"""
import os
import sys
import traceback

# The project root sits one level above the api/ folder.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Turn off any long-running/local-only features before the app factory runs.
os.environ.setdefault("FLASK_ENV", "production")
os.environ.setdefault("FLASK_DEBUG", "0")
os.environ.setdefault("ENABLE_CROWD_LOG_SCHEDULER", "False")
os.environ.setdefault("ENABLE_HEALTH_SCHEDULER", "False")
os.environ.setdefault("ENABLE_BACKUP_SCHEDULER", "False")

# Fall back to an in-memory SQLite so a misconfigured deployment still boots
# (data will be lost between invocations; set DATABASE_URL to keep data).
if not os.environ.get("DATABASE_URL") and not os.environ.get("POSTGRES_URL"):
    os.environ["DATABASE_URL"] = "sqlite:////tmp/hospital.db"


def _build_app():
    from app import create_app, db  # local import so any error is captured

    flask_app = create_app()
    with flask_app.app_context():
        try:
            db.create_all()
        except Exception as exc:
            flask_app.logger.error(
                "Vercel bootstrap: db.create_all() failed: %s", exc
            )
    return flask_app


try:
    app = _build_app()
except Exception as startup_error:
    # Surface a readable error page instead of a blank INTERNAL_FUNCTION_
    # INVOCATION_FAILED so the deployment is debuggable from the browser.
    from flask import Flask, jsonify

    error_message = str(startup_error)
    error_trace = traceback.format_exc()
    print("=" * 60, file=sys.stderr)
    print("SmartCare startup failed:", file=sys.stderr)
    print(error_trace, file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    app = Flask(__name__)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def _startup_failure(path):  # noqa: ARG001
        return jsonify({
            "status": "startup_error",
            "error": error_message,
            "hint": (
                "Check the Vercel function logs for the full traceback. "
                "Common causes: missing DATABASE_URL, Postgres unreachable, "
                "or a package version mismatch."
            ),
            "database_url_set": bool(os.environ.get("DATABASE_URL")),
            "secret_key_set": bool(os.environ.get("SECRET_KEY")),
        }), 500
