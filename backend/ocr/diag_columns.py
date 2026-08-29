#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnose column layout + image objects on exercise pages of math books."""
import os, re, sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pypdfium2 as pdfium
import booklib as B

DP = "/Users/lucas.ma/Downloads/dp learning"
BOOKS = {
    'MA-HODDER-2019': f'{DP}/Mathematics - Analysis and Approaches HL - Hodder 2019.pdf',
    'MA-OXFORD-2019': f'{DP}/HL OXFPRD 教材/Mathematics HL - Analysis and Approaches - OXFORD 2019.pdf',
    'MA-HAESE-AA2': f'{DP}/HAESE AND HARRIS 最新教材/Mathematics - Analysis and Approaches HL 2 - Haese 2019.pdf',
    'MA-HAESE-CORE1': f'{DP}/HAESE AND HARRIS 最新教材/Mathematics - Core Topics HL 1 - Haese 2019.pdf',
}

MATH_CHAPTER_END = [
    r'mixed\s+practice', r'mixed\s+review', r'review\s+set', r'chapter\s+review',
    r'self[\s-]?test', r'test\s+yourself', r'practice\s+questions?',
    r'mixed\s+questions?', r'revision\s+(exercise|set|questions?)',
    r'end[\s-]?of[\s-]?chapter\s+(questions?|exercises?)',
]

def col_stats(page):
    """Line x-extents: how many lines start near left margin vs a middle gutter."""
    lines = B.pdfium_lines(page)
    if not lines:
        return None
    W = float(page.get_width()); H = float(page.get_height())
    # collect char x positions from a raw pass
    tp = page.get_textpage()
    n = tp.count_chars()
    xs = []
    for i in range(n):
        try:
            b = tp.get_charbox(i)
            xs.append((float(b[0]), float(b[2])))
        except Exception:
            pass
    tp.close()
    if not xs:
        return None
    # histogram of char centers into 20 bins
    import collections
    bins = collections.Counter()
    for x0, x1 in xs:
        c = (x0 + x1) / 2
        bins[min(19, int(c / W * 20))] += 1
    # a column gutter shows as a persistent low-density bin near middle
    mid = [bins[b] for b in range(7, 13)]
    edges = [bins[b] for b in list(range(0, 7)) + list(range(13, 20))]
    avg_mid = sum(mid) / len(mid) if mid else 0
    avg_edge = sum(edges) / len(edges) if edges else 1
    # lines starting in right half
    right_lines = sum(1 for top, t, x0 in lines if x0 > W * 0.5)
    return dict(nlines=len(lines), right_start=right_lines,
                mid_density=avg_mid / max(1, avg_edge), bins=dict(bins))

def image_objects(page):
    """Enumerate image objects with bboxes (PDF points, bottom-up y)."""
    H = float(page.get_height())
    imgs = []
    try:
        for obj in page.get_objects(max_depth=4):
            try:
                if obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                    l, b, r, t = obj.get_pos()
                    imgs.append((float(l), H - float(t), float(r), H - float(b)))  # screen coords
            except Exception:
                pass
    except Exception:
        pass
    return imgs

for bid, path in BOOKS.items():
    print(f"\n===== {bid} =====")
    if not os.path.exists(path):
        print("  MISSING FILE"); continue
    pdf = pdfium.PdfDocument(path)
    n = len(pdf)
    checked = 0
    for i in range(n):
        if checked >= 6:
            break
        page = pdf[i]
        try:
            ok, hdr = B.is_exercise_page_pdfium(page, patterns=MATH_CHAPTER_END)
        except Exception:
            ok = False
        if not ok:
            continue
        checked += 1
        st = col_stats(page)
        imgs = image_objects(page)
        if st:
            print(f"  p{i+1}: lines={st['nlines']} right-start={st['right_start']} "
                  f"mid/edge density={st['mid_density']:.3f} images={len(imgs)}")
            if imgs:
                for im in imgs[:4]:
                    print(f"     img bbox(x0={im[0]:.0f},y0={im[1]:.0f},x1={im[2]:.0f},y1={im[3]:.0f})")
    pdf.close()
