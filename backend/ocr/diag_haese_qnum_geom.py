"""diag_haese_qnum_geom.py — characterise the real question-number glyph
geometry so split_bands_visual can isolate COLOURED question digits from the
many small coloured math symbols/sub-part letters.

Prints (y, h, w, aspect=w/h) for every connected component in the left margin
(x_frac_hi=0.14) with min_sat=80, for a few selected pages. We compare a
CORRECTLY-separated page (bp=480: single-question bands, black numbers) against
a MERGED page (bp=486: one band tok=5 spanning many coloured questions).
"""
import os, sys, collections
import booklib as B
import extract_books as E
import pypdfium2 as pdfium

BOOK_ID = 'MA-HAESE-CORE1'
book = next(b for b in E.BOOKS if b['id'] == BOOK_ID)
doc = pdfium.PdfDocument(book['path'])

def components_geom(page, dpi=200, x_frac_lo=0.0, x_frac_hi=0.14,
                    min_h=4, max_h=60, min_w=2, max_w=120,
                    min_sat=80, dark_lum=150):
    ink, (Wp, Hp), scale = B.visual_ink_mask(page, dpi=dpi, x_frac_lo=x_frac_lo,
                                             x_frac_hi=x_frac_hi, min_sat=min_sat,
                                             dark_lum=dark_lum)
    if not ink:
        return []
    H = float(page.get_height())
    # rebuild components with geometry
    from collections import deque
    seen = set(); comps = []
    for seed in ink:
        if seed in seen:
            continue
        stack = deque([seed]); seen.add(seed); ys = []; xs = []
        while stack:
            y, x = stack.popleft()
            ys.append(y); xs.append(x)
            for dy, dx in ((-1,0),(1,0),(0,-1),(0,1)):
                nb = (y+dy, x+dx)
                if nb in ink and nb not in seen:
                    seen.add(nb); stack.append(nb)
        h = max(ys)-min(ys)+1; w = max(xs)-min(xs)+1
        if min_h <= h <= max_h and min_w <= w <= max_w:
            comps.append((min(ys)/scale, h/scale, w/scale))
    return sorted(comps)

PAGES = [480, 486, 488, 492]
for bp in PAGES:
    page = doc[bp-1]
    W = float(page.get_width()); H = float(page.get_height())
    comps = components_geom(page)
    # only components in the upper body region (skip headers/footers)
    body = [c for c in comps if 0.05*H <= c[0] <= 0.95*H]
    print(f"\n=== bp={bp}  W={W:.0f} H={H:.0f}  total_comps={len(comps)} body={len(body)} ===")
    # bucket by height to see the dominant question-number size
    hb = collections.Counter(round(c[1]) for c in body)
    print("  height histogram:", dict(sorted(hb.items())))
    wb = collections.Counter(round(c[2]) for c in body)
    print("  width histogram :", dict(sorted(wb.items())))
    # show the LARGEST components (likely real question digits)
    big = sorted(body, key=lambda c: -c[1])[:30]
    print("  top-30 by height (y, h, w, aspect=w/h):")
    for (y, h, w) in big:
        print(f"      y={y:7.1f} h={h:5.1f} w={w:5.1f} asp={w/h:4.2f}")
doc.close()
