"""diag_haese_blue3.py — validate the threshold rule.

A coloured candidate (blue, digit-sized, left-edge, near a text-number-cluster
x0) is a GENUINE missing question-number (=> a merge to split) ONLY IF it lies
inside a text-layer band AND the nearest black number is > 200pt away (the band
is tall = contains a missing coloured question). Candidates within ~100pt of a
black number are body digits inside normal-length questions -> ignore.
"""
import re
import booklib as B
import extract_books as E
import pypdfium2 as pdfium

BOOK_ID = 'MA-HAESE-CORE1'
book = next(b for b in E.BOOKS if b['id'] == BOOK_ID)
cfg = book.get('seg', {})
doc = pdfium.PdfDocument(book['path'])
dpi = 200
GAP = 200.0

def number_x0_clusters(page):
    H = float(page.get_height())
    xs = []
    for top, t, x0 in B.pdfium_lines(page):
        if re.match(r'^\s*\d{1,2}\s+[A-Za-z]', t) and 0.05*H <= top <= 0.95*H:
            xs.append(x0)
    xs.sort()
    cl = []
    for x in xs:
        if cl and x - cl[-1][-1] <= 40:
            cl[-1].append(x)
        else:
            cl.append([x])
    return [sum(c)/len(c) for c in cl]

def candidates(page, clusters):
    H = float(page.get_height())
    ink, (Wp, Hp), scale = B.visual_ink_mask(page, dpi=dpi, x_frac_lo=0.0,
                                             x_frac_hi=1.0, min_sat=80, dark_lum=150)
    if not ink or not clusters:
        return []
    img = page.render(scale=dpi/72.0).to_pil().convert('HSV')
    px = img.load()
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
        if not (14.0 <= h <= 23.0 and 5.0 <= w <= 28.0): continue
        x0=min(xs)/scale
        if not any(abs(x0-c)<=25 for c in clusters): continue
        col_left = min(clusters, key=lambda c: abs(c-x0)) - 25
        yb0=int(round(min(ys))); yb1=int(round(max(ys)))
        xa=int(round(col_left*scale)); xb=int(round((x0-1.0)*scale))
        if xb>xa and any((py,px2) in ink for py in range(yb0,yb1+1) for px2 in range(xa,xb+1)):
            continue
        hs=[px[px2,py][0] for py in range(min(ys),max(ys)+1) for px2 in range(min(xs),max(xs)+1) if (py,px2) in ink]
        if not (140 <= (sum(hs)/len(hs) if hs else -1) <= 195): continue
        out.append((round((min(ys)+max(ys))/2/scale,1), round(x0,1)))
    return sorted(out)

def black_ys(page):
    H=float(page.get_height())
    out=[]
    for top,t,x0 in B.pdfium_lines(page):
        if re.match(r'^\s*\d{1,2}\s+[A-Za-z]', t) and 0.05*H<=top<=0.95*H:
            out.append(top)
    return out

for bp in [480, 482, 486, 492]:
    page = doc[bp-1]
    cl = number_x0_clusters(page)
    cands = candidates(page, cl)
    bbands = B.question_bands_pdfium(page, cfg=cfg)
    by = black_ys(page)
    splits=[]
    for (cy, cx) in cands:
        inside = [ (y0,y1) for (t,y0,y1) in bbands if y0-2 <= cy <= y1+2 ]
        if not inside: continue
        dmin = min(abs(cy-b) for b in by) if by else 999
        if dmin > GAP:
            splits.append((cy, round(dmin)))
    print(f"bp={bp}: bands={len(bbands)} black={len(by)} cands={len(cands)} SPLITS={len(splits)} -> {splits}")
doc.close()
