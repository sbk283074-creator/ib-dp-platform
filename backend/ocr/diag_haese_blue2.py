"""diag_haese_blue2.py — validate the FINAL coloured-question-number detector.

Per page:
  1. cluster text-layer number-line x0s (question indents; gap>40 => new column)
  2. scan coloured (min_sat=80), BLUE (hue in [140,195]), digit-sized
     (h[14,23] w[5,28]) LEFT-EDGE components whose x0 is within +-25 of a
     cluster centre. These are the coloured question numbers.
  3. report clusters, candidate y's, and how many fall inside each text band.

Ground truth:
  bp=480 all black -> ~0 coloured in question column
  bp=482 -> 1 coloured (15) in left column (x0~242)
  bp=486 -> a few coloured in left(x0~119)/right(x0~202) columns
  bp=492 -> several coloured
"""
import re
import booklib as B
import extract_books as E
import pypdfium2 as pdfium

BOOK_ID = 'MA-HAESE-CORE1'
book = next(b for b in E.BOOKS if b['id'] == BOOK_ID)
doc = pdfium.PdfDocument(book['path'])
dpi = 200

def number_x0_clusters(page):
    H = float(page.get_height())
    xs = []
    for top, t, x0 in B.pdfium_lines(page):
        if re.match(r'^\s*\d{1,2}\b', t) and 0.05*H <= top <= 0.95*H:
            xs.append(x0)
    xs.sort()
    clusters = []
    for x in xs:
        if clusters and x - clusters[-1][-1] <= 40:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return [sum(c)/len(c) for c in clusters]

def coloured_qnums(page, clusters):
    H = float(page.get_height()); W = float(page.get_width())
    ink, (Wp, Hp), scale = B.visual_ink_mask(page, dpi=dpi, x_frac_lo=0.0,
                                             x_frac_hi=1.0, min_sat=80, dark_lum=150)
    if not ink or not clusters:
        return []
    img = page.render(scale=dpi/72.0).to_pil().convert('HSV')
    px = img.load()
    from collections import deque
    seen = set(); out = []
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
        x0=min(xs)/scale
        if not any(abs(x0 - c) <= 25 for c in clusters):
            continue
        # left-edge within its column (col_left = nearest cluster left edge)
        col_left = min(clusters, key=lambda c: abs(c - x0)) - 25
        yb0=int(round(min(ys))); yb1=int(round(max(ys)))
        xa=int(round(col_left*scale)); xb=int(round((x0-1.0)*scale))
        left_empty = (xb<=xa) or not any((py,px2) in ink for py in range(yb0,yb1+1) for px2 in range(xa,xb+1))
        if not left_empty:
            continue
        # hue check
        hs=[]
        for py in range(min(ys),max(ys)+1):
            for px2 in range(min(xs),max(xs)+1):
                if (py,px2) in ink:
                    hs.append(px[px2,py][0])
        avg = sum(hs)/len(hs) if hs else -1
        if not (140 <= avg <= 195):
            continue
        out.append((round((min(ys)+max(ys))/2/scale,1), round(x0,1)))
    return sorted(out)

for bp in [480, 482, 486, 492]:
    page = doc[bp-1]
    cl = number_x0_clusters(page)
    qn = coloured_qnums(page, cl)
    print(f"bp={bp}: clusters(x0)={cl}  coloured_qnums={len(qn)}")
    print(f"      y's = {[y for (y,_) in qn]}")
doc.close()
