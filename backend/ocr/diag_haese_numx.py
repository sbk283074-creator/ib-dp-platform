"""diag_haese_numx.py — find the x0 (indent) of text-layer question numbers on
each page, to anchor the visual coloured-number scan adaptively.

Print, per page, the text-layer LINES whose text is a bare integer (the
question number line) or starts with a digit, with (x0, y, text). This tells us
where question numbers live spatially so we can scan for their coloured
counterparts at the same x0.
"""
import re
import booklib as B
import extract_books as E
import pypdfium2 as pdfium

BOOK_ID = 'MA-HAESE-CORE1'
book = next(b for b in E.BOOKS if b['id'] == BOOK_ID)
doc = pdfium.PdfDocument(book['path'])

INT_RE = re.compile(r'^\s*(\d{1,2})\s*$')
for bp in [480, 482, 486, 492]:
    page = doc[bp-1]
    W = float(page.get_width()); H = float(page.get_height())
    print(f"\n===== bp={bp}  W={W:.0f} =====")
    for top, t, x0 in B.pdfium_lines(page):
        m = INT_RE.match(t)
        if m and 0.05*H <= top <= 0.95*H:
            print(f"      x0={x0:7.1f} y={top:7.1f}  {t!r}")
        elif re.match(r'^\s*\d{1,2}\b', t) and x0 < 0.2*W and 0.05*H <= top <= 0.95*H:
            print(f"      x0={x0:7.1f} y={top:7.1f}  STARTS-WITH-DIGIT {t[:40]!r}")
doc.close()
