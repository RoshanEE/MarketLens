"""
Runs all SQL migration files in supabase/migrations/ against the configured Postgres database.
Usage (from the backend/ directory):
    python migrate.py
"""

import os
import pathlib
import psycopg2
from dotenv import load_dotenv

env_path = pathlib.Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

MIGRATIONS_DIR = pathlib.Path(__file__).parent.parent / "supabase" / "migrations"


def run_migrations():
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError(f"DATABASE_URL is not set. Looked for .env at: {env_path}")

    # psycopg2 uses postgresql:// (no +asyncpg driver prefix)
    conn_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    print(f"Connecting to database…")
    conn = psycopg2.connect(conn_url)
    conn.autocommit = True  # DDL statements don't need an explicit transaction

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        print("No migration files found.")
        return

    try:
        with conn.cursor() as cur:
            for migration_file in migration_files:
                print(f"Running {migration_file.name}…")
                sql = migration_file.read_text(encoding="utf-8")
                cur.execute(sql)
                print(f"  ✓ {migration_file.name} applied.")
    finally:
        conn.close()

    print("\nAll migrations applied successfully.")


if __name__ == "__main__":
    run_migrations()
