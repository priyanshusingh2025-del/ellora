from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from ..auth import role_required

from ..db import get_db

from ..reports import get_statistics


admin_bp = Blueprint("admin", __name__)

@admin_bp.get("/admin")
@role_required("ADMIN")
def home():
    return redirect(url_for("admin.services"))


@admin_bp.get("/admin/services")
@role_required("ADMIN")
def services():
    rows = get_db().execute(
        "SELECT * FROM services ORDER BY id"
    ).fetchall()

    return render_template(
        "admin/services.html",
        services=rows
    )


@admin_bp.post("/admin/services/add")
@role_required("ADMIN")
def add_service():
    name = request.form.get(
        "service_name",
        ""
    ).strip()

    code = request.form.get(
        "service_code",
        ""
    ).strip().upper()

    if not name or not code or not code.isalnum():
        flash("Enter a valid name and alphanumeric code.", "error")
        return redirect(url_for("admin.services"))

    db = get_db()

    try:
        db.execute(
            '''
            INSERT INTO services (
                service_name,
                service_code
            )
            VALUES (?, ?)
            ''',
            (name, code)
        )

        db.commit()

        flash("Service added.", "success")

    except Exception:
        db.rollback()
        flash(
            "Service could not be added. Check for duplicates.",
            "error"
        )

    return redirect(url_for("admin.services"))


@admin_bp.post("/admin/services/<int:service_id>/toggle")
@role_required("ADMIN")
def toggle_service(service_id):
    db = get_db()

    db.execute(
        '''
        UPDATE services
        SET is_open = CASE
            WHEN is_open = 1 THEN 0
            ELSE 1
        END
        WHERE id = ?
        ''',
        (service_id,)
    )

    db.commit()

    flash("Service availability updated.", "success")

    return redirect(url_for("admin.services"))


@admin_bp.post("/admin/services/<int:service_id>/rename")
@role_required("ADMIN")
def rename_service(service_id):
    name = request.form.get(
        "service_name",
        ""
    ).strip()

    if not name:
        flash("Service name cannot be empty.", "error")
        return redirect(url_for("admin.services"))

    db = get_db()

    try:
        db.execute(
            '''
            UPDATE services
            SET service_name = ?
            WHERE id = ?
            ''',
            (name, service_id)
        )

        db.commit()

        flash("Service renamed.", "success")

    except Exception:
        db.rollback()
        flash("Unable to rename service.", "error")

    return redirect(url_for("admin.services"))


@admin_bp.get("/admin/reports")
@role_required("ADMIN")
def reports():
    statistics = get_statistics()

    return render_template(
        "admin/reports.html",
        stats=statistics
    )
