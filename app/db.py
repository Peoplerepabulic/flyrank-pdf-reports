"""SQLite layer for the report pipeline (BE-08).

- report.db lives in data/ (overridable via REPORT_DB).
- Schema auto-created on startup.
- Seed inserts ~200 bookstore orders, but ONLY when the orders table is
  empty — re-running the seed never duplicates data (idempotent).
- A reports table tracks generated PDFs: id, content hash, file path.
"""
import os
import random
import sqlite3
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("REPORT_DB", os.path.join(BASE_DIR, "data", "report.db"))
REPORTS_DIR = os.environ.get("REPORTS_DIR", os.path.join(BASE_DIR, "reports"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    title  TEXT NOT NULL,
    author TEXT NOT NULL,
    genre  TEXT NOT NULL,
    price  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id    INTEGER NOT NULL REFERENCES books(id),
    quantity   INTEGER NOT NULL,
    ordered_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    hash       TEXT NOT NULL UNIQUE,
    path       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

BOOKS = [
    ("The Pragmatic Programmer", "David Thomas", "Technology", 39.99),
    ("Clean Code", "Robert Martin", "Technology", 34.99),
    ("Designing Data-Intensive Applications", "Martin Kleppmann", "Technology", 44.99),
    ("Dune", "Frank Herbert", "Sci-Fi", 19.99),
    ("Neuromancer", "William Gibson", "Sci-Fi", 16.99),
    ("The Left Hand of Darkness", "Ursula Le Guin", "Sci-Fi", 15.99),
    ("Project Hail Mary", "Andy Weir", "Sci-Fi", 18.99),
    ("Sapiens", "Yuval Noah Harari", "History", 22.99),
    ("Guns, Germs, and Steel", "Jared Diamond", "History", 21.99),
    ("The Silk Roads", "Peter Frankopan", "History", 20.99),
    ("Thinking, Fast and Slow", "Daniel Kahneman", "Psychology", 18.99),
    ("Atomic Habits", "James Clear", "Psychology", 17.99),
    ("Man's Search for Meaning", "Viktor Frankl", "Psychology", 14.99),
    ("The Name of the Wind", "Patrick Rothfuss", "Fantasy", 19.99),
    ("Mistborn", "Brandon Sanderson", "Fantasy", 17.99),
    ("The Hobbit", "J.R.R. Tolkien", "Fantasy", 15.99),
    ("Educated", "Tara Westover", "Memoir", 18.99),
    ("Becoming", "Michelle Obama", "Memoir", 19.99),
    ("Kitchen Confidential", "Anthony Bourdain", "Memoir", 16.99),
    ("The Lean Startup", "Eric Ries", "Business", 24.99),
]


def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) AS n FROM orders").fetchone()["n"] == 0:
            _seed(conn)
        conn.commit()
    finally:
        conn.close()


def _seed(conn: sqlite3.Connection, n_orders: int = 200) -> None:
    """Deterministic seed (fixed RNG seed) of ~200 orders across 20 books."""
    rng = random.Random(20261002)
    book_ids = []
    for title, author, genre, price in BOOKS:
        cur = conn.execute(
            "INSERT INTO books (title, author, genre, price) VALUES (?, ?, ?, ?)",
            (title, author, genre, price),
        )
        book_ids.append(cur.lastrowid)
    base = datetime(2026, 1, 5)
    # weight popular books higher so top-5 is interesting
    weights = [3 if i < 5 else 1 for i in range(len(book_ids))]
    for _ in range(n_orders):
        book_id = rng.choices(book_ids, weights=weights)[0]
        quantity = rng.choices([1, 1, 1, 2, 2, 3, 5], k=1)[0]
        ordered_at = (base + timedelta(days=rng.randint(0, 270))).isoformat()
        conn.execute(
            "INSERT INTO orders (book_id, quantity, ordered_at) VALUES (?, ?, ?)",
            (book_id, quantity, ordered_at),
        )
