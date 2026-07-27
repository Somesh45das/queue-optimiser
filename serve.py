"""
Production server entry point using Waitress.

Waitress is a pure-Python, cross-platform WSGI server suitable for both
Windows and Linux. Use this for concurrency tests and production runs
instead of Flask's development server.

Usage:
    python serve.py                   # 127.0.0.1:5000, 16 threads
    python serve.py --host 0.0.0.0    # bind on all interfaces
    python serve.py --threads 32      # more worker threads
"""
import argparse
import os

# Silence dev-only helpers before importing the app factory.
os.environ.setdefault("FLASK_ENV", "production")
os.environ.setdefault("FLASK_DEBUG", "0")
# Background schedulers only run in the reloader child, so mark this
# process explicitly so the crowd-log / backup jobs start.
os.environ.setdefault("WERKZEUG_RUN_MAIN", "true")


def build_app():
    from app import create_app
    app = create_app()
    app.config["DEBUG"] = False
    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--threads", type=int, default=16,
                        help="Worker threads (default: 16)")
    parser.add_argument("--connection-limit", type=int, default=200,
                        help="Max simultaneous connections (default: 200)")
    args = parser.parse_args()

    from waitress import serve

    app = build_app()
    print("=" * 60)
    print(f"  🏥 SmartCare (production) · http://{args.host}:{args.port}")
    print(f"  Threads: {args.threads} · Connection limit: {args.connection_limit}")
    print("=" * 60)
    serve(
        app,
        host=args.host,
        port=args.port,
        threads=args.threads,
        connection_limit=args.connection_limit,
        channel_timeout=30,
        ident="SmartCare",
    )


if __name__ == "__main__":
    main()
