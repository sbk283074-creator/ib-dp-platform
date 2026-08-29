#!/usr/bin/env python3
"""PROTOTYPE 12: seed-based independent locator + answer-region extraction.
For each manifest question (order, monotonic lower bound):
  - build many candidate seeds (whole, suffixes, prefixes, mid chunks) of the
    OCR'd skeleton; the FIRST seed that is an EXACT substring of the markscheme
    norm AND verifies (difflib sim of full Q vs window > 0.5) gives the block.
  - answer region = markscheme[found : next 'Examiners report'].
Read-only: reports stats + watch questions for Topic 1 HL-paper1.
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

def seeds_of(Q):
    L = len(Q)
    out = [Q]
    for Ln in (70, 55, 40, 30, 22, 16, 11):
        if L >= Ln:
            out.append(Q[-Ln:])          # suffixes
            out.append(Q[:Ln])           # prefixes
    for s in range(0, max(1, L - 28), 14):
        out.append(Q[s:s + 28])          # mid chunks
    # dedupe preserve order
    seen = set(); uniq = []
    for x in out:
        if x and x not in seen:
            seen.add(x); uniq.append(x)
    return uniq

def locate(Q, hay, start):
    for seed in seeds_of(Q):
        if len(seed) < 8: continue
        p = hay.find(seed, start)
        while p != -1:
            w = hay[max(0, p - 120):p + len(Q) + 250]
            if difflib.SequenceMatcher(None, Q, w).ratio() > 0.5:
                return p
            p = hay.find(seed, p + 1)
    return -1

def answer_text(full, start):
    region = full[start:start + 6000]
    er = re.search(r"Examiners\s+report", region)
    end = start + er.start() if er else start + min(5500, len(region))
    return full[start:end].strip()

def main():
    man = json.load(open(E.MANIFEST, encoding="utf-8"))
    recs = [r for r in man if r.get("topic") == "Topic 1" and r.get("paper_type") == "HL-paper1"]
    recs.sort(key=lambda r: r["id"])
    ms_doc = pdfium.PdfDocument(E.SRC_ROOT + "/Topic 1/markscheme-HL-paper1.pdf")
    M_full = E.build_markscheme_index(ms_doc)["full"]
    hay = norm(M_full)

    LB = 0
    mapped = 0
    bleed = 0
    watch = {"Topic1_HL-paper1_q02","Topic1_HL-paper1_q06","Topic1_HL-paper1_q07","Topic1_HL-paper1_q26"}
    for i, r in enumerate(recs):
        Q = q_skeleton(r["question_text"])
        p = locate(Q, hay, LB)
        if p < 0:
            print(f"[{r['id'].replace('MA_HL_topic_','')}] LOC FAIL (LB={LB})")
            LB = min(len(hay), LB + 1200)
            continue
        mapped += 1
        LB = p + 1
        ans = answer_text(M_full, p)
        if "Examiners report" in ans:
            bleed += 1
        if r["id"].endswith(tuple(watch)):
            cr = "cuberoots" in norm(ans)
            print(f"[{r['id'].replace('MA_HL_topic_','')}] pos={p} cube={cr} | ANS: {ans[:90].replace(chr(10),' ')}")
    print(f"\nmapped={mapped}/{len(recs)} still_bleed={bleed}")

if __name__ == "__main__":
    main()
