"""
Shared database connection dependency for FastAPI routes.
"""

import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras


def get_db():
    """FastAPI dependency that yields a psycopg2 connection, closing it after use."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        yield conn
    finally:
        conn.close()
