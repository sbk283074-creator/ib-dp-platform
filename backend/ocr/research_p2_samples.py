#!/usr/bin/env python3
"""Supplementary dump: show real QP + MS header lines for representative P2 papers."""
import pypdfium2 as pdfium, os, re

BASE = "/Users/lucas.ma/Downloads/dp learning/IB 数学 AA  HL 历年真题"

qhead_re = re.compile(r'(?m)^\s*(\d+)\.\s*\[Maximum mark: (\d+)\]')
numre4 = re.compile(r'(?m)^\s*(?:Question\s+(\d+)|(\d+)\.(?!\d)\s|(\d+)\s+METHOD\b|(\d+)\s+\([a-z]\))')

def load(path):
    d = pdfium.PdfDocument(path)
    pages = [d[i].get_textpage().get_text_range() for i in range(len(d))]
    d.close()
    return "\n".join(pages)

samples = [
 ("2024.5HL/Mathematics_analysis_and_approaches_paper_2__TZ1_HL.pdf", "2024_5_TZ1"),
 ("2021May_TZ1 (the 4th-format paper)", "2021May_TZ1"),
 ("2021Nov (N=11)", "2021Nov"),
]
for note, slug in samples:
    if slug == "2021May_TZ1":
        qp = "IB 数学 HL 真题（2006-23）/2021 May/IB 数学 AA  HL  2021.05/Mathematics_analysis_and_approaches_paper_2__TZ1_HL.pdf"
    elif slug == "2021Nov":
        qp = "IB 数学 HL 真题（2006-23）/2021 Nov/Mathematics_analysis_and_approaches_paper_2__HL.pdf"
    else:
        qp = f"2024.5HL/Mathematics_analysis_and_approaches_paper_2__TZ1_HL.pdf"
    qfull = load(os.path.join(BASE, qp))
    mfull = load(os.path.join(BASE, qp[:-4] + "_markscheme.pdf"))
    print(f"\n===== {note}  (QP={os.path.basename(qp)}) =====")
    print("-- QP question headers (qhead_re) --")
    for m in list(qhead_re.finditer(qfull))[:3]:
        ln = qfull[m.start():m.start()+70].splitlines()[0]
        print(f"   {ln.strip()[:80]}")
    print(f"   ... total N={len(list(qhead_re.finditer(qfull)))}")
    anc = mfull.rfind("Presentation of candidate work")
    seg = mfull[anc:] if anc>0 else mfull
    print("-- MS question headers (numre4, first 12 detected) --")
    cnt=0
    for m in numre4.finditer(seg):
        num = int(m.group(1) or m.group(2) or m.group(3) or m.group(4))
        ln = seg[m.start():m.start()+70].splitlines()[0]
        print(f"   Q{num}: {ln.strip()[:80]}")
        cnt+=1
        if cnt>=12: break
