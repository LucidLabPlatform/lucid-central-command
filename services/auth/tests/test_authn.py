from datetime import datetime, timezone

import bcrypt
import psycopg2
import pytest

import app as auth_app
from tests.conftest import TEST_DB_URL, POSTGRES_AVAILABLE


@pytest.fixture()
def tmp_db(monkeypatch):
    if not POSTGRES_AVAILABLE:
        pytest.skip("Postgres not reachable")
    monkeypatch.setattr(auth_app, "DB_URL", TEST_DB_URL)
    auth_app.init_db(TEST_DB_URL)

    hashed = bcrypt.hashpw(b"correct-password", bcrypt.gensalt()).decode()
    with psycopg2.connect(TEST_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE username = 'testuser'")
            cur.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (%s, %s, %s, %s)",
                ("testuser", hashed, "agent", datetime.now(timezone.utc).isoformat()),
            )
        conn.commit()

    yield TEST_DB_URL

    with psycopg2.connect(TEST_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE username = 'testuser'")
        conn.commit()


def test_correct_password(tmp_db):
    user = auth_app.get_user("testuser", tmp_db)
    assert user is not None
    assert bcrypt.checkpw(b"correct-password", user["password_hash"].encode())


def test_wrong_password(tmp_db):
    user = auth_app.get_user("testuser", tmp_db)
    assert user is not None
    assert not bcrypt.checkpw(b"wrong-password", user["password_hash"].encode())


def test_unknown_username(tmp_db):
    user = auth_app.get_user("nobody", tmp_db)
    assert user is None
