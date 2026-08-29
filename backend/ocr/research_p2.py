#!/usr/bin/env python3
"""
SESSION 2 — RESEARCH ONLY (no extraction, no manifest, no DB writes).
Probes the structure of the 13 in-scope Math AA HL Paper 2 past papers:
  - question-paper (QP) text-layer viability + question count via qhead_re
  - mark-scheme (MS) segmentation via the 3-alt numre (P1 detector)
  - MS segmentation via the 4-alt numre (adds the P2-specific "N (a)" no-dot header)
  - PUA glyph density, page counts, MS raster-page count
Prints a table + dumps MS header lines for any paper that does NOT fully resolve.
"""
import pypdfium2 as pdfium, os, re

BASE = "/Users/lucas.ma/Downloads/dp learning/IB 数学 AA  HL 历年真题"

PAPERS = [
 ("2024.5HL/Mathematics_analysis_and_approaches_paper_2__TZ1_HL.pdf", "2024_5_TZ1"),
 ("2024.5HL/Mathematics_analysis_and_approaches_paper_2__TZ2_HL.pdf", "2024_5_TZ2"),
 ("2024.11HL/Mathematics_analysis_and_approaches_paper_2__HL.pdf",    "2024_11"),
 ("IB 数学 HL 真题（2006-23）/2021 May/IB 数学 AA  HL  2021.05/Mathematics_analysis_and_approaches_paper_2__TZ1_HL.pdf", "2021May_TZ1"),
 ("IB 数学 HL 真题（2006-23）/2021 May/IB 数学 AA  HL  2021.05/Mathematics_analysis_and_approaches_paper_2__TZ2_HL.pdf", "2021May_TZ2"),
 ("IB 数学 HL 真题（2006-23）/2021 Nov/Mathematics_analysis_and_approaches_paper_2__HL.pdf", "2021Nov"),
 ("IB 数学 HL 真题（2006-23）/2022 May/Mathematics_analysis_and_approaches_paper_2__TZ1_HL.pdf", "2022May_TZ1"),
 ("IB 数学 HL 真题（2006-23）/2022 May/Mathematics_analysis_and_approaches_paper_2__TZ2_HL.pdf", "2022May_TZ2"),
 ("IB 数学 HL 真题（2006-23）/2022 Nov/Mathematics_analysis_and_approaches_paper_2__HL.pdf", "2022Nov"),
 ("IB 数学 HL 真题（2006-23）/2023 May/Mathematics_analysis_and_approaches_paper_2__TZ1_HL.pdf", "2023May_TZ1"),
 ("IB 数学 HL 真题（2006-23）/2023 May/Mathematics_analysis_and_approaches_paper_2__TZ2_HL.pdf", "2023May_TZ2"),
 ("IB 数学 HL 真题（2006-23）/2023 Nov/Mathematics_analysis_and_approaches_paper_2__TZ1_HL.pdf", "2023Nov_TZ1"),
 ("IB 数学 HL 真题（2006-23）/2023 Nov/Mathematics_analysis_and_approaches_paper_2__TZ2_HL.pdf", "2023Nov_TZ2"),
]

qhead_re = re.compile(r'(?m)^\s*(\d+)\.\s*\[Maximum mark: (\d+)\]')
# 3-alt detector (P1)
numre3 = re.compile(r'(?m)^\s*(?:Question\s+(\d+)|(\d+)\.(?!\d)\s|(\d+)\s+METHOD\b)')
# 4-alt detector (P1 + P2 "N (a)" no-dot)
numre4 = re.compile(r'(?m)^\s*(?:Question\s+(\d+)|(\d+)\.(?!\d)\s|(\d+)\s+METHOD\b|(\d+)\s+\([a-z]\))')

PUA = re.compile(r'[\ue000-\uf8ff]')

def load(path):
    d = pdfium.PdfDocument(path)
    pages = [d[i].get_textpage().get_text_range() for i in range(len(d))]
    full = "\n".join(pages)
    d.close()
    return pages, full

def count_pua(text):
    return len(PUA.findall(text))

def raster_pages(pages):
    # pages whose text is mostly empty (<=40 chars) -> raster/scanned figure page
    return sum(1 for p in pages if len(p.strip()) <= 40)

def walk(numre, mfull, anc, N):
    start = anc + len("Presentation of candidate work") if anc > 0 else 0
    expected = 1; got = {}
    for m in numre.finditer(mfull, start):
        num = int(m.group(1) or m.group(2) or m.group(3) or m.group(4))
        if 1 <= num <= N and num == expected:
            got[num] = m.start(); expected += 1
            if expected > N: break
    return got

def main():
    print(f"{'slug':12} {'QPpg':>4} {'N':>3} {'QPpu':>5} | {'MSpg':>4} {'3alt':>5} {'4alt':>5} {'MSpu':>6} {'MSraster':>8}")
    print("-"*70)
    problems = []
    for qp_rel, slug in PAPERS:
        qpages, qfull = load(os.path.join(BASE, qp_rel))
        try:
            mpages, mfull = load(os.path.join(BASE, qp_rel[:-4] + "_markscheme.pdf"))
        except Exception as e:
            print(f"{slug:12} QP ok | MS MISSING: {e}")
            problems.append(slug); continue
        N = len(list(qhead_re.finditer(qfull)))
        anc = mfull.rfind("Presentation of candidate work")
        g3 = walk(numre3, mfull, anc, N)
        g4 = walk(numre4, mfull, anc, N)
        qpu = count_pua(qfull); mpu = count_pua(mfull); mr = raster_pages(mpages)
        flag3 = "" if len(g3)==N else "  <-- 3alt short"
        print(f"{slug:12} {len(qpages):>4} {N:>3} {qpu:>5} | {len(mpages):>4} {len(g3):>5} {len(g4):>5} {mpu:>6} {mr:>8}{flag3}")
        if len(g4) != N:
            problems.append(slug)
            # dump MS headers to diagnose
            print(f"    >>> 4alt still short ({len(g4)}/{N}). MS header sample:")
            lines = [ln for ln in mfull[anc:].splitlines() if re.match(r'^\s*(\d+)\b', ln.strip())][:25]
            for ln in lines[:18]:
                print(f"        | {ln.strip()[:90]}")
    print("-"*70)
    if problems:
        print("PAPERS NEEDING ATTENTION:", problems)
    else:
        print("ALL 13 P2 PAPERS RESOLVE 12/12 (or N/N) WITH 4-ALT DETECTOR.")

if __name__ == "__main__":
    main()
