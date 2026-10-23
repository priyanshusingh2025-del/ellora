import sys
from pathlib import Path

import click

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from queuesathi import create_app
from queuesathi.db import get_db


@click.command()
def main():
    """Show staff and admin accounts. Passwords are never shown."""
    app = create_app()

    with app.app_context():
        db = get_db()

        staff = db.execute(
            """
            SELECT u.username, u.role, u.active, s.service_code
            FROM users u
            LEFT JOIN services s ON s.id = u.service_id
            ORDER BY u.role, u.username
            """
        ).fetchall()

        students = db.execute(
            "SELECT COUNT(*) AS total FROM students"
        ).fetchone()

    click.echo("")
    click.echo("STAFF AND ADMIN ACCOUNTS")
    click.echo("-" * 64)
    click.echo(f"{'USERNAME':<24}{'ROLE':<10}{'DEPARTMENT':<14}{'ACTIVE'}")
    click.echo("-" * 64)

    for row in staff:
        department = row["service_code"] or "-"
        active = "yes" if row["active"] else "no"
        click.echo(
            f"{row['username']:<24}{row['role']:<10}"
            f"{department:<14}{active}"
        )

    if not staff:
        click.echo("No staff or admin accounts found.")

    click.echo("")
    click.echo(f"Registered students: {students['total']}")
    click.echo("")


if __name__ == "__main__":
    main()
