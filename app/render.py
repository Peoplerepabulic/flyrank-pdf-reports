"""Render the sales report HTML to PDF with headless Chromium (Playwright).

Print CSS handles pagination honestly:
- thead repeats on every page (display: table-header-group)
- no table row is ever split across a page break (break-inside: avoid)
"""
import os

TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Bookstore Sales Report</title>
<style>
  @page { size: A4; margin: 18mm 15mm; }
  body { font-family: Helvetica, Arial, sans-serif; color: #1a1a1a; font-size: 11pt; }
  h1 { font-size: 20pt; margin-bottom: 2px; }
  .meta { color: #666; margin-bottom: 18px; }
  h2 { font-size: 14pt; margin-top: 26px; border-bottom: 2px solid #1a1a1a; padding-bottom: 4px; }
  table { width: 100%; border-collapse: collapse; margin-top: 8px; }
  thead { display: table-header-group; }
  th { background: #1a1a1a; color: #fff; text-align: left; padding: 6px 8px; }
  td { padding: 5px 8px; border-bottom: 1px solid #ddd; }
  tr { break-inside: avoid; }
  .kpi { display: flex; gap: 24px; margin: 12px 0; }
  .kpi div { flex: 1; background: #f4f4f4; padding: 10px 14px; border-radius: 6px; }
  .kpi .v { font-size: 18pt; font-weight: bold; }
  .kpi .l { color: #666; font-size: 9pt; }
</style></head><body>
<h1>Bookstore Sales Report</h1>
<div class="meta">Generated __GENERATED_AT__ &middot; source: report.db (bookstore orders)</div>

<h2>Summary</h2>
<div class="kpi">
  <div><div class="v">__TOTAL_ORDERS__</div><div class="l">TOTAL ORDERS</div></div>
  <div><div class="v">$__TOTAL_REVENUE__</div><div class="l">TOTAL REVENUE</div></div>
  <div><div class="v">$__AVG_ORDER__</div><div class="l">AVG ORDER VALUE</div></div>
</div>

<h2>Top 5 Books by Revenue</h2>
<table><thead><tr><th>#</th><th>Title</th><th>Author</th><th>Genre</th><th>Units</th><th>Revenue</th></tr></thead>
<tbody>__TOP_BOOKS_ROWS__</tbody></table>

<h2>Revenue by Genre</h2>
<table><thead><tr><th>Genre</th><th>Orders</th><th>Units</th><th>Revenue</th></tr></thead>
<tbody>__GENRE_ROWS__</tbody></table>

<h2>Recent Orders (latest 60)</h2>
<table><thead><tr><th>ID</th><th>Title</th><th>Genre</th><th>Qty</th><th>Line total</th><th>Date</th></tr></thead>
<tbody>__RECENT_ROWS__</tbody></table>
</body></html>"""


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_html(data: dict, generated_at: str) -> str:
    t = data["totals"]
    top_rows = "".join(
        f"<tr><td>{i}</td><td>{_esc(b['title'])}</td><td>{_esc(b['author'])}"
        f"</td><td>{_esc(b['genre'])}</td><td>{b['units_sold']}</td>"
        f"<td>${b['revenue']}</td></tr>"
        for i, b in enumerate(data["top_books"], 1)
    )
    genre_rows = "".join(
        f"<tr><td>{_esc(g['genre'])}</td><td>{g['orders']}</td>"
        f"<td>{g['units_sold']}</td><td>${g['revenue']}</td></tr>"
        for g in data["by_genre"]
    )
    recent_rows = "".join(
        f"<tr><td>{o['id']}</td><td>{_esc(o['title'])}</td>"
        f"<td>{_esc(o['genre'])}</td><td>{o['quantity']}</td>"
        f"<td>${o['line_total']}</td><td>{_esc(o['ordered_at'][:10])}</td></tr>"
        for o in data["recent_orders"]
    )
    return (
        TEMPLATE.replace("__GENERATED_AT__", _esc(generated_at))
        .replace("__TOTAL_ORDERS__", str(t["total_orders"]))
        .replace("__TOTAL_REVENUE__", str(t["total_revenue"]))
        .replace("__AVG_ORDER__", str(t["avg_order_value"]))
        .replace("__TOP_BOOKS_ROWS__", top_rows)
        .replace("__GENRE_ROWS__", genre_rows)
        .replace("__RECENT_ROWS__", recent_rows)
    )


def render_pdf(html: str, out_path: str) -> str:
    """Render HTML to PDF at out_path. Returns out_path."""
    from playwright.sync_api import sync_playwright

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(path=out_path, format="A4", print_background=True)
        browser.close()
    return out_path
