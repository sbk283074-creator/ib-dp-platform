#!/usr/bin/env python3
"""Full feasibility scan across ALL physics topic PDFs. READ-ONLY.
For each (folder, paper): question + markscheme page counts, text char counts
(born-digital check), and cover-page check on page 1."""
import os, re
import pypdfium2 as pdfium

SRC = "/Users/lucas.ma/Downloads/dp learning/Physics-HL-Topic questions"
TITLE_LEAD = re.compile(r"^\s*hl\.?\s*p\w*r\s*\d+\s*p?\s*[\r\n]*", re.I)
def strip_title(t): return TITLE_LEAD.sub("", t or "").strip() if t else t
def is_cover(t):
    raw = (t or "").strip()
    if not raw or not re.search(r"\d", raw): return False
    return len(re.sub(r"[^a-z0-9]", "", strip_title(raw).lower())) < 3

def p1_text(path):
    d = pdfium.PdfDocument(path)
    return d[0].get_textpage().get_text_range()

def stats(path):
    d = pdfium.PdfDocument(path)
    n = len(d)
    chars = sum(len(d[i].get_textpage().get_text_range()) for i in range(n))
    return n, chars

print(f"{'folder':10s} {'paper':12s} {'qpg':>4s} {'qch':>7s} {'mspg':>5s} {'msch':>8s} {'cover?':>7s}")
total_qpg = total_mspg = 0
problems = []
for fol in sorted(os.listdir(SRC)):
    fdir = os.path.join(SRC, fol)
    if not os.path.isdir(fdir): continue
    files = os.listdir(fdir)
    qmap, mmap = {}, {}
    for f in files:
        if not f.lower().endswith(".pdf"): continue
        low = f.lower(); base = f[:-4]
        if "markscheme" in low:
            mmap[re.sub(r"^markscheme-", "", base, flags=re.I)] = f
        else:
            qmap[base] = f
    for paper in sorted(set(qmap) | set(mmap)):
        qf = qmap.get(paper); msf = mmap.get(paper)
        qpg = qch = mspg = msch = 0
        cover = "-"
        if qf:
            qpg, qch = stats(os.path.join(fdir, qf))
            cover = "YES" if is_cover(p1_text(os.path.join(fdir, qf))) else "no"
            if qch < qpg * 30:  # suspiciously little text => possibly scanned
                problems.append(f"{fol}/{paper}: q text only {qch} chars over {qpg}pg (maybe scanned?)")
        if msf:
            mspg, msch = stats(os.path.join(fdir, msf))
            if msch < mspg * 30:
                problems.append(f"{fol}/{paper}: ms text only {msch} chars over {mspg}pg (maybe scanned?)")
        total_qpg += qpg; total_mspg += mspg
        print(f"{fol:10s} {paper:12s} {qpg:4d} {qch:7d} {mspg:5d} {msch:8d} {cover:>7s}")

print(f"\nTOTAL question pages={total_qpg}  markscheme pages={total_mspg}")
print("PROBLEMS / flags:" if problems else "No scanned-PDF flags.")
for p in problems: print("  -", p)
