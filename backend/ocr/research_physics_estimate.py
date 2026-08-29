#!/usr/bin/env python3
"""Estimate question-record counts via separator-band detection over ALL
question PDFs (read-only; rough volume estimate for the handoff)."""
import os, re
import pypdfium2 as pdfium
import numpy as np

SRC = "/Users/lucas.ma/Downloads/dp learning/Physics-HL-Topic questions"
SCALE = 1.5
SEP_STD_MAX = 10; SEP_BR_RANGE = (90, 250); INK_FRAC_MAX = 0.01

def detect_runs(img):
    arr = np.asarray(img)
    means = arr.mean(axis=1); stds = arr.std(axis=1); ink = (arr < 128).mean(axis=1)
    cand = (stds < SEP_STD_MAX) & (ink < INK_FRAC_MAX) & (means > SEP_BR_RANGE[0]) & (means < SEP_BR_RANGE[1])
    H = arr.shape[0]; runs = []; y = 0
    while y < H:
        if cand[y]:
            y0 = y
            while y < H and cand[y]: y += 1
            runs.append((y0, y - 1))
        else: y += 1
    return runs

grand = 0
print(f"{'folder':10s} {'paper':12s} {'pages':>5s} {'est_q':>6s}")
perfol = {}
for fol in sorted(os.listdir(SRC)):
    fdir = os.path.join(SRC, fol)
    if not os.path.isdir(fdir): continue
    for f in sorted(os.listdir(fdir)):
        if not f.lower().endswith(".pdf") or "markscheme" in f.lower(): continue
        path = os.path.join(fdir, f)
        doc = pdfium.PdfDocument(path)
        est = 0
        for pi in range(len(doc)):
            img = doc[pi].render(scale=SCALE).to_pil().convert("L")
            runs = detect_runs(img)
            # bands = runs+1 (each separator splits content); but if page has no
            # separator at all, it's 1 band. If runs present, (#runs+1) bands.
            est += max(1, len(runs))
        perfol.setdefault(fol, 0)
        perfol[fol] += est
        paper = f[:-4]
        print(f"{fol:10s} {paper:12s} {len(doc):5d} {est:6d}")
        grand += est
print("\n--- per folder ---")
for fol, n in sorted(perfol.items()):
    print(f"  {fol:10s}: ~{n} questions")
print(f"\nGRAND ESTIMATE (upper-ish): ~{grand} question records")
