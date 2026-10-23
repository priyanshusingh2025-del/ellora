import os

import click

from flask import Flask, render_template, url_for, g, request
from flask_wtf.csrf import CSRFProtect

from .config import Config
from .db import init_app, init_db

csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_object(Config)

    app.config["DATABASE"] = os.path.join(
        app.instance_path,
        "queuesathi.sqlite3"
    )

    if test_config:
        app.config.update(test_config)

    if os.getenv("VERCEL") == "1" and not app.config.get("DATABASE_URL"):
        raise RuntimeError(
            "Set DATABASE_URL or POSTGRES_URL to a persistent PostgreSQL "
            "database on Vercel."
        )

    if not app.config.get("SECRET_KEY"):
        if app.config.get("TESTING"):
            app.config["SECRET_KEY"] = "testing-only-secret"
        else:
            raise RuntimeError(
                "SECRET_KEY is missing. Set it in .env or in Vercel environment variables."
            )

    # The instance folder is only needed for local SQLite.
    # On Vercel the filesystem is read-only, so do not create it there.
    if not app.config.get("DATABASE_URL"):
        os.makedirs(app.instance_path, exist_ok=True)

    csrf.init_app(app)

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

    @app.cli.command("init-db")
    def initialize_database():
        init_db()
        click.echo("QueueSathi database initialized.")

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
