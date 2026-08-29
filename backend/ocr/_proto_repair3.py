#!/usr/bin/env python3
"""PROTOTYPE 9: independent per-question block location via subsequence match
seeded by a distinctive exact substring of the question skeleton. Read-only test
on Topic 1 HL-paper1: prints matched block start + answer text snippet.
"""
import os, re, json, sys
sys.path.insert(0, os.path.dirname(__file__))
import extract_math_topic as E
import pypdfium2 as pdfium

def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def is_subseq(needle, hay):
    it = iter(hay)
    return all(c in it for c in needle)

def find_subseq_start(needle, hay, lo, hi):
    if hi > len(hay): hi = len(hay)
    for s in range(lo, hi):
        if is_subseq(needle, hay[s:hi]):
            return s
    return -1

def locate_block(Q, hay, start):
    """Find the char position in `hay` (>= start) where question skeleton Q
    appears as a subsequence, anchored by an exact distinctive substring seed."""
    # candidate seeds: distinctive suffixes of Q (longest first -> most unique)
    seeds = []
    for L in (70, 55, 40, 28, 18, 12):
        if len(Q) >= L:
            seeds.append(Q[-L:])
    # also a mid distinctive chunk
    if len(Q) >= 50:
        seeds.append(Q[20:20+40])
    for seed in seeds:
        p = hay.find(seed, start)
        while p != -1:
            # verify Q is a subsequence in a window around p
            lo = max(0, p - 200)
            hi = min(len(hay), p + 400)
            s = find_subseq_start(Q, hay, lo, hi)
            if s != -1:
                return s
            p = hay.find(seed, p + 1)
    return -1

def main():
    man = json.load(open(E.MANIFEST, encoding="utf-8"))
    recs = [r for r in man if r.get("topic") == "Topic 1" and r.get("paper_type") == "HL-paper1"]
    recs.sort(key=lambda r: r["id"])

    tn = 1
    tdir = os.path.join(E.SRC_ROOT, f"Topic {tn}")
    ms_pdf = os.path.join(tdir, "markscheme-HL-paper1.pdf")
    ms_doc = pdfium.PdfDocument(ms_pdf)
    ms_index = E.build_markscheme_index(ms_doc)
    full = ms_index["full"]
    hay = norm(full)

    lower = 0
    ok = 0
    for idx, r in enumerate(recs):
        Q = norm(E.strip_title(E.MARK.sub("", r["question_text"]))) if False else norm(E.strip_title(re.sub(r"\[\d+\s*marks?\]|\[\d+\]", "", r["question_text"])))
        p = locate_block(Q, hay, lower)
        if p == -1:
            print(f"[{r['id'].replace('MA_HL_topic_','')}] NOT FOUND (lower={lower})")
            lower = min(len(hay), lower + 300)  # advance so we don't loop forever on later ones
            continue
        ok += 1
        # answer region: from p to next question's start (we approximate by next '[N marks]' total after a gap, or 4000 chars)
        region = full[p:p + 4000]
        # cut at next 'Examiners report' if present within region
        er = re.search(r"Examiners\s+report", region)
        end = p + er.start() if er else p + min(4000, len(region))
        ans = full[p:end].strip()
        lower = p + 1  # monotonic lower bound for next question
        if r["id"].endswith(("Topic1_HL-paper1_q02","Topic1_HL-paper1_q06","Topic1_HL-paper1_q07","Topic1_HL-paper1_q26")):
            print(f"[{r['id'].replace('MA_HL_topic_','')}] pos={p} | ANS: {ans[:90].replace(chr(10),' ')}")
    print(f"\nOK={ok}/{len(recs)}")

if __name__ == "__main__":
    main()
