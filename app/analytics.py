"""Aggregate SQL for the sales report, wrapped in getReportData().

One function, one place where the numbers come from — the PDF renderer and
the API both use this, so the report can never disagree with itself.
"""
from .db import get_conn

# The exact aggregate queries behind the report (also pasted in README.md).
TOTALS_SQL = """
SELECT COUNT(*) AS total_orders,
       ROUND(SUM(o.quantity * b.price), 2) AS total_revenue,
       ROUND(AVG(o.quantity * b.price), 2) AS avg_order_value
FROM orders o JOIN books b ON b.id = o.book_id;
"""

TOP_BOOKS_SQL = """
SELECT b.title, b.author, b.genre,
       SUM(o.quantity) AS units_sold,
       ROUND(SUM(o.quantity * b.price), 2) AS revenue
FROM orders o JOIN books b ON b.id = o.book_id
GROUP BY b.id
ORDER BY revenue DESC
LIMIT 5;
"""

BY_GENRE_SQL = """
SELECT b.genre,
       COUNT(*) AS orders,
       SUM(o.quantity) AS units_sold,
       ROUND(SUM(o.quantity * b.price), 2) AS revenue
FROM orders o JOIN books b ON b.id = o.book_id
GROUP BY b.genre
ORDER BY revenue DESC;
"""

RECENT_ORDERS_SQL = """
SELECT o.id, b.title, b.genre, o.quantity,
       ROUND(o.quantity * b.price, 2) AS line_total,
       o.ordered_at
FROM orders o JOIN books b ON b.id = o.book_id
ORDER BY o.ordered_at DESC
LIMIT 60;
"""


def getReportData() -> dict:
    """Run the aggregate queries and return plain-data report payload."""
    conn = get_conn()
    try:
        totals = dict(conn.execute(TOTALS_SQL).fetchone())
        top_books = [dict(r) for r in conn.execute(TOP_BOOKS_SQL).fetchall()]
        by_genre = [dict(r) for r in conn.execute(BY_GENRE_SQL).fetchall()]
        recent = [dict(r) for r in conn.execute(RECENT_ORDERS_SQL).fetchall()]
    finally:
        conn.close()
    return {
        "totals": totals,
        "top_books": top_books,
        "by_genre": by_genre,
        "recent_orders": recent,
    }
