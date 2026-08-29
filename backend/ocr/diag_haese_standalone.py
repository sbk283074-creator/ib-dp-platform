"""diag_haese_standalone.py — test the "standalone line-start digit" detector.

A question number (black OR coloured) sits at the left margin (x0 ~ 95-175)
as a digit-sized glyph (h in [15,22], w in [6,26]) with EMPTY ink immediately
to its right (line-start: the number is followed by a gap, then question text).
Body digits are embedded (adjacent glyph ink to the right) so they are excluded.

We drop min_sat (include black ink too) so both black and coloured numbers are
caught. Test on pages with known ground truth:
  bp=480 -> expect 6 (toks 16-21, all black)
  bp=482 -> expect 8 (13-20, 15 coloured/missing)
  bp=486 -> expect ~14 (5 .. ~18)
  bp=492 -> expect ~15
"""
import booklib as B
import extract_books as E
import pypdfium2 as pdfium

BOOK_ID = 'MA-HAESE-CORE1'
book = next(b for b in E.BOOKS if b['id'] == BOOK_ID)
doc = pdfium.PdfDocument(book['path'])

def standalone_numbers(page, dpi=200):
    xfl, xfh = 0.0, 0.12
    ink, (Wp, Hp), scale = B.visual_ink_mask(page, dpi=dpi, x_frac_lo=xfl,
                                             x_frac_hi=xfh, min_sat=0, dark_lum=150)
    if not ink:
        return []
    H = float(page.get_height()); W = float(page.get_width())
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
        if not (15.0 <= h <= 22.0 and 6.0 <= w <= 26.0):
            continue
        x0=min(xs)/scale; x1=max(xs)/scale; yc=(min(ys)+max(ys))/2.0/scale
        if not (95.0 <= x0 <= 175.0):
            continue
        if not (0.05*H <= yc <= 0.96*H):
            continue
        # require whitespace immediately to the RIGHT (line-start, not inline)
        gap_lo = x1 + 2.0
        gap_hi = x1 + 34.0
        yb0 = int(round((yc - 0.5*h)*scale)); yb1 = int(round((yc + 0.5*h)*scale))
        xa = int(round(gap_lo*scale)); xb = int(round(gap_hi*scale))
        has_right = any((py, px) in ink for py in range(yb0, yb1+1) for px in range(xa, xb+1))
        if has_right:
            continue
        cands.append((round(yc,1), round(x0,1), round(w,1)))
    return sorted(cands)

EXPECT = {480: 6, 482: 8, 486: 14, 492: 15}
for bp in [480, 482, 486, 492]:
    page = doc[bp-1]
    c = standalone_numbers(page)
    exp = EXPECT.get(bp)
    print(f"bp={bp}: standalone_numbers={len(c)}  expect~{exp}")
    for (y, x0, w) in c:
        print(f"      y={y:7.1f} x0={x0:6.1f} w={w:5.1f}")
doc.close()
