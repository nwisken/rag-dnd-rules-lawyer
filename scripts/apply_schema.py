"""Apply db/init/*.sql to the database in DATABASE_URL, in order.

docker-compose auto-runs these only on a fresh volume; this applies them to any DB
(CI's service container, or Azure Postgres for the one-time prod load) with no psql client.

Usage:
    uv run python scripts/apply_schema.py
"""

from pathlib import Path

from ruleslawyer.ingest.load import connect

INIT_DIR = Path("db/init")


def main() -> None:
    """Runs each db/init/*.sql file in filename order against DATABASE_URL."""
    conn = connect()
    # autocommit + no params => psycopg uses the simple-query protocol, so a file's
    # multiple statements run in one execute (the extended protocol forbids that)
    conn.autocommit = True
    for sql_file in sorted(INIT_DIR.glob("*.sql")):
        conn.execute(sql_file.read_text(encoding="utf-8"))
        print(f"applied {sql_file}")
    conn.close()


if __name__ == "__main__":
    main()
