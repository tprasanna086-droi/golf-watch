"""
Seed the lakes table from sample_lakes.csv.

Usage:
    python -m db.seed_lakes      (from backend/)
    python db/seed_lakes.py      (from backend/)
"""

import csv
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

    csv_path = Path(__file__).resolve().parent / "sample_lakes.csv"
    if not csv_path.exists():
        print(f"ERROR: {csv_path} not found")
        sys.exit(1)

    # Read CSV rows
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("ERROR: CSV is empty")
        sys.exit(1)

    insert_sql = """
        INSERT INTO lakes (name, district, basin, lat, lon, geom, initial_area_ha, risk_class)
        VALUES (
            %(name)s,
            %(district)s,
            %(basin)s,
            %(lat)s,
            %(lon)s,
            ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326),
            %(initial_area_ha)s,
            %(risk_class)s
        )
        ON CONFLICT (name) DO NOTHING;
    """

    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        with conn.cursor() as cur:
            for row in rows:
                # Cast numeric fields
                row["lat"] = float(row["lat"])
                row["lon"] = float(row["lon"])
                row["initial_area_ha"] = float(row["initial_area_ha"])
                cur.execute(insert_sql, row)
            seeded = cur.rowcount  # last statement's count; count total instead
        # Query actual count of seeded lakes
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM lakes;")
            total = cur.fetchone()[0]
        conn.close()
        print(f"Seeded {len(rows)} lakes ({total} total in table)")
    except psycopg2.Error as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
