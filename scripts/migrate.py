"""PROVIDED — applies every .sql file in migrations/ exactly once, in filename order.

Runs automatically as part of `docker compose up`. You should not need to
change this file; just add new .sql files to migrations/.
"""

from __future__ import annotations

import os
import pathlib
import sys

import psycopg

DSN = os.environ["DATABASE_URL"]
MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations"


def main() -> int:
    with psycopg.connect(DSN) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename   TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.commit()

        applied = {row[0] for row in conn.execute("SELECT filename FROM schema_migrations")}

        pending = [p for p in sorted(MIGRATIONS_DIR.glob("*.sql")) if p.name not in applied]
        if not pending:
            print("migrations: up to date", flush=True)
            return 0

        for path in pending:
            print(f"migrations: applying {path.name}", flush=True)
            conn.execute(path.read_text())
            conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,))
            conn.commit()

    print(f"migrations: applied {len(pending)} file(s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
