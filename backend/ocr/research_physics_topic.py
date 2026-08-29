#!/usr/bin/env python3
"""PHASE A RESEARCH PROBE for Session 11 — Physics HL Topic questions.

READ-ONLY. No manifest/figure writes. Goal:
  1. Inventory every PDF (topic/option x paper) + page counts.
  2. Confirm born-digital TEXT layer (not scanned).
  3. Detect whether questions are separated by light horizontal rule lines
     (the same band-detection the Math extractor relies on).
  4. Probe the markscheme: do answers repeat the question prompt? Are there
     "[N marks]" anchors? -> validates the prompt-matching answer strategy.
  5. Flag naming inconsistencies + cover-only pages.
"""
import os, re, json
import pypdfium2 as pdfium
import numpy as np

SRC = "/Users/lucas.ma/Downloads/dp learning/Physics-HL-Topic questions"
SCALE = 2.0
SEP_STD_MAX = 10
SEP_BR_RANGE = (90, 250)
INK_FRAC_MAX = 0.01

TITLE_LEAD = re.compile(r"^\s*hl\.?\s*p\w*r\s*\d+\s*p?\s*[\r\n]*", re.I)
def strip_title(t):
    return TITLE_LEAD.sub("", t or "").strip() if t else t
def is_cover(t):
    raw = (t or "").strip()
    if not raw or not re.search(r"\d", raw): return False
    return len(re.sub(r"[^a-z0-9]", "", strip_title(raw).lower())) < 3

def detect_separator_runs(img_gray):
    arr = np.asarray(img_gray)
    means = arr.mean(axis=1); stds = arr.std(axis=1); ink = (arr < 128).mean(axis=1)
    cand = (stds < SEP_STD_MAX) & (ink < INK_FRAC_MAX) & (means > SEP_BR_RANGE[0]) & (means < SEP_BR_RANGE[1])
    H = arr.shape[0]; runs = []; y = 0
    while y < H:
        if cand[y]:
            y0 = y
            while y < H and cand[y]: y += 1
            runs.append((y0, y - 1))
        else:
            y += 1
    return runs

def page_text(doc, pi):
    return doc[pi].get_textpage().get_text_range()

def alpha_norm(s):
    s = re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())
    return re.sub(r"\s+", " ", s).strip()

def main():
    # ---- 1. Inventory ----
    print("\n================ 1. INVENTORY ================")
    folders = sorted([d for d in os.listdir(SRC) if os.path.isdir(os.path.join(SRC, d))])
    inv = {}   # folder -> {paper_name: (qpdf, mspdf, qpages, mspages)}
    for fol in folders:
        fdir = os.path.join(SRC, fol)
        files = os.listdir(fdir)
        qmap, mmap = {}, {}
        for f in files:
            if not f.lower().endswith(".pdf"): continue
            low = f.lower()
            is_ms = "markscheme" in low
            # paper name = strip "markscheme-" prefix and ".pdf"
            base = f[:-4]
            if is_ms:
                pname = re.sub(r"^markscheme-", "", base, flags=re.I)
                mmap[pname] = f
            else:
                qmap[base] = f
        inv[fol] = {"q": qmap, "ms": mmap}
        papers = sorted(set(qmap) | set(mmap))
        print(f"  {fol:10s}: papers = {papers}")

    # ---- 2-5. Probe representative samples ----
    print("\n================ 2-5. STRUCTURE PROBES ================")
    samples = []
    # core (lowercase naming)
    samples.append(("Topic 1", "HL-paper1"))
    samples.append(("Topic 12", "HL-paper3"))
    # option B (inconsistent CAPITAL naming)
    samples.append(("Option B", "HL-Paper-1"))
    # option A (lowercase, paper3 only)
    samples.append(("Option A", "HL-paper3"))

    for fol, pname in samples:
        if fol not in inv: 
            print(f"\n--- {fol}/{pname}: FOLDER MISSING ---"); continue
        qf = inv[fol]["q"].get(pname)
        msf = inv[fol]["ms"].get(pname)
        if not qf:
            print(f"\n--- {fol}/{pname}: QUESTION PDF MISSING (have q={list(inv[fol]['q'])} ms={list(inv[fol]['ms'])}) ---")
            continue
        qpath = os.path.join(SRC, fol, qf)
        mspath = os.path.join(SRC, fol, msf) if msf else None
        print(f"\n--- {fol} / {pname} ---")
        print(f"    qfile={qf}  msfile={msf}")

        qdoc = pdfium.PdfDocument(qpath)
        qpages = len(qdoc)
        # text layer (born-digital?) — sum chars over all pages
        q_chars = sum(len(page_text(qdoc, i)) for i in range(qpages))
        print(f"    QUESTION: pages={qpages}  total_text_chars={q_chars}  (~{q_chars//max(qpages,1)} chars/page)")

        # separator / band detection on first 3 pages
        band_counts = []
        for pi in range(min(3, qpages)):
            img = qdoc[pi].render(scale=SCALE).to_pil().convert("L")
            runs = detect_separator_runs(img)
            nbands = len(runs)
            band_counts.append(nbands)
        print(f"    separator runs on first 3 pages = {band_counts}  (0 => no rule lines, questions NOT visually separated)")

        # cover-page check on page 1
        p1 = page_text(qdoc, 0)
        p1_stripped = strip_title(p1)
        print(f"    p1 text (first 220c): {p1[:220]!r}")
        print(f"    p1 is_cover={is_cover(p1)}  | p1 stripped-len={len(p1_stripped)}")

        # markscheme probe
        if mspath:
            msdoc = pdfium.PdfDocument(mspath)
            mspages = len(msdoc)
            ms_chars = sum(len(page_text(msdoc, i)) for i in range(mspages))
            full_ms = "\n".join(page_text(msdoc, i) for i in range(mspages))
            n_marks = len(re.findall(r"\[\d+\s*marks?\]", full_ms))
            # Does the markscheme repeat the question prompt? Test with first question's prompt.
            # Take first ~70 alpha chars of p1 question (after stripping title).
            qp = alpha_norm(p1_stripped)[:70]
            prompt_in_ms = (qp[:40] in alpha_norm(full_ms)) if len(qp) >= 20 else None
            print(f"    MARKSCHEME: pages={mspages}  total_text_chars={ms_chars}  '[N marks]' count={n_marks}")
            print(f"    markscheme repeats Q1 prompt? {prompt_in_ms}  (Q1 alpha-prefix={qp!r})")
            print(f"    markscheme p1 (first 200c): {full_ms[:200]!r}")
        else:
            print("    MARKSCHEME: MISSING")

    print("\n================ DONE ================")

if __name__ == "__main__":
    main()
