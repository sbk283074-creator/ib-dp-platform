#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render diagnostic pages to PNG for visual inspection."""
import os, sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pypdfium2 as pdfium

DP = "/Users/lucas.ma/Downloads/dp learning"
OUT = "/tmp/diag_pages"
os.makedirs(OUT, exist_ok=True)
JOBS = [
    ('oxford_p153', f'{DP}/HL OXFPRD 教材/Mathematics HL - Analysis and Approaches - OXFORD 2019.pdf', 152),
    ('oxford_p6',   f'{DP}/HL OXFPRD 教材/Mathematics HL - Analysis and Approaches - OXFORD 2019.pdf', 5),
    ('haese_aa2_p66', f'{DP}/HAESE AND HARRIS 最新教材/Mathematics - Analysis and Approaches HL 2 - Haese 2019.pdf', 65),
    ('haese_aa2_p40', f'{DP}/HAESE AND HARRIS 最新教材/Mathematics - Analysis and Approaches HL 2 - Haese 2019.pdf', 39),
    ('haese_core1_p32', f'{DP}/HAESE AND HARRIS 最新教材/Mathematics - Core Topics HL 1 - Haese 2019.pdf', 31),
    ('hodder_p22',  f'{DP}/Mathematics - Analysis and Approaches HL - Hodder 2019.pdf', 21),
]
for name, path, pno in JOBS:
    pdf = pdfium.PdfDocument(path)
    page = pdf[pno]
    print(name, 'size=', page.get_size(), 'rot=', page.get_rotation())
    bmp = page.render(scale=0.9)
    img = bmp.to_pil()
    img.save(f'{OUT}/{name}.png')
    pdf.close()
    print(' saved', f'{OUT}/{name}.png', img.size)
