from functools import wraps

from flask import (
    Blueprint,
    request,
    render_template,
    redirect,
    url_for,
    session,
    flash,
    abort,
    g
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from .db import get_db


auth_bp = Blueprint("auth", __name__)


@auth_bp.before_app_request
def load_current_account():
    g.user = None
    g.student = None

    # Static files and the health check never need the logged-in account.
    if request.endpoint in ("static", "health_check"):
        return

    user_id = session.get("user_id")
    student_id = session.get("student_id")

    if user_id:
        g.user = get_db().execute(
            """
            SELECT *
            FROM users
            WHERE id = ? AND active = 1
            """,
            (user_id,)
        ).fetchone()

        if g.user is None:
            session.clear()

    elif student_id:
        g.student = get_db().execute(
            """
            SELECT *
            FROM students
            WHERE id = ?
            """,
            (student_id,)
        ).fetchone()

        if g.student is None:
            session.clear()


def student_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.user:
            abort(403)

        if not g.student:
            return redirect(
                url_for("auth.student_login")
            )

        return view(*args, **kwargs)

    return wrapper


def role_required(*roles):
    def decorator(view):

        @wraps(view)
        def wrapper(*args, **kwargs):
            if g.student:
                abort(403)

            if not g.user:
                # Admin-only pages send visitors to the admin login.
                if roles == ("ADMIN",):
                    return redirect(url_for("auth.admin_login"))

                return redirect(url_for("auth.staff_select"))

            if g.user["role"] not in roles:
                abort(403)

            return view(*args, **kwargs)

        return wrapper

    return decorator


def login_required(view):
    return role_required("STAFF", "ADMIN")(view)


@auth_bp.route("/student/register", methods=["GET", "POST"])
def student_register():
    if g.user:
        abort(403)

    if g.student:
        return redirect(
            url_for("customer.dashboard")
        )

    if request.method == "POST":
        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        confirm = request.form.get(
            "confirm_password", ""
        )

        if len(username) < 3:
            flash(
                "Username must contain at least 3 characters.",
                "error"
            )

        elif len(password) < 8:
            flash(
                "Password must contain at least 8 characters.",
                "error"
            )

        elif password != confirm:
            flash(
                "Passwords do not match.",
                "error"
            )

        else:
            db = get_db()

            existing = db.execute(
                """
                SELECT id
                FROM students
                WHERE username = ?
                """,
                (username,)
            ).fetchone()

            if existing:
                flash(
                    "Username already exists.",
                    "error"
                )

            else:
                try:
                    student_id = db.execute(
                        """
                        INSERT INTO students (
                            username,
                            password_hash
                        )
                        VALUES (?, ?)
                        RETURNING id
                        """,
                        (
                            username,
                            generate_password_hash(password)
                        )
                    ).fetchone()["id"]

                    db.commit()

                    session.clear()
                    session["student_id"] = student_id

                    return redirect(
                        url_for("customer.dashboard")
                    )

                except Exception:
                    db.rollback()
                    flash(
                        "Registration failed. Please try again.",
                        "error"
                    )

    return render_template(
        "auth/student_register.html"
    )


@auth_bp.route("/student/login", methods=["GET", "POST"])
def student_login():
    if g.user:
        abort(403)

    if g.student:
        return redirect(
            url_for("customer.dashboard")
        )

    if request.method == "POST":
        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        student = get_db().execute(
            """
            SELECT *
            FROM students
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        if student and check_password_hash(
            student["password_hash"],
            password
        ):
            session.clear()
            session["student_id"] = student["id"]

            return redirect(
                url_for("customer.dashboard")
            )

        flash(
            "Invalid student credentials.",
            "error"
        )

    return render_template(
        "auth/student_login.html"
    )


@auth_bp.get("/staff/login")
def staff_select():
    if g.student:
        abort(403)

    if g.user:
        if g.user["role"] == "ADMIN":
            return redirect(
                url_for("admin.services")
            )

        return redirect(
            url_for("staff.dashboard")
        )

    services = get_db().execute(
        """
        SELECT *
        FROM services
        ORDER BY service_name
        """
    ).fetchall()

    return render_template(
        "auth/staff_select.html",
        services=services
    )


@auth_bp.route(
    "/staff/login/<service_code>",
    methods=["GET", "POST"]
)
def staff_login(service_code):
    if g.student:
        abort(403)

    if g.user:
        if g.user["role"] == "STAFF":
            return redirect(
                url_for("staff.dashboard")
            )

        return redirect(
            url_for("admin.services")
        )

    service = get_db().execute(
        """
        SELECT *
        FROM services
        WHERE service_code = ?
        """,
        (service_code.upper(),)
    ).fetchone()

    if not service:
        abort(404)

    if request.method == "POST":
        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        user = get_db().execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
              AND role = 'STAFF'
              AND active = 1
              AND service_id = ?
            """,
            (username, service["id"])
        ).fetchone()

        if user and check_password_hash(
            user["password_hash"],
            password
        ):
            session.clear()
            session["user_id"] = user["id"]

            return redirect(
                url_for("staff.dashboard")
            )

        flash(
            "Invalid credentials for this service.",
            "error"
        )

    return render_template(
        "auth/staff_login.html",
        service=service
    )


@auth_bp.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():
    if g.student:
        abort(403)

    if g.user:
        if g.user["role"] == "ADMIN":
            return redirect(
                url_for("admin.services")
            )

        abort(403)

    if request.method == "POST":
        username = request.form.get(
            "username", ""
        ).strip()

        password = request.form.get(
            "password", ""
        )

        user = get_db().execute(
            """
            SELECT *
            FROM users
            WHERE username = ?
              AND role = 'ADMIN'
              AND active = 1
            """,
            (username,)
        ).fetchone()

        if user and check_password_hash(
            user["password_hash"],
            password
        ):
            session.clear()
            session["user_id"] = user["id"]

            return redirect(
                url_for("admin.services")
            )

        flash(
            "Invalid administrator credentials.",
            "error"
        )

    return render_template(
        "auth/admin_login.html"
    )


@auth_bp.get("/login")
def login():
    return redirect(
        url_for("auth.student_login")
    )


@auth_bp.post("/logout")
def logout():
    session.clear()

    flash(
        "Logged out successfully.",
        "success"
    )

    return redirect(
        url_for("auth.student_login")
    )
