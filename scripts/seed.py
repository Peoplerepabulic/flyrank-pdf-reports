#!/usr/bin/env python3
"""Seed the report database. Idempotent: init_db() only inserts the ~200
orders when the orders table is empty."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import DB_PATH, get_conn, init_db  # noqa: E402


def main() -> None:
    init_db()
    conn = get_conn()
    try:
        n_orders = conn.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"]
        n_books = conn.execute("SELECT COUNT(*) AS n FROM books").fetchone()["n"]
    finally:
        conn.close()
    print(f"seeded OK: {n_books} books, {n_orders} orders in {DB_PATH}")


if __name__ == "__main__":
    main()
