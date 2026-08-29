#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnose Haese section headers vs worked-solutions headers."""
import re
import pypdfium2 as pdfium
from booklib import pdfium_lines

CORE = '/Users/lucas.ma/Downloads/dp learning/HAESE AND HARRIS 最新教材/Mathematics - Core Topics HL 1 - Haese 2019.pdf'
SOL = '/Users/lucas.ma/Downloads/dp learning/HAESE AND HARRIS 最新教材/Mathematics - Core Topics HL 1 - WORKED SOLUTIONS - Haese 2019.pdf'

pat = re.compile(
    r'mixed\s+practice|mixed\s+review|review\s+set|chapter\s+review|'
    r'self[\s-]?test|test\s+yourself|practice\s+questions?|mixed\s+questions?|'
    r'revision\s+(exercise|set|questions?)|end[\s-]?of[\s-]?chapter\s+(questions?|exercises?)',
    re.I)

print('===== TEXTBOOK review pages =====')
pdf = pdfium.PdfDocument(CORE)
cnt = 0
for i in range(len(pdf)):
    lines = [t for _, t, _ in pdfium_lines(pdf[i])]
    txt = '\n'.join(lines)
    m = pat.search(txt)
    if m:
        cnt += 1
        if cnt <= 8 or cnt % 20 == 0:
            print(f'p{i+1}: hdr={m.group(0)!r} first3={[l[:45] for l in lines[:3]]}')
print('total:', cnt)
pdf.close()

print()
print('===== SOLUTIONS header format =====')
pdf = pdfium.PdfDocument(SOL)
hdr_re = re.compile(r'Chapter\s+\d+\s*\(([^)]*)\)\s*(.{0,40})')
seen = 0
for i in range(len(pdf)):
    lines = [t for _, t, _ in pdfium_lines(pdf[i])]
    if not lines:
        continue
    joined = ' '.join(lines[:3])
    m = hdr_re.search(joined)
    if m:
        seen += 1
        if seen <= 8 or seen % 60 == 0:
            print(f'p{i+1}: {m.group(0)[:70]!r}')
print('pages with Chapter(...) header:', seen, 'of', len(pdf))
pdf.close()
