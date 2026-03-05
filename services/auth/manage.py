"""User management CLI for lucid-auth.

Usage:
    python manage.py add-agent <agent_id>
    python manage.py add-cc
    python manage.py remove <username>
    python manage.py list
"""

import argparse
import os
import secrets
import time
from datetime import datetime, timezone

import bcrypt
import psycopg2
import psycopg2.extras

DB_URL = os.environ.get("LUCID_DB_URL", "postgresql://lucid:lucid_secret@localhost:5432/lucid")


def get_conn() -> psycopg2.extensions.connection:
    for attempt in range(10):
        try:
            conn = psycopg2.connect(DB_URL)
            conn.cursor().execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username      TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role          TEXT NOT NULL,
                    created_at    TEXT NOT NULL
                )
                """
            )
            conn.commit()
            return conn
        except psycopg2.OperationalError:
            if attempt == 9:
                raise
            time.sleep(1)
    raise RuntimeError("unreachable")


def _create_user(username: str, role: str) -> str:
    password = secrets.token_urlsafe(24)
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    created_at = datetime.now(timezone.utc).isoformat()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (%s, %s, %s, %s)",
                (username, hashed, role, created_at),
            )
        conn.commit()

    return password


def cmd_add_agent(args):
    agent_id = args.agent_id
    password = _create_user(agent_id, "agent")
    print(f"Created agent '{agent_id}'")
    print(f"Password: {password}")
    print("(copy to Pi .env as AGENT_PASSWORD — shown only once)")


def cmd_add_cc(args):
    username = "central-command"
    password = _create_user(username, "central-command")
    print(f"Created user '{username}'")
    print(f"Password: {password}")
    print("(copy to .env as CC_PASSWORD — shown only once)")


def cmd_remove(args):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE username = %s", (args.username,))
            rowcount = cur.rowcount
        conn.commit()
    if rowcount:
        print(f"Removed '{args.username}'")
    else:
        print(f"User '{args.username}' not found")


def cmd_list(args):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT username, role, created_at FROM users ORDER BY created_at"
            )
            rows = cur.fetchall()

    if not rows:
        print("(no users)")
        return

    rows = [dict(r) for r in rows]
    col_w = [max(len(str(r[c])) for r in rows) for c in ("username", "role", "created_at")]
    col_w = [max(w, h) for w, h in zip(col_w, [8, 4, 10])]
    header = f"{'username':<{col_w[0]}}  {'role':<{col_w[1]}}  {'created_at':<{col_w[2]}}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(f"{row['username']:<{col_w[0]}}  {row['role']:<{col_w[1]}}  {row['created_at']:<{col_w[2]}}")


def main():
    parser = argparse.ArgumentParser(description="lucid-auth user management")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add_agent = sub.add_parser("add-agent", help="Add a Pi agent user")
    p_add_agent.add_argument("agent_id", help="Agent hostname / ID")
    p_add_agent.set_defaults(func=cmd_add_agent)

    p_add_cc = sub.add_parser("add-cc", help="Add the central-command user")
    p_add_cc.set_defaults(func=cmd_add_cc)

    p_remove = sub.add_parser("remove", help="Remove a user")
    p_remove.add_argument("username")
    p_remove.set_defaults(func=cmd_remove)

    p_list = sub.add_parser("list", help="List all users")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
