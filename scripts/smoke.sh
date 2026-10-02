#!/usr/bin/env bash
# Smoke test for the report API. Starts the server, exercises every endpoint,
# verifies idempotency (two rapid POSTs -> same id, one PDF), then stops it.
set -u
cd "$(dirname "$0")/.."
PORT="${PORT:-8124}"
BASE="http://localhost:$PORT"

.venv/bin/python scripts/seed.py >/dev/null
# fresh state: drop any reports from previous runs so the first POST is a 201
rm -f reports/*.pdf
.venv/bin/python -c "
import sqlite3, os
db = os.environ.get('REPORT_DB', 'data/report.db')
conn = sqlite3.connect(db)
conn.execute('DELETE FROM reports')
conn.commit(); conn.close()
"
.venv/bin/uvicorn app.main:app --port "$PORT" >/tmp/pdf_smoke.log 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
sleep 4

fail() { echo "SMOKE FAIL: $1"; exit 1; }

R1=$(curl -s -w "\n%{http_code}" -X POST "$BASE/reports")
[ "$(echo "$R1" | tail -1)" = "201" ] || fail "POST /reports -> $(echo "$R1" | tail -1), want 201"
ID=$(echo "$R1" | head -1 | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
URL=$(echo "$R1" | head -1 | python3 -c "import json,sys; print(json.load(sys.stdin)['file_url'])")
echo "created report id=$ID url=$URL"

R2=$(curl -s -X POST "$BASE/reports")
ID2=$(echo "$R2" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
[ "$ID" = "$ID2" ] || fail "idempotent re-POST gave id=$ID2, want $ID"
NFILES=$(ls reports/report_*.pdf | wc -l)
[ "$NFILES" = "1" ] || fail "expected 1 PDF on disk, found $NFILES"
echo "idempotent re-POST -> same id=$ID2, one PDF on disk"

curl -s "$BASE/reports/$ID" | grep -q '"id"' || fail "GET /reports/$ID"
CT=$(curl -s -o /tmp/smoke.pdf -w "%{content_type}" "$BASE/reports/$ID/file")
[ "$CT" = "application/pdf" ] || fail "GET file content-type=$CT"
[ -s /tmp/smoke.pdf ] || fail "downloaded PDF is empty"
echo "downloaded PDF: $(wc -c < /tmp/smoke.pdf) bytes"

[ "$(curl -s -o /dev/null -w "%{http_code}" "$BASE/reports/999999")" = "404" ] \
  || fail "GET unknown id, want 404"
echo "GET unknown id -> 404"

echo "SMOKE OK"
