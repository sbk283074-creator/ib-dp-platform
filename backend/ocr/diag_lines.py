#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dump line x0 layout + object types for candidate pages."""
import os, sys, warnings, collections
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pypdfium2 as pdfium
import booklib as B

DP = "/Users/lucas.ma/Downloads/dp learning"
PAGES = [
    ('MA-OXFORD-2019', f'{DP}/HL OXFPRD 教材/Mathematics HL - Analysis and Approaches - OXFORD 2019.pdf', [5, 152]),
    ('MA-HAESE-AA2', f'{DP}/HAESE AND HARRIS 最新教材/Mathematics - Analysis and Approaches HL 2 - Haese 2019.pdf', [39, 65]),
    ('MA-HODDER-2019', f'{DP}/Mathematics - Analysis and Approaches HL - Hodder 2019.pdf', [21, 22]),
]
for bid, path, pnos in PAGES:
    pdf = pdfium.PdfDocument(path)
    for pno in pnos:
        page = pdf[pno]
        W = float(page.get_width())
        print(f"\n===== {bid} p{pno+1} (W={W:.0f}) =====")
        lines = B.pdfium_lines(page)
        for top, t, x0 in lines[:45]:
            bar = int(x0 / W * 60)
            print(f"  y={top:6.1f} x0={x0:6.1f} {' '*bar}| {t[:70]}")
        # object type census
        types = collections.Counter()
        try:
            for obj in page.get_objects(max_depth=8):
                types[obj.type] += 1
        except Exception as e:
            print('  obj err', e)
        print('  object types:', dict(types))
    pdf.close()
