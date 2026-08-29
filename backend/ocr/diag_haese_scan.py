"""(a) Confirm whether Q18's number is truly absent from the text layer (vs
misread to a non-digit), and (b) scan the WHOLE MA-HAESE-CORE1 book for
suspiciously-tall bands = merged questions caused by missing colored qnums.
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as B
import pypdfium2 as pdfium

BOOK = next(b for b in E.BOOKS if b['id'] == 'MA-HAESE-CORE1')
doc = pdfium.PdfDocument(BOOK['path'])

# ---- (a) raw char dump in the Q18 region of PDF page 480 ----
print("=== (a) raw char text in y-region 1730-1875 of PDF page 480 ===")
page = doc[480 - 1]
H = float(page.get_height())
tp = page.get_textpage()
n = tp.count_chars()
seen = []
for i in range(n):
    try:
        b = tp.get_charbox(i)
        x0, y0, x1, y1 = float(b[0]), float(b[1]), float(b[2]), float(b[3])
    except Exception:
        continue
    top = H - y1
    if 1730 <= top <= 1875:
        seen.append((round(top), round(x0), tp.get_text_range(i, 1)))
# print unique-ish rows
rows = {}
for top, x0, ch in seen:
    rows.setdefault(top, [])
    rows[top].append((x0, ch))
for top in sorted(rows):
    s = ''.join(c for _, c in sorted(rows[top]))
    print(f"  top={top:5d} | {s!r}")
tp.close()

# ---- (b) whole-book tall-band scan ----
print("\n=== (b) tall-band (merged-question) scan over all pages ===")
patterns = BOOK.get('exercise_patterns') or E.PRACTICE_PATTERNS
issues = []
for i in range(len(doc)):
    page = doc[i]
    try:
        ok, hdr, kind = B.is_exercise_page_pdfium(page, patterns=patterns, min_markers=3)
    except Exception:
        continue
    if not ok:
        continue
    try:
        bands = B.question_bands_pdfium(page, cfg=BOOK.get('seg'))
    except Exception:
        continue
    if len(bands) < 2:
        continue
    hs = sorted(b[2] - b[1] for b in bands)
    med = hs[len(hs)//2]
    tall = [b for b in bands if (b[2]-b[1]) > 2.2 * max(med, 40)]
    if tall:
        issues.append((i+1, hdr, kind, len(bands),
                       [(b[0], round(b[2]-b[1])) for b in tall]))
print(f"exercise pages scanned; pages with suspiciously-tall bands: {len(issues)}")
for pg, hdr, kind, nb, tall in issues:
    print(f"  PDF p{pg:3d}  hdr={hdr!r:24} kind={kind:12} nbands={nb} tall={tall}")
