#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify column detection + bands + image bboxes on key pages.

Mirrors the real extraction pipeline in extract_books.py:
  - two_col books get a narrow gutter_search override
  - column_lines (char-gap limited) with cross-column phantom dedup
  - question_bands_from_lines per column, then wrap-merge
Renders the resulting crop boxes to /tmp/diag_verify/ for eyeballing.
"""
import os, sys, warnings, json
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pypdfium2 as pdfium
import booklib as B

DP = "/Users/lucas.ma/Downloads/dp learning"
OUT = '/tmp/diag_verify'
os.makedirs(OUT, exist_ok=True)

# Oxford 2019 two-col: use a fixed gutter (calibrated from rendered page)
OXFORD_GUTTER = 440.0

PAGES = [
    # (name, pdf_path, page_index0, strict, gdict or None)
    ('oxford_p153', f'{DP}/HL OXFPRD 教材/Mathematics HL - Analysis and Approaches - OXFORD 2019.pdf', 152, True, dict(gutter_x=OXFORD_GUTTER)),
    ('oxford_p6',   f'{DP}/HL OXFPRD 教材/Mathematics HL - Analysis and Approaches - OXFORD 2019.pdf', 5, True, dict(gutter_x=OXFORD_GUTTER)),
    ('haese_aa2_p66', f'{DP}/HAESE AND HARRIS 最新教材/Mathematics - Analysis and Approaches HL 2 - Haese 2019.pdf', 65, True, None),
    ('haese_aa2_p40', f'{DP}/HAESE AND HARRIS 最新教材/Mathematics - Analysis and Approaches HL 2 - Haese 2019.pdf', 39, True, None),
    ('hodder_p22',  f'{DP}/Mathematics - Analysis and Approaches HL - Hodder 2019.pdf', 21, True, None),
]

for name, path, pno, strict, gdict in PAGES:
    pdf = pdfium.PdfDocument(path)
    page = pdf[pno]
    H = float(page.get_height()); W = float(page.get_width())
    if gdict:
        kind, gut = B.detect_columns(page, **gdict)
    else:
        kind, gut = B.detect_columns(page)
    gdicts = []
    if kind == 'two-col' and gut:
        left_lines = B.column_lines(page, 0.0, gut, dedup_against=None)
        right_lines = B.column_lines(page, gut, W,
                                     dedup_against=[(t, tx) for (t, tx, _) in left_lines])
        bl = B.question_bands_from_lines(left_lines, H, strict=strict)
        br = B.question_bands_from_lines(right_lines, H, strict=strict)
        merged = False
        if bl and br:
            ln = bl[-1][0].rstrip('.'); rn = br[0][0].rstrip('.')
            if ln and ln == rn and ln.isdigit():
                bl[-1] = (bl[-1][0], bl[-1][1], max(bl[-1][2], br[0][2]))
                br = br[1:]; merged = True
        for idx_l, (t, yo, y1) in enumerate(bl):
            is_wrap = merged and idx_l == len(bl) - 1
            gdicts.append(dict(tok=t, x0=0, x1=(W if is_wrap else gut), y0=yo, y1=y1))
        for (t, yo, y1) in br:
            gdicts.append(dict(tok=t, x0=gut, x1=W, y0=yo, y1=y1))
        print(f"{name} kind={kind} gutter={gut:.0f} | L={len(bl)} R={len(br)} wrap_merged={merged}")
        print(f"   L: {[(t, round(yo), round(y1)) for t,yo,y1 in bl[:10]]}")
        print(f"   R: {[(t, round(yo), round(y1)) for t,yo,y1 in br[:10]]}")
    else:
        lines = B.pdfium_lines(page)
        bands = B.question_bands_from_lines(lines, H, strict=strict)
        for (t, yo, y1) in bands:
            gdicts.append(dict(tok=t, x0=0, x1=W, y0=yo, y1=y1))
        print(f"{name} kind={kind} gutter={gut} | bands={len(bands)}")
        print(f"   bands: {[(t, round(yo), round(y1)) for t,yo,y1 in bands[:10]]}")
    # image attribution (same as extractor)
    imgs = B.page_image_bboxes(page)
    if imgs and gdicts:
        hs = sorted([g['y1'] - g['y0'] for g in gdicts])
        h_med = hs[len(hs) // 2] if hs else 80
        margin = 0.4 * h_med
        for g in gdicts:
            for (ix0, iy0, ix1, iy1) in imgs:
                icy = (iy0 + iy1) / 2
                if icy < g['y0'] - margin or icy > g['y1'] + margin:
                    continue
                x_ok = (ix0 >= g['x0'] - 10 and ix1 <= g['x1'] + 10)
                full_w = (ix0 < 5 and ix1 > W - 5)
                if not (x_ok or full_w):
                    continue
                g['y0'] = min(g['y0'], iy0 - 4); g['y1'] = max(g['y1'], iy1 + 4)
                g['x0'] = min(g['x0'], ix0 - 4); g['x1'] = max(g['x1'], ix1 - 4 if False else ix1 + 4)
    print(f"   images={len(imgs)}")
    # render crops for eyeballing
    if gdicts:
        tuples = [(g['x0'], g['x1'], g['y0'], g['y1']) for g in gdicts]
        paths = [os.path.join(OUT, f"{name}_{j:02d}_q{g['tok'].rstrip('.')}") + '.jpg'
                 for j, g in enumerate(gdicts)]
        try:
            B.render_page_crops_xy(page, tuples, paths, dpi=110)
            print(f"   rendered {len(paths)} crops -> {OUT}/{name}_*.jpg")
        except Exception as e:
            print(f"   render FAILED: {e}")
    pdf.close()
