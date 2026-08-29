#!/usr/bin/env python3
"""PROTOTYPE 11: independent per-question locator (no pre-segmentation).
For each manifest question (in order):
  1) locate it in the CLEAN question PDF (sliding-window difflib vs OCR'd skel,
     monotonic lower bound) -> get the CLEAN question prompt text.
  2) locate that CLEAN prompt in the CLEAN markscheme -> answer start.
  3) answer region = markscheme[start : next 'Examiners report'].
Read-only: prints mapped markscheme position + answer snippet for watch questions.
"""
import os, re, json, sys, difflib
sys.path.insert(0, os.path.dirname(__file__))
import extract_math_topic as E
import pypdfium2 as pdfium

def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def q_skeleton(qtext):
    t = E.strip_title(qtext)
    t = re.sub(r"\[\d+\s*marks?\]|\[\d+\]", "", t)
    return norm(t)

def window_search(hay, needle_norm, lo, hi, step=40, wpad=120):
    """Return (best_raw_pos, best_sim) of the window in hay[lo:hi] whose norm
    best matches needle_norm."""
    best_pos, best_sim = -1, -1.0
    wl = max(60, len(needle_norm))
    end = min(hi, len(hay))
    s = lo
    while s + wl <= end:
        w = hay[s:s + wl + wpad]
        sc = difflib.SequenceMatcher(None, needle_norm, norm(w)).ratio()
        if sc > best_sim:
            best_sim, best_pos = sc, s
        s += step
    # refine around best with fine step
    if best_pos >= 0:
        fine_lo = max(lo, best_pos - step)
        fine_hi = min(end, best_pos + step + wl + wpad)
        s = fine_lo
        while s + wl <= fine_hi:
            w = hay[s:s + wl + wpad]
            sc = difflib.SequenceMatcher(None, needle_norm, norm(w)).ratio()
            if sc > best_sim:
                best_sim, best_pos = sc, s
            s += 5
    return best_pos, best_sim

PROMPT_END = re.compile(r"(?i)\(?\b(M1|A1|R1|AG|N0|N1|Note|Accept|Allow|Do not|METHOD|EITHER|OR|THEN|Total|FT|WP)\b|\[\d+\s*marks?\]|Markscheme|Examiners\s+report")
def answer_region(full, start):
    """Answer region = full[start : next 'Examiners report'] (or 4000 cap)."""
    region = full[start:start + 5000]
    er = re.search(r"Examiners\s+report", region)
    end = start + er.start() if er else start + min(4500, len(region))
    return full[start:end].strip()

def main():
    man = json.load(open(E.MANIFEST, encoding="utf-8"))
    recs = [r for r in man if r.get("topic") == "Topic 1" and r.get("paper_type") == "HL-paper1"]
    recs.sort(key=lambda r: r["id"])
    tn = 1
    tdir = os.path.join(E.SRC_ROOT, f"Topic {tn}")
    q_doc = pdfium.PdfDocument(tdir + "/HL-paper1.pdf")
    ms_doc = pdfium.PdfDocument(tdir + "/markscheme-HL-paper1.pdf")
    Q_full = E.build_markscheme_index(q_doc)["full"]
    M_full = E.build_markscheme_index(ms_doc)["full"]

    LB_q = 0
    LB_m = 0
    watch = {"Topic1_HL-paper1_q02","Topic1_HL-paper1_q06","Topic1_HL-paper1_q07","Topic1_HL-paper1_q26"}
    ok = 0
    for i, r in enumerate(recs):
        qsk = q_skeleton(r["question_text"])
        # Step 1: locate in clean question PDF
        pq, sq = window_search(Q_full, qsk, LB_q, min(len(Q_full), LB_q + 25000))
        if pq < 0:
            print(f"[{r['id'].replace('MA_HL_topic_','')}] Q-LOC FAIL")
            LB_q = min(len(Q_full), LB_q + 1500)
            continue
        # extract clean prompt (window around pq)
        clean_prompt = Q_full[pq:pq + 700]
        # Step 2: locate clean prompt in clean markscheme
        pm, sm = window_search(M_full, norm(clean_prompt), LB_m, min(len(M_full), LB_m + 35000))
        if pm < 0:
            print(f"[{r['id'].replace('MA_HL_topic_','')}] M-LOC FAIL (sq={sq:.2f})")
            LB_m = min(len(M_full), LB_m + 1500)
            continue
        ok += 1
        LB_q = pq + 50
        LB_m = pm + 50
        if r["id"].endswith(tuple(watch)):
            ans = answer_region(M_full, pm)
            cr = "cuberoots" in norm(ans)
            print(f"[{r['id'].replace('MA_HL_topic_','')}] Mpos={pm} sq={sq:.2f} sm={sm:.2f} cube={cr} | ANS: {ans[:85].replace(chr(10),' ')}")
    print(f"\nOK={ok}/{len(recs)}")

if __name__ == "__main__":
    main()
