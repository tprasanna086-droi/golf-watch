"""
Initialize the database by applying schema.sql.

Usage:
    python -m db.init_db        (from backend/)
    python db/init_db.py        (from backend/)
"""

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env at the backend root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL is not set in .env")
        sys.exit(1)

    schema_path = Path(__file__).resolve().parent / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.close()
        print("Schema applied successfully")
    except psycopg2.Error as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
