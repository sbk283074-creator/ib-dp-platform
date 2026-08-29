"""diag_haese_visual_split.py — verify the coloured-number merge hypothesis on
MA-HAESE-CORE1 and decide the injection point.

For a list of pages, print:
  * column kind (detect_columns)
  * text-layer bands from question_bands_pdfium (single-col path)
  * visual coloured qnum y-centres (visual_qnum_tops, min_sat=80)
This tells us (a) whether affected pages are single- or two-column, and
(b) whether visual_qnum_tops cleanly separates merged question numbers.
"""
import os, sys
import booklib as B
import extract_books as E
import pypdfium2 as pdfium

BOOK_ID = 'MA-HAESE-CORE1'
book = next(b for b in E.BOOKS if b['id'] == BOOK_ID)
pdf_path = book['path']
cfg = book.get('seg', {})

# pages to inspect (raw PDF page numbers). Reported merge at bp=482 (raw 483).
PAGES = [480, 481, 482, 483, 484, 485, 486, 487, 488, 489, 490, 491, 492, 493]

doc = pdfium.PdfDocument(pdf_path)
print(f"book={BOOK_ID} pages={len(doc)} gutter_x={book.get('gutter_x')} two_col={book.get('two_col')}")
for bp in PAGES:
    i = bp - 1
    if i < 0 or i >= len(doc):
        print(f"  bp={bp}: OUT OF RANGE"); continue
    page = doc[i]
    W = float(page.get_width()); H = float(page.get_height())
    kind, gutter = B.detect_columns(page)
    try:
        bands = B.question_bands_pdfium(page, cfg=cfg)
    except Exception as e:
        bands = []; print(f"  bp={bp}: bands error {e}")
    # visual coloured qnums across full left margin of the page
    vis = B.visual_qnum_tops(page, dpi=200, x_frac_lo=0.0, x_frac_hi=0.14,
                             min_sat=80, y_min=0.04, y_max=0.96)
    btoks = [t for (t, _, _) in bands]
    print(f"  bp={bp}: kind={kind} W={W:.0f} bands={len(bands)} toks={btoks}")
    # show visual qnums that fall inside each band (the merge signature)
    for (t, y0, y1) in bands:
        inside = [round(y, 1) for y in vis if y0 - 2 <= y <= y1 + 2]
        if inside:
            print(f"      band tok={t} y0={y0:.0f} y1={y1:.0f} -> visual qnums INSIDE: {inside}")
    if not bands:
        print(f"      (no text bands; visual qnums on page: {[round(y,1) for y in vis]})")
doc.close()
