#!/usr/bin/env python3
"""
SESSION 3 — RESEARCH ONLY (no extraction, no manifest, no DB writes).
Math AA HL Paper 3 (past papers, 2021 May -> 2024.11). Probes structure exactly
like research_p2.py but for P3 (HL calculator paper — FEWER, LONGER questions).
Reports: QP/ MS pages, N (question count), MS anchor "Presentation of candidate work"
presence, resolution with the 4-alt numre, PUA density, MS raster pages.
Dumps MS header samples for a representative paper + the 2023 Nov single-HL paper.
"""
import pypdfium2 as pdfium, os, re

BASE = "/Users/lucas.ma/Downloads/dp learning/IB 数学 AA  HL 历年真题"

PAPERS = [
 ("2024.5HL/Mathematics_analysis_and_approaches_paper_3__TZ1_HL.pdf", "2024_5_TZ1"),
 ("2024.5HL/Mathematics_analysis_and_approaches_paper_3__TZ2_HL.pdf", "2024_5_TZ2"),
 ("2024.11HL/Mathematics_analysis_and_approaches_paper_3__HL.pdf",    "2024_11"),
 ("IB 数学 HL 真题（2006-23）/2021 May/IB 数学 AA  HL  2021.05/Mathematics_analysis_and_approaches_paper_3__TZ1_HL.pdf", "2021May_TZ1"),
 ("IB 数学 HL 真题（2006-23）/2021 May/IB 数学 AA  HL  2021.05/Mathematics_analysis_and_approaches_paper_3__TZ2_HL.pdf", "2021May_TZ2"),
 ("IB 数学 HL 真题（2006-23）/2021 Nov/Mathematics_analysis_and_approaches_paper_3__HL.pdf", "2021Nov"),
 ("IB 数学 HL 真题（2006-23）/2022 May/Mathematics_analysis_and_approaches_paper_3__TZ1_HL.pdf", "2022May_TZ1"),
 ("IB 数学 HL 真题（2006-23）/2022 May/Mathematics_analysis_and_approaches_paper_3__TZ2_HL.pdf", "2022May_TZ2"),
 ("IB 数学 HL 真题（2006-23）/2022 Nov/Mathematics_analysis_and_approaches_paper_3__HL.pdf", "2022Nov"),
 ("IB 数学 HL 真题（2006-23）/2023 May/Mathematics_analysis_and_approaches_paper_3__TZ1_HL.pdf", "2023May_TZ1"),
 ("IB 数学 HL 真题（2006-23）/2023 May/Mathematics_analysis_and_approaches_paper_3__TZ2_HL.pdf", "2023May_TZ2"),
 ("IB 数学 HL 真题（2006-23）/2023 Nov/Mathematics_analysis_and_approaches_paper_3__HL.pdf", "2023Nov"),
]

# P3 QP marks label varies: some papers "Maximum mark" (singular), some
# "Maximum marks" (plural, e.g. 2022May_TZ1). Accept both.
qhead_re = re.compile(r'(?m)^\s*(\d+)\.\s*\[Maximum marks?: (\d+)\]')
numre4 = re.compile(r'(?m)^\s*(?:Question\s+(\d+)|(\d+)\.(?!\d)\s|(\d+)\s+METHOD\b|(\d+)\s+\([a-z]\))')
PUA = re.compile(r'[\ue000-\uf8ff]')
ANCHOR = "Presentation of candidate work"

def load(path):
    d = pdfium.PdfDocument(path)
    pages = [d[i].get_textpage().get_text_range() for i in range(len(d))]
    full = "\n".join(pages)
    d.close()
    return pages, full

def walk(numre, mfull, anc, N):
    start = anc + len(ANCHOR) if anc > 0 else 0
    expected = 1; got = {}
    for m in numre.finditer(mfull, start):
        num = int(m.group(1) or m.group(2) or m.group(3) or m.group(4))
        if 1 <= num <= N and num == expected:
            got[num] = m.start(); expected += 1
            if expected > N: break
    return got

def main():
    print(f"{'slug':12} {'QPpg':>4} {'N':>3} {'QPpu':>5} | {'MSpg':>4} {'anc?':>4} {'res':>4} {'MSpu':>6} {'raster':>6}")
    print("-"*64)
    for qp_rel, slug in PAPERS:
        qpages, qfull = load(os.path.join(BASE, qp_rel))
        try:
            mpages, mfull = load(os.path.join(BASE, qp_rel[:-4] + "_markscheme.pdf"))
        except Exception as e:
            print(f"{slug:12} QP ok | MS MISSING: {e}"); continue
        N = len(list(qhead_re.finditer(qfull)))
        anc = mfull.rfind(ANCHOR)
        g = walk(numre4, mfull, anc, N)
        qpu = len(PUA.findall(qfull)); mpu = len(PUA.findall(mfull))
        raster = sum(1 for p in mpages if len(p.strip()) <= 40)
        print(f"{slug:12} {len(qpages):>4} {N:>3} {qpu:>5} | {len(mpages):>4} {('Y' if anc>0 else 'N'):>4} {len(g):>4} {mpu:>6} {raster:>6}")
    print("-"*64)

if __name__ == "__main__":
    main()
