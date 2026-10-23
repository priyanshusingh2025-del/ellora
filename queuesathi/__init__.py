import os

import click
from flask import Flask, jsonify, render_template, request, url_for, g
from flask_compress import Compress
from flask_wtf.csrf import CSRFProtect

from .config import Config
from .db import init_app, init_db
from .setup_data import seed_defaults


csrf = CSRFProtect()
compress = Compress()


def default_database_path(app):
    # 1. An explicit path, such as a Render persistent disk.
    configured = os.environ.get("DATABASE_PATH")

    if configured:
        return configured

    # 2. Local development: instance/queuesathi.sqlite3
    return os.path.join(
        app.instance_path,
        "queuesathi.sqlite3"
    )


def create_app(test_config=None):
    app = Flask(
        __name__,
        instance_relative_config=True
    )

    app.config.from_object(Config)

    app.config["DATABASE"] = default_database_path(app)

    if test_config:
        app.config.update(test_config)

    if not app.config.get("SECRET_KEY"):
        if app.config.get("TESTING"):
            app.config["SECRET_KEY"] = "testing-only-secret"

        else:
            raise RuntimeError(
                "SECRET_KEY is missing. Add it to your local .env "
                "file or to the Render environment variables."
            )

    database_folder = os.path.dirname(app.config["DATABASE"])

    if database_folder:
        os.makedirs(database_folder, exist_ok=True)

    csrf.init_app(app)
    compress.init_app(app)   # gzip compression for HTML, CSS, JS, JSON

    init_app(app)

    from .auth import auth_bp
    from .routes.customer import customer_bp
    from .routes.staff import staff_bp
    from .routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(customer_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(admin_bp)

        # ---------- Static files with automatic version numbers ----------
    # Produces /static/css/style.css?v=1718000000. The number changes when
    # the file changes, so browsers can cache files for a year safely.
    @app.context_processor
    def asset_helpers():
        def static_url(filename):
            path = os.path.join(app.static_folder, filename)
            try:
                version = int(os.path.getmtime(path))
            except OSError:
                version = 0
            return url_for("static", filename=filename, v=version)

        return {"static_url": static_url}

    # ---------- Security and caching headers ----------
    @app.after_request
    def add_response_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )

        # Private pages and live APIs must never be cached. This also stops
        # the Back button from showing a dashboard after logout.
        is_private = (
            g.get("user") is not None
            or g.get("student") is not None
            or request.path.startswith(("/api/", "/staff/api/"))
        )

        if is_private and not request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store"

        return response

    if not app.config.get("TESTING"):
        with app.app_context():
            init_db()
            seed_defaults()

    @app.cli.command("init-db")
    def initialize_database():
        init_db()
        click.echo("QueueSathi database initialized.")

    # Lightweight health check for Render and uptime monitors.
    # It does not touch the database.
    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    # Cache policy:
    # - Static CSS/JS/images: cacheable by browsers for one hour.
    # - Everything else (student, staff, admin pages, JSON):
    #   never stored, so private queue data is not shown from cache.
    @app.after_request
    def set_cache_policy(response):
        if request.endpoint == "static":
            response.cache_control.public = True
            response.cache_control.max_age = 3600

        else:
            response.cache_control.no_store = True
            response.cache_control.private = True

        return response

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template("errors/500.html"), 500

    return app