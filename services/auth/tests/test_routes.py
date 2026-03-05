from datetime import datetime, timezone

import bcrypt
import psycopg2
import pytest
from fastapi.testclient import TestClient

import app as auth_app
from app import app
from tests.conftest import TEST_DB_URL, POSTGRES_AVAILABLE


@pytest.fixture(autouse=True)
def tmp_db(monkeypatch):
    if not POSTGRES_AVAILABLE:
        pytest.skip("Postgres not reachable")
    monkeypatch.setattr(auth_app, "DB_URL", TEST_DB_URL)
    auth_app.init_db(TEST_DB_URL)

    hashed = bcrypt.hashpw(b"secret123", bcrypt.gensalt()).decode()
    with psycopg2.connect(TEST_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE username = 'nikandros'")
            cur.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (%s, %s, %s, %s)",
                ("nikandros", hashed, "agent", datetime.now(timezone.utc).isoformat()),
            )
        conn.commit()

    yield TEST_DB_URL

    with psycopg2.connect(TEST_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE username = 'nikandros'")
            cur.execute("DELETE FROM authn_log WHERE username IN ('nikandros', 'ghost')")
            cur.execute("DELETE FROM authz_log WHERE username IN ('nikandros', 'ghost')")
        conn.commit()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# /authn
# ---------------------------------------------------------------------------

def test_authn_valid(client):
    resp = client.post("/authn", json={
        "username": "nikandros",
        "password": "secret123",
        "clientid": "pi-nikandros",
    })
    assert resp.status_code == 200
    assert resp.json() == {"result": "allow"}


def test_authn_bad_password(client):
    resp = client.post("/authn", json={
        "username": "nikandros",
        "password": "wrong",
        "clientid": "pi-nikandros",
    })
    assert resp.status_code == 200
    assert resp.json() == {"result": "deny"}


def test_authn_unknown_user(client):
    resp = client.post("/authn", json={
        "username": "ghost",
        "password": "anything",
        "clientid": "x",
    })
    assert resp.status_code == 200
    assert resp.json() == {"result": "deny"}


# ---------------------------------------------------------------------------
# /authz
# ---------------------------------------------------------------------------

def test_authz_valid(client):
    resp = client.post("/authz", json={
        "username": "nikandros",
        "clientid": "pi-nikandros",
        "topic": "lucid/agents/nikandros/status",
        "action": "publish",
    })
    assert resp.status_code == 200
    assert resp.json() == {"result": "allow"}


def test_authz_denied(client):
    resp = client.post("/authz", json={
        "username": "nikandros",
        "clientid": "pi-nikandros",
        "topic": "lucid/agents/zephyros/status",
        "action": "publish",
    })
    assert resp.status_code == 200
    assert resp.json() == {"result": "deny"}


def test_authz_unknown_user(client):
    resp = client.post("/authz", json={
        "username": "ghost",
        "clientid": "x",
        "topic": "lucid/agents/ghost/status",
        "action": "publish",
    })
    assert resp.status_code == 200
    assert resp.json() == {"result": "deny"}
