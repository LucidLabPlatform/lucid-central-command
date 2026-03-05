"""Shared test fixtures for lucid-auth.

Tests that need a real Postgres are skipped automatically when Postgres is
not reachable.  Set LUCID_TEST_DB_URL to point at a running Postgres, or
just run `docker-compose up -d lucid-db` and use the default.
"""
import os
import pytest

TEST_DB_URL = os.environ.get(
    "LUCID_TEST_DB_URL",
    "postgresql://lucid:lucid_secret@localhost:5432/lucid",
)


def postgres_available() -> bool:
    try:
        import psycopg2
        conn = psycopg2.connect(TEST_DB_URL, connect_timeout=2)
        conn.close()
        return True
    except Exception:
        return False


# Evaluated once at collection time
POSTGRES_AVAILABLE = postgres_available()

requires_postgres = pytest.mark.skipif(
    not POSTGRES_AVAILABLE,
    reason="Postgres not reachable — set LUCID_TEST_DB_URL or start lucid-db",
)
