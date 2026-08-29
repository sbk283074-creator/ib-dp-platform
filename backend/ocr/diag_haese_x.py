"""diag_haese_x.py — measure the x-position of question numbers vs body digits.

For a couple of pages we print:
  * text-layer LINES that start at the left margin (x0 < 0.06*W) with their
    y and text (these are the real question-start lines, number black or the
    first line of a question whose coloured number is missing).
  * visual LARGE coloured components (h in [15,22], w in [6,26]) with their
    (x0, y) so we can see whether real question numbers sit at the extreme
    left margin, distinct from body digits.
"""
import booklib as B
import extract_books as E
import pypdfium2 as pdfium

BOOK_ID = 'MA-HAESE-CORE1'
book = next(b for b in E.BOOKS if b['id'] == BOOK_ID)
doc = pdfium.PdfDocument(book['path'])

def comps_geom_x(page):
    ink, (Wp, Hp), scale = B.visual_ink_mask(page, dpi=200, x_frac_lo=0.0,
                                             x_frac_hi=0.22, min_sat=80, dark_lum=150)
    if not ink:
        return []
    H = float(page.get_height()); W = float(page.get_width())
    from collections import deque
    seen = set(); out = []
    for seed in ink:
        if seed in seen: continue
        stack = deque([seed]); seen.add(seed); ys=[]; xs=[]
        while stack:
            y, x = stack.popleft(); ys.append(y); xs.append(x)
            for dy, dx in ((-1,0),(1,0),(0,-1),(0,1)):
                nb=(y+dy,x+dx)
                if nb in ink and nb not in seen: seen.add(nb); stack.append(nb)
        h=(max(ys)-min(ys)+1)/scale; w=(max(xs)-min(xs)+1)/scale
        if 15.0 <= h <= 22.0 and 6.0 <= w <= 26.0:
            yc=(min(ys)+max(ys))/2.0/scale
            x0=min(xs)/scale; x1=max(xs)/scale
            if 0.04*H <= yc <= 0.96*H:
                out.append((round(x0,1), round(yc,1), round(w,1)))
    return out

for bp in [492, 486, 482]:
    page = doc[bp-1]
    W = float(page.get_width()); H = float(page.get_height())
    print(f"\n===== bp={bp}  W={W:.0f} =====")
    print("  -- text-layer LEFT-MARGIN lines (x0 < 0.06*W) --")
    for top, t, x0 in B.pdfium_lines(page):
        if x0 < 0.06*W and 0.05*H <= top <= 0.95*H:
            print(f"      x0={x0:6.1f} y={top:7.1f}  {t[:60]!r}")
    print("  -- visual large coloured components (x0, y, w) --")
    for (x0, y, w) in sorted(comps_geom_x(page)):
        print(f"      x0={x0:6.1f} y={y:7.1f} w={w:5.1f}")
doc.close()
