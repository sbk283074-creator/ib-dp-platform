"""diag_haese_merge_scan.py — full-book scan of MA-HAESE-CORE1 to enumerate
every page where a coloured question number was missed by the text-layer
detector (=> bands merged) and validate the refined visual detector.

Refined visual qnum = connected component in left margin (x_frac_hi=0.14),
saturated (min_sat=80), with glyph HEIGHT in [15,22] and WIDTH in [6,26]
(the real question-number digit size; excludes small coloured math symbols
and thin vertical bars). Header/footer zones (y in [0.05,0.96]) excluded.

Per text-layer band tok=N, coloured qnums strictly inside (y > band_top+6)
are the NEXT sequential questions; total questions = bands + inside-count.
Pages with inside-count > 0 are the merged pages we must split.
"""
import os, sys, collections
import booklib as B
import extract_books as E
import pypdfium2 as pdfium

BOOK_ID = 'MA-HAESE-CORE1'
book = next(b for b in E.BOOKS if b['id'] == BOOK_ID)
cfg = book.get('seg', {})
doc = pdfium.PdfDocument(book['path'])
N = len(doc)

def qnum_comps(page):
    """Return sorted list of (y) for question-number-sized coloured components."""
    ink, (Wp, Hp), scale = B.visual_ink_mask(page, dpi=200, x_frac_lo=0.0,
                                             x_frac_hi=0.14, min_sat=80, dark_lum=150)
    if not ink:
        return []
    H = float(page.get_height())
    from collections import deque
    seen = set(); out = []
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
        h = (max(ys)-min(ys)+1)/scale; w = (max(xs)-min(xs)+1)/scale
        if 15.0 <= h <= 22.0 and 6.0 <= w <= 26.0:
            yc = (min(ys)+max(ys))/2.0/scale
            if 0.05*H <= yc <= 0.96*H:
                out.append(yc)
    return sorted(out)

merged = []
for i in range(N):
    bp = i + 1
    page = doc[i]
    try:
        bands = B.question_bands_pdfium(page, cfg=cfg)
    except Exception:
        bands = []
    vis = qnum_comps(page)
    inside_total = 0
    per_band = []
    for (t, y0, y1) in bands:
        ins = [y for y in vis if y0 + 6 <= y <= y1]
        per_band.append((t, len(ins)))
        inside_total += len(ins)
    if inside_total > 0:
        merged.append((bp, len(bands), inside_total, per_band, len(vis)))

doc.close()
print(f"TOTAL pages={N}  MERGED pages={len(merged)}")
for bp, nb, inside, pb, nv in merged:
    print(f"  bp={bp}: text_bands={nb} extra_coloured={inside} page_vis={nv}  band_detail={pb}")
