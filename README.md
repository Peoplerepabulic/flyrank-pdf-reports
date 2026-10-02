# PDF Report Generator (FlyRank BE-08)

A self-built report pipeline: query data → render PDF → serve it, with
idempotent generation. No report SaaS, no shortcuts — SQL, HTML, and a
headless browser, wired together.

## What it does

`POST /reports` aggregates ~200 bookstore orders from SQLite, renders a
multi-page sales PDF with headless Chromium, stores the file on disk, and
returns `201 {id, file_url}`. `GET /reports/{id}` returns the record;
`GET /reports/{id}/file` downloads the PDF. The JSON record carries only the
link — never the file bytes.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# Chromium for Playwright (one-time; the venv's installer times out in some
# sandboxes, so fetch it directly and unpack into the expected layout):
#   curl -sSL -o /tmp/chrome.zip https://cdn.playwright.dev/builds/cft/153.0.8010.12/linux64/chrome-linux64.zip
#   mkdir -p ~/.cache/ms-playwright/chromium-1243 && unzip -q /tmp/chrome.zip -d ~/.cache/ms-playwright/chromium-1243
#   mv ~/.cache/ms-playwright/chromium-1243/chrome-linux64 ~/.cache/ms-playwright/chromium-1243/chrome-linux
#   (same for chrome-headless-shell-linux64.zip -> chromium_headless_shell-1243/)
.venv/bin/python scripts/seed.py   # idempotent: 20 books, 200 orders
.venv/bin/uvicorn app.main:app --port 8124
```

Then:

```bash
curl -X POST localhost:8124/reports
# {"id":1,"hash":"…","file_url":"/reports/1/file","created_at":"…"}  (201)
curl localhost:8124/reports/1
curl -OJ localhost:8124/reports/1/file   # downloads report_1.pdf
```

## The aggregate SQL (the exact queries behind the report)

```sql
-- two totals + average
SELECT COUNT(*) AS total_orders,
       ROUND(SUM(o.quantity * b.price), 2) AS total_revenue,
       ROUND(AVG(o.quantity * b.price), 2) AS avg_order_value
FROM orders o JOIN books b ON b.id = o.book_id;

-- top 5 books by revenue
SELECT b.title, b.author, b.genre,
       SUM(o.quantity) AS units_sold,
       ROUND(SUM(o.quantity * b.price), 2) AS revenue
FROM orders o JOIN books b ON b.id = o.book_id
GROUP BY b.id ORDER BY revenue DESC LIMIT 5;

-- revenue grouped by genre
SELECT b.genre, COUNT(*) AS orders,
       SUM(o.quantity) AS units_sold,
       ROUND(SUM(o.quantity * b.price), 2) AS revenue
FROM orders o JOIN books b ON b.id = o.book_id
GROUP BY b.genre ORDER BY revenue DESC;
```

All three (plus the 60-row recent-orders query) live in
`app/analytics.py::getReportData()` — one function, so the PDF can never
disagree with itself.

## Pagination, handled honestly

The 60-row recent-orders table spans 3 pages. Print CSS guarantees:
`thead { display: table-header-group; }` (header repeats every page) and
`tr { break-inside: avoid; }` (no row is ever split across a page break).
Verified in the generated PDF: 3 pages, headers on each, no split rows.

## Idempotency

The report payload is hashed (SHA-256 over canonical JSON). A repeat `POST`
with identical data returns the existing report id (`200`, same id) instead
of rendering again — rapid double-submits produce exactly one PDF file.
Verified live: two rapid POSTs → both returned id 1, one file on disk.

## Download proof

`GET /reports/1/file` → `200 application/pdf`, ~39.8 KB, opens as a 3-page
A4 report (summary KPIs, top-5 table, genre breakdown, 60 recent orders).

## Stages (what was built when)

- **Stage 0–1:** `report.db` schema + deterministic seed script (20 books,
  200 orders; re-runnable, never duplicates).
- **Stage 2:** aggregate SQL wrapped in `getReportData()`.
- **Stage 3:** HTML template + Playwright/Chromium PDF renderer with print CSS.
- **Stage 4:** files on disk (`reports/report_<id>.pdf`), DB stores the path;
  `POST /reports` (201), `GET /reports/{id}`, `GET /reports/{id}/file`.
- **Stage 5:** content-hash idempotency (repeat POST → same id, one file).
- **Stage 6:** this README.
