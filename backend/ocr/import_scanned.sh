#!/usr/bin/env bash
# Merge a scanned book's chunk files and import into the running backend.
# Usage: import_scanned.sh BOOKID [API_BASE]
set -u
BOOK="$1"; API="${2:-http://localhost:3011}"
HERE="$(cd "$(dirname "$0")"; pwd)"
cd "$HERE"
PY="/Users/lucas.ma/.workbuddy/binaries/python/envs/default/bin/python"

echo ">>> merging $BOOK" >&2
"$PY" extract_books_scanned.py --merge "$BOOK" || { echo "merge failed"; exit 1; }

JSON="book_json/${BOOK}.json"
[ -f "$JSON" ] || { echo "no merged json $JSON"; exit 1; }
QCOUNT=$("$PY" -c "import json;print(len(json.load(open('$JSON'))['questions']))")
echo ">>> importing $BOOK ($QCOUNT questions) to $API" >&2

# curl must bypass the HTTP_PROXY env that otherwise intercepts localhost
curl --noproxy '*' -s -X POST "$API/api/books/import" \
  -H "Content-Type: application/json" \
  --data-binary @"$JSON" \
  -w "\nHTTP %{http_code}\n"
