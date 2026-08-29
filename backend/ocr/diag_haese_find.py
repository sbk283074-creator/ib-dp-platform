"""Locate the real PDF page for book page 482 / 'Review set 17B' in Haese Core 1,
and confirm the colored-qnum merge by inspecting the detector's bands there.
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as B
import pypdfium2 as pdfium

BOOK = next(b for b in E.BOOKS if b['id'] == 'MA-HAESE-CORE1')
doc = pdfium.PdfDocument(BOOK['path'])
n = len(doc)
print(f"total PDF pages = {n}")

target_pdf = None
review_pdf = None
for i in range(n):
    page = doc[i]
    txt = '\n'.join(t for _, t, _ in B.pdfium_lines(page))
    # printed page number: header like '482 ...' or 'Review set 17B'
    if 'Review set 17B' in txt or 'REVIEW SET 17B' in txt:
        review_pdf = i + 1
        # capture the printed page number if present
        m = re.match(r'^\s*(\d{1,4})\b', txt.strip())
        print(f"  PDF page {i+1}: contains 'Review set 17B'  (first line: {txt.strip().splitlines()[0][:60]!r})")
    if re.search(r'\b482\b', txt[:200]):
        # crude: printed page number near top
        target_pdf = i + 1

print(f"\nReview set 17B on PDF page: {review_pdf}")
print(f"PDF page whose top text mentions 482: {target_pdf}")

# Inspect the review-set page
if review_pdf:
    page = doc[review_pdf - 1]
    H = float(page.get_height()); W = float(page.get_width())
    print(f"\n=== Review set 17B page: PDF {review_pdf}, H={H} W={W} ===")
    lines = B.pdfium_lines(page)
    margin = B._seg_cfg(BOOK.get('seg'))['qnum_margin'] * W
    for top, t, x0 in lines:
        if top > 0.40 * H:  # bottom 60% = the questions
            tag = B._line_start_number(t, True)
            alt = B._line_start_number_alt_glyph(t)
            bare = B._bare_dot(t)
            mark = ''
            if tag is not None: mark = f'  QNUM={tag}'
            elif alt is not None: mark = f'  ALT={alt}'
            elif bare: mark = '  BAREDOT'
            print(f"  top={top:7.1f} x0={x0:6.1f} margin={margin:.1f} | {t!r}{mark}")
    print("\n  question_bands_pdfium:")
    for num, y0, y1 in B.question_bands_pdfium(page, cfg=BOOK.get('seg')):
        print(f"    qnum={num} y0={y0:.1f} y1={y1:.1f} h={y1-y0:.1f}")
