#!/usr/bin/env python3
"""PROTOTYPE 7: anchor-substring similarity + monotonic DP. Validates T1 P1."""
import os, re, json, sys
sys.path.insert(0, os.path.dirname(__file__))
import extract_math_topic as E

SRC = E.SRC_ROOT
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

def anchors(qtext):
    """Return list of normalized sub-phrase anchors (>=12 chars) from a question.
    Split on sub-part labels so each sub-part (esp. the last/distinctive one) is
    its own anchor — those ARE substrings of the markscheme block."""
    t = E.strip_title(qtext)
    t = MARK.sub("", t)            # drop [N] marks tags
    label_re = re.compile(r"(?<![a-z])(a|b|c|d|e|f|i{1,3}|iv|v{1,3}|vi{1,3}|ci{1,3}|civ)\.?\s*", re.IGNORECASE)
    positions = [m.start() for m in label_re.finditer(t)]
    if not positions:
        positions = [0]
    out = []
    for k, pos in enumerate(positions):
        end = positions[k + 1] if k + 1 < len(positions) else len(t)
        pn = norm(t[pos:end])
        if len(pn) >= 12:
            out.append(pn)
    tail = norm(t)
    if len(tail) >= 12:
        out.append(tail)
    return out

def score_block(qanchors, bnorm):
    best = 0
    for a in qanchors:
        if a and a in bnorm:
            best = max(best, len(a))
    return best

def dp_align(A, B, gap=10.0):
    m, n = len(A), len(B)
    INF = -1e9
    dp = [[INF]*(n+1) for _ in range(m+1)]
    bt = [[None]*(n+1) for _ in range(m+1)]
    dp[0][0] = 0
    for i in range(m+1):
        for j in range(n+1):
            if dp[i][j] == INF: continue
            if i < m and j < n:
                s = A[i][j]
                if dp[i][j] + s > dp[i+1][j+1]:
                    dp[i+1][j+1] = dp[i][j] + s; bt[i+1][j+1] = (i, j, 'a')
            if j < n and dp[i][j] - gap > dp[i][j+1]:
                dp[i][j+1] = dp[i][j] - gap; bt[i][j+1] = (i, j, 'sb')
    pairing = [-1]*m
    i, j = m, n
    while i > 0 or j > 0:
        if bt[i][j] is None: break
        pi, pj, t = bt[i][j]
        if t == 'a': pairing[pi] = pj
        i, j = pi, pj
    return pairing

def main():
    man = json.load(open(E.MANIFEST, encoding="utf-8"))
    recs = [r for r in man if r.get("topic") == "Topic 1" and r.get("paper_type") == "HL-paper1"]
    recs.sort(key=lambda r: r["id"])

    ms_pdf = os.path.join(SRC, "Topic 1", "markscheme-HL-paper1.pdf")
    ms_doc = __import__("pypdfium2").PdfDocument(ms_pdf)
    E._MS_DOC = ms_doc
    ms_index = E.build_markscheme_index(ms_doc)
    full = ms_index["full"]
    starts = prompt_starts(full)
    blocks = [block_text(full, s, starts[i+1] if i+1 < len(starts) else len(full)) for i, s in enumerate(starts)]
    bnorm = [norm(b) for b in blocks]
    print(f"blocks={len(blocks)} recs={len(recs)}")

    A = []
    for r in recs:
        a = anchors(r["question_text"])
        A.append([score_block(a, bnorm[j]) for j in range(len(blocks))])
    pairing = dp_align(A, blocks)
    mono = all(pairing[i] <= pairing[i+1] for i in range(len(pairing)-1) if pairing[i] >= 0 and pairing[i+1] >= 0)
    print("monotonic:", mono)
    for idx, r in enumerate(recs):
        qid = r["id"].replace("MA_HL_topic_", "")
        j = pairing[idx]
        if qid in ("Topic1_HL-paper1_q07","Topic1_HL-paper1_q02","Topic1_HL-paper1_q06","Topic1_HL-paper1_q26"):
            cr = "cube roots" in blocks[j].lower()
            print(f"[{qid}] -> block#{j} score={A[idx][j]} cube_roots={cr} | {blocks[j][:80].replace(chr(10),' ')}")
    print("pairing first 14:", pairing[:14])
    # how many got score 0 (no anchor matched)?
    zero = sum(1 for i in range(len(recs)) if A[i][pairing[i]] == 0)
    print("questions with score-0 pairing:", zero)

if __name__ == "__main__":
    main()
