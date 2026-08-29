#!/usr/bin/env python3
"""PROTOTYPE 10: robust answer-block alignment.
1) Build per-question markscheme blocks by splitting on 'Examiners report'.
2) Drop degenerate blocks (title/empty/header-only).
3) Monotonic DP aligning each question to a block, score = difflib-sim
   MINUS a position prior (favours order, lets similarity win locally).
Read-only: prints mapping + quality stats for Topic 1 HL-paper1.
"""
import os, re, json, sys, difflib
sys.path.insert(0, os.path.dirname(__file__))
import extract_math_topic as E
import pypdfium2 as pdfium

def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

MARK = re.compile(r"\[\d+\s*marks?\]|\[\d+\]")

STEM = re.compile(r"^\s*(?:a\.|\(a\)|b\.|\(b\)|\(c\)|\(i\)|\(ii\)|\(iii\)|"
                  r"The |Find |Show |Let |Given |Consider |Hence |A |An |Solve |"
                  r"Prove |Using |Write |Express |Determine |Calculate |Sketch |"
                  r"If |For |Find )", re.IGNORECASE)

PROMPT_END = re.compile(r"(?i)\(?\b(M1|A1|R1|AG|N0|N1|FT|WP)\b|\[\d+\s*marks?\]|Markscheme|Examiners\s+report")
def leading_prompt(b):
    m = PROMPT_END.search(b)
    if m: return b[:m.start()]
    return b[:240]

def block_text(full, s, e):
    region = full[s:e]
    er_m = re.search(r"Examiners\s+report", region)
    end = s + er_m.start() if er_m else e
    return full[s:end].strip()

def q_skeleton(qtext):
    t = E.strip_title(qtext)
    t = re.sub(r"\[\d+\s*marks?\]|\[\d+\]", "", t)
    return norm(t)

SOLN_MARK_ONLY = re.compile(r"(?i)^\s*(M1|A1|R1|AG|EITHER|OR|THEN|METHOD|Note|Accept|Allow|Do not|WP|FT)\b")
def is_q_block(b):
    t = b.strip()
    t = re.sub(r"^(Markscheme|Examiners report|HL Paper \d)\s*", "", t, flags=re.I)
    if len(t) < 40:
        return False
    if SOLN_MARK_ONLY.search(t[:25]):
        return False  # starts with a pure solution marker -> fragment, not a question
    if not MARK.search(t):
        return False  # must carry a marks tag (prompt or solution)
    return True

SUBPART = re.compile(r"^\s*(\(i\)|\(ii\)|\(iii\)|\(iv\)|ci\.|cii\.|ciii\.|civ\.|i\.|ii\.|iii\.|iv\.)", re.IGNORECASE)
def prompt_starts(full):
    out = []
    for m in re.finditer(r"\n", full):
        p = m.start() + 1
        line = full[p:p + 220]
        ls = line.strip()
        if not ls: continue
        if SOLN_MARK_ONLY.search(ls[:45]): continue
        tagm = MARK.search(line)
        if not tagm: continue
        ls_end = ls.rfind("]")
        if ls_end < 0 or ls_end < tagm.start(): continue
        if len(ls) - ls_end > 40: continue
        if not STEM.match(ls): continue
        if SUBPART.match(ls): continue   # subpart line -> merge into parent question
        out.append(p)
    return out

def build_blocks(full):
    starts = prompt_starts(full)
    raw = [block_text(full, s, starts[i+1] if i+1 < len(starts) else len(full)) for i, s in enumerate(starts)]
    raw = [re.sub(r"^\s*Markscheme\s*", "", b) for b in raw]
    return raw

def sim(a, b):
    if not a or not b: return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()

def align(qskel, cands, prior=0.03, bgap=0.20, qgap=0.60):
    """Monotonic alignment of questions -> candidate blocks (raw segments).
    Allows block-skips (bgap) and question-skips (qgap) so it never fails
    entirely when counts differ. score = sim - prior*|j-i|."""
    m = len(qskel)
    K = len(cands)
    def sc(i, k):
        _, b = cands[k]
        return sim(qskel[i], norm(leading_prompt(b))) - prior * abs(k - i)
    INF = -1e9
    dp = [[INF]*(K+1) for _ in range(m+1)]
    bt = [[None]*(K+1) for _ in range(m+1)]
    dp[0][0] = 0
    for i in range(m+1):
        for k in range(K+1):
            if dp[i][k] == INF: continue
            if i < m and k < K:
                s = sc(i, k)
                if dp[i][k] + s > dp[i+1][k+1]:
                    dp[i+1][k+1] = dp[i][k] + s; bt[i+1][k+1] = (i, k, 'a')
            if k < K and dp[i][k] - bgap > dp[i][k+1]:
                dp[i][k+1] = dp[i][k] - bgap; bt[i][k+1] = (i, k, 'sb')
            if i < m and dp[i][k] - qgap > dp[i+1][k]:
                dp[i+1][k] = dp[i][k] - qgap; bt[i+1][k] = (i, k, 'sq')
    pairing = [-1]*m
    i, k = m, K
    while i > 0 or k > 0:
        if bt[i][k] is None: break
        pi, pk, t = bt[i][k]
        if t == 'a': pairing[pi] = pk
        i, k = pi, pk
    return pairing

def main():
    man = json.load(open(E.MANIFEST, encoding="utf-8"))
    recs = [r for r in man if r.get("topic") == "Topic 1" and r.get("paper_type") == "HL-paper1"]
    recs.sort(key=lambda r: r["id"])
    ms_doc = pdfium.PdfDocument(E.SRC_ROOT + "/Topic 1/markscheme-HL-paper1.pdf")
    ms_index = E.build_markscheme_index(ms_doc)
    full = ms_index["full"]
    raw = build_blocks(full)
    print(f"raw_blocks={len(raw)} recs={len(recs)}")
    qskel = [q_skeleton(r["question_text"]) for r in recs]
    pairing = align(qskel, list(enumerate(raw)))
    mono = all(pairing[i] <= pairing[i+1] for i in range(len(pairing)-1) if pairing[i] >= 0 and pairing[i+1] >= 0)
    print("monotonic:", mono)
    # quality
    sims = []
    for i in range(len(recs)):
        k = pairing[i]
        if k < 0:
            sims.append(0.0); continue
        b = raw[k]
        sims.append(sim(qskel[i], norm(leading_prompt(b))))
    hi = sum(1 for s in sims if s >= 0.6)
    md = sum(1 for s in sims if 0.4 <= s < 0.6)
    lo = sum(1 for s in sims if s < 0.4)
    print(f"sim>=0.6: {hi} | 0.4-0.6: {md} | <0.4: {lo}")
    watch = {"Topic1_HL-paper1_q02","Topic1_HL-paper1_q06","Topic1_HL-paper1_q07","Topic1_HL-paper1_q26"}
    for i, r in enumerate(recs):
        qid = r["id"].replace("MA_HL_topic_", "")
        if qid in watch:
            k = pairing[i]
            btxt = raw[k] if k >= 0 else ""
            cr = "cuberoots" in norm(leading_prompt(btxt))
            print(f"[{qid}] -> raw#{k} sim={sims[i]:.2f} cube={cr} | {btxt[:60].replace(chr(10),' ')}")
    print("first 16:", [(recs[i]['id'].replace('MA_HL_topic_',''), pairing[i]) for i in range(16)])

if __name__ == "__main__":
    main()
