#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Research helper: map a text-based book's concentrated-practice pages.

For a given book id (from extract_books.BOOKS), scan every page and report
pages that look like concentrated-practice pages (end-of-chapter / mixed
practice / review set / self-test / chapter review). For each such page
print layout facts: two-column? gutter? #raster images? #question markers.
Also print a count of how many practice pages and an estimated question total.

Usage: python research_text.py <BOOKID> [--pages N]
"""
import os, re, sys, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import booklib as B
from extract_books import BOOKS

PRACTICE_PATTERNS = [
    r'end[\s\-]?of[\s\-]?chapter\s+(questions?|exercises?)',
    r'end[\s\-]?of[\s\-]?topic\s+questions?',
    r'mixed\s+practice',
    r'mixed\s+review',
    r'review\s+set',
    r'chapter\s+review',
    r'self[\s\-]?test',
    r'test\s+yourself',
    r'practice\s+questions?',
    r'mixed\s+questions?',
    r'revision\s+(exercise|set|questions?)',
    r'exam[\s\-]?style\s+(questions?|practice)',
    r'end[\s\-]?of[\s\-]?unit',
    r'summary\s+questions?',
    r'check\s+your\s+progress',
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('book')
    ap.add_argument('--pat', action='append', default=[])
    ap.add_argument('--allpages', action='store_true', help='print every page, not just practice')
    args = ap.parse_args()
    book = next((b for b in BOOKS if b['id'] == args.book and not b.get('scanned') and not b.get('skip_extract')), None)
    if not book:
        print(f"no text book {args.book}"); sys.exit(1)
    pats = args.pat if args.pat else PRACTICE_PATTERNS
    patterns_re = re.compile('|'.join(pats), re.I)
    cfg = book.get('seg')
    pdf = B.pdfium.PdfDocument(book['path'])
    n = len(pdf)
    print(f"# BOOK {book['id']}  {book['title']}")
    print(f"# pages={n}  path={book['path']}")
    print(f"# practice patterns: {pats}")
    print("-" * 100)
    practice_pages = 0
    est_q = 0
    for i in range(n):
        page = pdf[i]
        lines = B.pdfium_lines(page)
        txt = '\n'.join(t for _, t, _ in lines)
        head = '\n'.join(t for _, t, _ in lines[:10])
        # also scan full text for any practice heading (some appear mid/lower)
        m = patterns_re.search(txt)
        if not m:
            if args.allpages:
                print(f"p{i+1:4d}  (no practice heading)")
            page = None; continue
        # it's a practice page candidate
        practice_pages += 1
        kind, gutter = B.detect_columns(page)
        imgs = B.page_image_bboxes(page)
        bands = B.question_bands_pdfium(page, cfg=cfg)
        sec = B.section_for_page_pdfium(page, None)
        # count distinct question numbers
        qnums = [b[0] for b in bands if b[0] is not None]
        # estimate: number of digit question bands
        nq = len(bands)
        est_q += nq
        gtx = f"{gutter:.0f}" if gutter else "-"
        print(f"p{i+1:4d}  cols={kind:8s} gutter={gtx:>5} imgs={len(imgs):2d} bands={nq:3d} qrange={min(qnums) if qnums else '-'}..{max(qnums) if qnums else '-'}  | {sec[:40]}")
        if args.allpages == False and practice_pages <= 3:
            # show the heading line for first few
            print(f"        heading: {m.group(0).strip()!r}")
    print("-" * 100)
    print(f"PRACTICE PAGES ~ {practice_pages}   ESTIMATED QUESTIONS ~ {est_q}")
    pdf.close()

if __name__ == '__main__':
    main()
