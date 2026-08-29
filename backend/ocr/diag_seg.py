#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnostic: for each text-based book, dump per-page question markers and the
resulting bands so we can TUNE per-book seg configs without a full re-extract.

Only "interesting" pages are printed:
  - exercise pages (detected by is_exercise_page_pdfium), and
  - pages that have >=3 left-margin candidate numbers but were NOT classified
    (potential under-rejection / wrong threshold).

Usage:
  python diag_seg.py --book MA-HODDER-2019 --limit 60
  python diag_seg.py            (all text books)
"""
import os, re, argparse, sys
import booklib as B
import pypdfium2 as pdfium

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract_books as EB   # reuse BOOKS registry + MATH_CHAPTER_END

DP = "/Users/lucas.ma/Downloads/dp learning"


def candidate_markers(page, sc):
    """List (top_frac, num_or_None, x0_frac, strict_ok) for every line-start
    candidate, before monotonic filtering."""
    H = float(page.get_height()); W = float(page.get_width())
    margin = sc['qnum_margin'] * W
    out = []
    for top, text, x0 in B.pdfium_lines(page):
        if (0 <= top < 0.05 * H or top > 0.94 * H) and len(text) < 15:
            continue
        if top < 0.06 * H and re.match(r'^\d{1,3}\s+[A-Z]{2,}', text):
            continue
        num = B._line_start_number(text, sc['strict_qnum'])
        strict_ok = num is not None
        if num is None and B._bare_dot(text):
            num = None  # bare dot
            strict_ok = True
        if num is not None or B._bare_dot(text):
            out.append((round(top / H, 3), num, round(x0 / W, 3),
                        strict_ok, x0 <= margin))
    return out


def diag_book(book, limit):
    seg = book.get('seg')
    sc = B._seg_cfg(seg)
    patterns = book.get('exercise_patterns')
    pdf = pdfium.PdfDocument(book['path'])
    n = len(pdf)
    print(f"\n========== {book['id']}  ({book['title']}) ==========")
    print(f"  seg={seg}  patterns={patterns and len(patterns)}  pages={n}")
    shown = 0
    for i in range(n):
        page = pdf[i]
        try:
            ok, hdr = B.is_exercise_page_pdfium(page, patterns=patterns,
                                                min_markers=sc['min_markers'])
        except Exception as e:
            ok, hdr = False, None
        cands = candidate_markers(page, sc)
        left_nums = [c for c in cands if c[4]]
        bands = []
        if ok:
            try:
                bands = B.question_bands_pdfium(page, cfg=seg)
            except Exception as e:
                bands = []
        interesting = ok or len(left_nums) >= 3
        if not interesting:
            page = None; continue
        shown += 1
        H = float(page.get_height()); W = float(page.get_width())
        print(f"\n  -- p{i+1}  exercise={ok} hdr={hdr!r}  "
              f"#left_nums={len(left_nums)} #bands={len(bands)}")
        if ok:
            # show bands compactly
            bs = ", ".join(f"{b[0]}@{int(b[1])}-{int(b[2])}" for b in bands)
            print(f"     BANDS: {bs}")
        # show raw candidates (top%, num, x0frac, strict_ok, left_ok)
        cc = " | ".join(f"{c[0]:.2f}:{c[1]}{'' if c[3] else '?'}{'L' if c[4] else 'i'}"
                        for c in cands[:25])
        print(f"     CAND: {cc}")
        page = None
        if limit and shown >= limit:
            break
    pdf.close()
    print(f"  (shown {shown} interesting pages)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--book')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()
    targets = [b for b in EB.BOOKS
               if not b.get('scanned') and not b.get('skip_extract')]
    if args.book:
        targets = [b for b in targets if b['id'] == args.book]
    for b in targets:
        diag_book(b, args.limit)


if __name__ == '__main__':
    main()
