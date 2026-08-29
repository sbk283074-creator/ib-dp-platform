#!/usr/bin/env python3
"""Prototype 13b: relaxed fuzzy-local locator (no strict prefilter, short needle)."""
import os, re, json, difflib, time
import pypdfium2 as pdfium

SRC_ROOT = "/Users/lucas.ma/Downloads/dp learning/IB数学AA  HL 分章练习/IB数学AA-Mathmatics HL IB Question Bank"
MANIFEST = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/data/math_topic_manifest.json"
TITLE_LEAD = re.compile(r"^\s*hl\.?\s*p\w*r\s*\d+\s*p?\s*[\r\n]*", re.I)

def strip_title(text):
    return TITLE_LEAD.sub("", text or "").strip()
def anorm(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()
def skeleton(qtext):
    t = strip_title(qtext)
    t = re.sub(r"\[\s*\d+\s*(?:marks?)?\s*\]", " ", t)
    return anorm(t)

def build_hay(mspdf):
    doc = pdfium.PdfDocument(mspdf)
    raw = "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
    return raw, anorm(raw)

def locate(needle, hay, start, window=14000, step=6):
    seg = hay[start:start + window]
    best_pos, best_score = -1, 0.0
    L = len(needle)
    if L < 12 or len(seg) < L:
        return -1, 0.0
    pos = 0
    while pos <= len(seg) - L:
        w = seg[pos:pos + L]
        s = difflib.SequenceMatcher(None, needle, w).ratio()
        if s > best_score:
            best_score = s
            best_pos = start + pos
        pos += step
    return best_pos, best_score

def main():
    recs = json.load(open(MANIFEST))
    tn, paper = 1, "HL-paper1"
    sel = [r for r in recs if r['topic'] == f"Topic {tn}" and r['paper_type'] == paper]
    mspdf = os.path.join(SRC_ROOT, f"Topic {tn}", "markscheme-" + paper + ".pdf")
    raw, hay = build_hay(mspdf)
    print(f"hay len={len(hay)}  questions={len(sel)}")
    t0 = time.time()
    prev_end = 0
    fails = 0
    for i, r in enumerate(sel):
        sk = skeleton(r['question_text'])
        # try full skeleton and the last 90 chars (often the distinctive math)
        best = (-1, 0.0)
        for ndl in (sk, sk[-90:]):
            if len(ndl) < 12:
                continue
            p, s = locate(ndl, hay, prev_end, window=14000, step=6)
            if s > best[1]:
                best = (p, s)
        pos, score = best
        if pos < 0 or score < 0.4:
            fails += 1
            print(f"  [{r['source']}] FAIL score={score:.2f} LB={prev_end} skel={sk[:50]!r}")
            # advance past one [N marks] block
            m = re.search(r"\[\s*\d+\s*marks?\s*\]", raw[prev_end:prev_end + 6000])
            prev_end = (prev_end + m.end()) if m else min(len(raw), prev_end + 1500)
            continue
        print(f"  [{r['source']}] score={score:.2f} pos={pos} snip={hay[pos:pos+50]!r}")
        prev_end = pos + max(len(sk), 60)
    print(f"\nTIME={time.time()-t0:.1f}s  FAILS={fails}/{len(sel)}")

if __name__ == "__main__":
    main()
