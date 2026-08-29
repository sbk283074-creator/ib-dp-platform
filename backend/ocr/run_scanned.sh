#!/usr/bin/env bash
# Extract a scanned book via a SINGLE python sweep (one model load), skipping
# page-blocks whose chunk file already exists, flushing 10-page chunks as it
# goes (crash-resilient). Merges into book_json/{id}.json when done.
# Usage: run_scanned.sh BOOKID [END] [DPI]
set -u
BOOK="$1"; END="${2:-99999}"; DPI="${3:-90}"
HERE="$(cd "$(dirname "$0")"; pwd)"
cd "$HERE"
PY="/Users/lucas.ma/.workbuddy/binaries/python/envs/default/bin/python"

# find first missing 10-page block
FIRST=""
for ((p=1; p<=END; p+=10)); do
  ck="book_json/_chunk_${BOOK}_$(printf %05d $p).jsonl"
  [ -f "$ck" ] || { FIRST=$p; break; }
done
if [ -z "$FIRST" ]; then
  echo ">>> all blocks done for $BOOK, merging" >&2
  "$PY" extract_books_scanned.py --merge "$BOOK"
  echo "DONE $BOOK"
  exit 0
fi
echo ">>> sweep $BOOK pages $FIRST..$END dpi=$DPI" >&2
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 "$PY" extract_books_scanned.py \
  --book "$BOOK" --sweep "$FIRST" "$END" --dpi "$DPI"
echo ">>> sweep done for $BOOK (may have stopped early), merging available chunks" >&2
"$PY" extract_books_scanned.py --merge "$BOOK"
echo "DONE $BOOK"
