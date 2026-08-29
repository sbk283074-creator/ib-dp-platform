import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
# dry-run single book, write json, report counts
import argparse
BOOK_ID = sys.argv[1] if len(sys.argv) > 1 else 'PH-OX-2023'
book = next(b for b in E.BOOKS if b['id'] == BOOK_ID)
# monkeypatch: call extract_text_book_pdfium in dry-run mode
qs = E.extract_text_book_pdfium(book, dry_run=True)
print(f"{BOOK_ID}: dry-run extracted {len(qs)} questions")
from collections import Counter
bp = Counter(q.get('book_page') for q in qs)
# show pages with >1 question (potential over-split) in the 700-720 range
multi = {p: c for p, c in bp.items() if c > 1 and 700 <= p <= 720}
print(f"  pages 700-720 with >1 q (potential over-split): {multi}")
# show total pages with >1
multi_all = {p: c for p, c in bp.items() if c > 1}
print(f"  TOTAL pages with >1 q: {len(multi_all)}  (sum of extras={sum(c-1 for c in multi_all.values())})")
