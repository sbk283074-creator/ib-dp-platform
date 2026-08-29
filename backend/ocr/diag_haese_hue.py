"""diag_haese_hue.py — sample the HUE of coloured left-edge digit components
to see if question numbers form a distinct colour cluster (e.g. cyan) from body
math. If so, we can isolate question numbers by hue + size + left-edge.

Render the page, convert to HSV, and for each coloured (min_sat=80) digit-sized
(h[14,23] w[5,28]) left-edge component, average its H channel.
"""
import booklib as B
import extract_books as E
import pypdfium2 as pdfium

BOOK_ID = 'MA-HAESE-CORE1'
book = next(b for b in E.BOOKS if b['id'] == BOOK_ID)
doc = pdfium.PdfDocument(book['path'])
dpi = 200

def components_hue(page):
    W = float(page.get_width()); H = float(page.get_height())
    ink, (Wp, Hp), scale = B.visual_ink_mask(page, dpi=dpi, x_frac_lo=0.0,
                                             x_frac_hi=1.0, min_sat=80, dark_lum=150)
    if not ink:
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
        yb0=int(round(min(ys))); yb1=int(round(max(ys)))
        xa=0; xb=int(round((x0-1.0)*scale))
        left_empty = (xb<=xa) or not any((py,px2) in ink for py in range(yb0,yb1+1) for px2 in range(xa,xb+1))
        if not left_empty:
            continue
        hs=[]
        for py in range(min(ys),max(ys)+1):
            for px2 in range(min(xs),max(xs)+1):
                if (py,px2) in ink:
                    hs.append(px[px2,py][0])
        avg = sum(hs)/len(hs) if hs else -1
        out.append((round((min(ys)+max(ys))/2/scale,1), round(x0,1), round(h,1), round(avg,1)))
    return out

for bp in [482, 480]:
    page = doc[bp-1]
    print(f"\n=== bp={bp} ===")
    res = components_hue(page)
    for (y,x0,h,avgh) in res:
        print(f"   y={y:7.1f} x0={x0:6.1f} h={h:5.1f} hueH={avgh:6.1f}")
doc.close()
