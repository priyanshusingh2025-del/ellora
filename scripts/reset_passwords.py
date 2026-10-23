import sys
from pathlib import Path

import click
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from queuesathi import create_app
from queuesathi.db import get_db


# Same rules as the account creation scripts and registration form.
MIN_PASSWORD_LENGTH = {
    "users": 12,      # staff and admin
    "students": 8,    # students
}


def find_accounts(db, username):
    """Return every account with this username (staff/admin and student)."""
    accounts = []

    user = db.execute(
        """
        SELECT u.id, u.username, u.role, u.active, s.service_code
        FROM users u
        LEFT JOIN services s ON s.id = u.service_id
        WHERE u.username = ?
        """,
        (username,)
    ).fetchone()

    if user:
        accounts.append(("users", user))

    student = db.execute(
        "SELECT id, username FROM students WHERE username = ?",
        (username,)
    ).fetchone()

    if student:
        accounts.append(("students", student))

    return accounts


def describe(table, row):
    if table == "students":
        return f"student account '{row['username']}'"

    department = row["service_code"] or "no department"
    return f"{row['role']} account '{row['username']}' ({department})"


@click.command()
@click.argument("username", required=False)
def main(username):
    """Reset the password of a staff, admin, or student account."""

    if not username:
        username = click.prompt("Username to reset").strip()

    app = create_app()

    with app.app_context():
        db = get_db()

        accounts = find_accounts(db, username)

        if not accounts:
            click.echo(f"No account named '{username}' was found.")
            return

        if len(accounts) == 1:
            table, row = accounts[0]
        else:
            click.echo(
                f"'{username}' exists as both a staff/admin and a student account."
            )
            choice = click.prompt(
                "Which one should be reset?",
                type=click.Choice(["staff", "student"]),
            )
            table, row = (
                accounts[0] if choice == "staff" else accounts[1]
            )

        click.echo(f"Found {describe(table, row)}.")

        click.confirm("Reset this account's password?", abort=True)

        minimum = MIN_PASSWORD_LENGTH[table]

        password = click.prompt(
            f"New password (at least {minimum} characters)",
            hide_input=True,
            confirmation_prompt=True,
        )

        if len(password) < minimum:
            click.echo(
                f"Password must contain at least {minimum} characters. "
                "Nothing was changed."
            )
            return

        password_hash = generate_password_hash(password)

        if table == "users":
            # Also reactivates the account in case it was disabled.
            db.execute(
                """
                UPDATE users
                SET password_hash = ?, active = 1
                WHERE id = ?
                """,
                (password_hash, row["id"])
            )
        else:
            db.execute(
                """
                UPDATE students
                SET password_hash = ?
                WHERE id = ?
                """,
                (password_hash, row["id"])
            )

        db.commit()

        click.echo("")
        click.echo(f"Password updated for '{username}'.")

        if table == "users":
            click.echo("The account has also been set to active.")

        click.echo("Log in with the new password. It was not stored anywhere in plain text.")


if __name__ == "__main__":
    main()
