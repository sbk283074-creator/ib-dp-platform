"""diag_haese_leftedge.py — detect question numbers as digit-sized connected
components at the LEFT EDGE of their column (nothing to their left within the
column). This catches BOTH black and coloured question numbers regardless of
indent or two-column layout, and excludes body digits (which have ink to their
left).

Test on pages with known ground truth:
  bp=480 -> 6 (16-21),  bp=482 -> 8 (13-20, 15 coloured),
  bp=486 -> ~14,        bp=492 -> ~15-19
"""
import booklib as B
import extract_books as E
import pypdfium2 as pdfium

BOOK_ID = 'MA-HAESE-CORE1'
book = next(b for b in E.BOOKS if b['id'] == BOOK_ID)
doc = pdfium.PdfDocument(book['path'])

def question_number_ys(page, dpi=200):
    W = float(page.get_width()); H = float(page.get_height())
    kind, gutter = B.detect_columns(page)
    cols = [(0.0, gutter)] if (kind == 'two-col' and gutter) else [(0.0, W)]
    ink, (Wp, Hp), scale = B.visual_ink_mask(page, dpi=dpi, x_frac_lo=0.0,
                                             x_frac_hi=1.0, min_sat=0, dark_lum=150)
    if not ink:
        return []
    from collections import deque
    seen = set(); cands = []
    for seed in ink:
        if seed in seen:
            continue
        stack = deque([seed]); seen.add(seed); ys=[]; xs=[]
        while stack:
            y, x = stack.popleft(); ys.append(y); xs.append(x)
            for dy, dx in ((-1,0),(1,0),(0,-1),(0,1)):
                nb=(y+dy,x+dx)
                if nb in ink and nb not in seen: seen.add(nb); stack.append(nb)
        h=(max(ys)-min(ys)+1)/scale; w=(max(xs)-min(xs)+1)/scale
        if not (14.0 <= h <= 23.0 and 5.0 <= w <= 28.0):
            continue
        x0=min(xs)/scale; x1=max(xs)/scale; yc=(min(ys)+max(ys))/2.0/scale
        if not (0.05*H <= yc <= 0.96*H):
            continue
        # which column?
        col_left = 0.0
        for (cl, cr) in cols:
            if cl - 1 <= x0 <= cr + 1:
                col_left = cl; break
        # left-edge test: no ink in [col_left, x0-1] within the y-band
        yb0 = int(round((yc - 0.5*h)*scale)); yb1 = int(round((yc + 0.5*h)*scale))
        xa = int(round(col_left*scale)); xb = int(round((x0 - 1.0)*scale))
        if xb <= xa:
            left_empty = True
        else:
            left_empty = not any((py, px) in ink for py in range(yb0, yb1+1) for px in range(xa, xb+1))
        if not left_empty:
            continue
        cands.append((round(yc,1), round(x0,1), round(w,1)))
    return sorted(cands)

EXPECT = {480: 6, 482: 8, 486: 14, 492: 16}
for bp in [480, 482, 486, 492]:
    c = question_number_ys(doc[bp-1])
    print(f"bp={bp}: count={len(c)}  expect~{EXPECT.get(bp)}")
    for (y, x0, w) in c:
        print(f"      y={y:7.1f} x0={x0:6.1f} w={w:5.1f}")
doc.close()
