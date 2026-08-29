#!/usr/bin/env python3
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import booklib as B, pypdfium2 as pdfium

DP = "/Users/lucas.ma/Downloads/dp learning"
JOBS = [
    ('oxford_p153', f'{DP}/HL OXFPRD 教材/Mathematics HL - Analysis and Approaches - OXFORD 2019.pdf', 152),
    ('haese_aa2_p66', f'{DP}/HAESE AND HARRIS 最新教材/Mathematics - Analysis and Approaches HL 2 - Haese 2019.pdf', 65),
    ('haese_aa2_p40', f'{DP}/HAESE AND HARRIS 最新教材/Mathematics - Analysis and Approaches HL 2 - Haese 2019.pdf', 39),
    ('hodder_p22',  f'{DP}/Mathematics - Analysis and Approaches HL - Hodder 2019.pdf', 21),
]
for name, path, pno in JOBS:
    pdf = pdfium.PdfDocument(path)
    p = pdf[pno]
    H = float(p.get_height()); W = float(p.get_width())
    # also show the white-fraction profile
    bmp = p.render(scale=50/72.0); img = bmp.to_pil().convert('L')
    w, h = img.size
    px = img.load()
    wf = [0]*w
    for x in range(w):
        wc = sum(1 for y in range(0, h, 2) if px[x,y]>=240)
        wf[x] = wc / ((h+1)//2)
    # find best gutter manually
    xs = int(0.25*w); xe = int(0.75*w)
    best = 0; best_cx = None
    rs = None
    for x in range(xs, xe+1):
        if wf[x] >= 0.96:
            if rs is None: rs = x
        else:
            if rs is not None:
                rw = x-rs
                if rw > best: best=rw; best_cx=(rs+x-1)/2
                rs=None
    if rs is not None:
        rw = xe+1-rs
        if rw>best: best=rw; best_cx=(rs+xe)/2
    # flanks
    if best_cx is not None:
        band = max(10, int(0.05*w))
        lx0=max(0,int(best_cx)-band); lx1=max(0,int(best_cx)-2)
        rx0=min(w,int(best_cx)+2);  rx1=min(w,int(best_cx)+band)
        def den(a,b):
            if b<=a: return 0
            return sum(1-wf[x] for x in range(a,b))/(b-a)
        dl=den(lx0,lx1); dr=den(rx0,rx1)
        gutter_pt = best_cx/w*W
        print(f"{name} W={W} w={w} best_blank_run={best}px ({best/w*100:.1f}%) best_cx_px={best_cx} gutter_pt={gutter_pt:.0f} dl={dl:.2f} dr={dr:.2f}")
    else:
        print(f"{name} no blank run found in middle")
    # also print gutter from booklib
    g = B.find_gutter_by_whitespace(p)
    print(f"  booklib.find_gutter = {g}")
    pdf.close()
