"""Diagnostic: confirm WHY Haese Core 1 review-set question numbers of a
different colour get missed by the qnum detector -> adjacent questions merge.

Renders the text-layer lines of a given PDF page and, for each left-margin
line, prints what `_line_start_number` / `question_bands_pdfium` would see,
so we can see the colored-number failure mode directly.
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as B

DP = E.DP  # book root, imported from extract_books
BOOK = next(b for b in E.BOOKS if b['id'] == 'MA-HAESE-CORE1')
pdf = BOOK['path']
import pypdfium2 as pdfium

# book page 482 -> 2-up PDF page 241 (1 pdf page = 2 book pages)
BOOKP = 482
PDFP = (BOOKP + 1) // 2  # 241
print(f"PDF={pdf}")
print(f"book page {BOOKP} -> PDF page {PDFP} (0-based idx {PDFP-1})")

doc = pdfium.PdfDocument(pdf)
page = doc[PDFP - 1]
H = float(page.get_height()); W = float(page.get_width())
print(f"page H={H} W={W}")

lines = B.pdfium_lines(page)
print(f"\n=== ALL LINES (top, x0, text) count={len(lines)} ===")
for top, t, x0 in lines:
    tag = B._line_start_number(t, True)
    alt = B._line_start_number_alt_glyph(t)
    bare = B._bare_dot(t)
    mark = ''
    if tag is not None: mark = f'  <-- QNUM={tag}'
    elif alt is not None: mark = f'  <-- ALT={alt}'
    elif bare: mark = '  <-- BAREDOT'
    # only print lines with a number-ish start or in the bottom 40% of page
    if mark or top > 0.55 * H:
        print(f"  top={top:7.1f} x0={x0:6.1f} | {t!r}{mark}")

print("\n=== question_bands_pdfium output ===")
bands = B.question_bands_pdfium(page, cfg=BOOK.get('seg'))
for num, y0, y1 in bands:
    print(f"  qnum={num} y0={y0:.1f} y1={y1:.1f} h={y1-y0:.1f}")

# Also: show the raw glyph colours of any leading digit near the bottom,
# to confirm a colour difference. pypdfium charbox does not expose colour,
# so instead report which lines START with a digit but were rejected because
# x0>margin or body-shape failed.
print("\n=== leading-digit lines the detector REJECTED (candidates for colour bug) ===")
margin = B._seg_cfg(BOOK.get('seg'))['qnum_margin'] * W
for top, t, x0 in lines:
    if re.match(r'^(\d{1,3})', t):
        num = B._line_start_number(t, True)
        if num is None:
            print(f"  top={top:7.1f} x0={x0:6.1f} margin={margin:.1f} | {t!r}  (rejected)")
