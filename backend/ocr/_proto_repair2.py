#!/usr/bin/env python3
"""PROTOTYPE 8: fuzzy (3-gram Jaccard) align of manifest questions -> markscheme
blocks, using each block's LEADING PROMPT (repeated question text) as the
comparison target. Tests on Topic 1 HL-paper1 only (read-only: prints mapping).
"""
import os, re, json, sys
sys.path.insert(0, os.path.dirname(__file__))
import extract_math_topic as E
import pypdfium2 as pdfium

STEM = re.compile(r"^\s*(?:a\.|\(a\)|b\.|\(b\)|\(c\)|\(i\)|\(ii\)|\(iii\)|"
                  r"The |Find |Show |Let |Given |Consider |Hence |A |An |Solve |"
                  r"Prove |Using |Write |Express |Determine |Calculate |Sketch |"
                  r"If |For |Find )", re.IGNORECASE)
SOLN_MARK = re.compile(r"(?i)\b(M1|A1|R1|AG|N0|N1|Note|Accept|Allow|Do not|Hence|Thus|So|METHOD|EITHER|OR|THEN|Total|FT|WP)\b")
MARK = re.compile(r"\[\d+\s*marks?\]|\[\d+\]")

def prompt_starts(full):
    out = []
    for m in re.finditer(r"\n", full):
        p = m.start() + 1
        line = full[p:p + 220]
        ls = line.strip()
        if not ls: continue
        if SOLN_MARK.search(ls[:45]): continue
        tagm = MARK.search(line)
        if not tagm: continue
        ls_end = ls.rfind("]")
        if ls_end < 0 or ls_end < tagm.start(): continue
        if len(ls) - ls_end > 40: continue
        if not STEM.match(ls): continue
        out.append(p)
    return out

def block_text(full, s, e):
    region = full[s:e]
    er_m = re.search(r"Examiners\s+report", region)
    end = s + er_m.start() if er_m else e
    return full[s:end].strip()

def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

# Prompt portion of a markscheme block ends at the first SOLUTION marker
# (M1/A1/R1/AG, possibly parenthesised) or the total "[N marks]" tag or
# "Examiners report". Per-subpart "[N]" tags must NOT cut the prompt short.
PROMPT_END = re.compile(r"(?i)\(?\b(M1|A1|R1|AG|N0|N1|FT|WP)\b|\[\d+\s*marks?\]|Markscheme|Examiners\s+report")
def leading_prompt(b):
    """The repeated question prompt at the top of a markscheme block:
    everything up to the first solution marker."""
    m = PROMPT_END.search(b)
    if m: return b[:m.start()]
    return b[:240]

def q_skeleton(qtext):
    t = E.strip_title(qtext)
    t = MARK.sub("", t)
    return norm(t)

def trigrams(s):
    return set(s[i:i+3] for i in range(len(s) - 2))

def jac(a, b):
    A, B = trigrams(a), trigrams(b)
    if not A or not B: return 0.0
    return len(A & B) / len(A | B)

import difflib
def sim(a, b):
    """Noise-tolerant similarity (LCS-based, 0..1) via difflib. Tolerates both
    dropped and inserted characters from OCR noise, unlike trigram Jaccard."""
    if not a or not b: return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()

def greedy_align(A, nblocks, min_gap=0.30):
    """Monotonic greedy: each question i gets its best-scoring unused block j
    with j > previous block. Robust when each question's own block scores high
    and uniquely. Returns pairing[i] = block index (or -1 if none >= min_gap)."""
    m = len(A)
    pairing = [-1]*m
    prev_j = -1
    used = [False]*nblocks
    for i in range(m):
        best_j, best_s = -1, -1.0
        for j in range(prev_j+1, nblocks):
            if used[j]: continue
            if A[i][j] > best_s:
                best_s, best_j = A[i][j], j
        if best_j == -1:  # fallback: any unused block
            for j in range(nblocks):
                if not used[j] and A[i][j] > best_s:
                    best_s, best_j = A[i][j], j
        pairing[i] = best_j
        if best_j >= 0:
            used[best_j] = True
            prev_j = best_j
    return pairing

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
    # Per-QUESTION blocks: split on "Examiners report" (≈1 per question), which
    # is a reliable delimiter (unlike prompt_starts which over-splits subparts).
    ers = [m.start() for m in re.finditer(r"Examiners\s+report", full)]
    starts = [0]
    for e in ers:
        tail = full[e:e + 60]
        m2 = re.match(r"Examiners\s+report\s*Markscheme\s*", tail)
        s = e + (m2.end() if m2 else len(re.match(r"Examiners\s+report", tail).group()))
        starts.append(s)
    starts = sorted(set(starts))
    blocks = [block_text(full, s, starts[i+1] if i+1 < len(starts) else len(full)) for i, s in enumerate(starts)]
    blocks = [re.sub(r"^\s*Markscheme\s*", "", b) for b in blocks]
    # leading-prompt skeletons
    bskel = [norm(leading_prompt(b)) for b in blocks]
    print(f"blocks={len(blocks)} recs={len(recs)}")

    qskel = [q_skeleton(r["question_text"]) for r in recs]
    A = []
    for i in range(len(recs)):
        A.append([sim(qskel[i], bskel[j]) for j in range(len(blocks))])
    pairing = greedy_align(A, len(blocks))
    mono = all(pairing[i] <= pairing[i+1] for i in range(len(pairing)-1) if pairing[i] >= 0 and pairing[i+1] >= 0)
    print("monotonic:", mono)

    watch = {"Topic1_HL-paper1_q02","Topic1_HL-paper1_q06","Topic1_HL-paper1_q07","Topic1_HL-paper1_q26"}
    for idx, r in enumerate(recs):
        qid = r["id"].replace("MA_HL_topic_", "")
        j = pairing[idx]
        if qid in watch:
            cr = "cube roots" in blocks[j].lower() or "cuberoots" in bskel[j]
            print(f"[{qid}] -> block#{j} jac={A[idx][j]:.2f} cube_roots={cr} | {blocks[j][:70].replace(chr(10),' ')}")
    print("pairing first 14:", pairing[:14])
    # score distribution
    scores = [A[i][pairing[i]] for i in range(len(recs)) if pairing[i] >= 0]
    hi = sum(1 for s in scores if s >= 0.5)
    mid = sum(1 for s in scores if 0.3 <= s < 0.5)
    lo = sum(1 for s in scores if s < 0.3)
    print(f"jaccard>=0.5: {hi} | 0.3-0.5: {mid} | <0.3: {lo} (of {len(scores)} mapped)")

if __name__ == "__main__":
    main()
