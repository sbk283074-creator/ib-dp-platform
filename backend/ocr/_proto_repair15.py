#!/usr/bin/env python3
"""Prototype 15: hybrid answer locator (fuzzy-local + strong-anchor fallback).

For each manifest question (in order) we need a START position in the clean
markscheme. We try:
  (1) fuzzy-local difflib match of the (alphanumeric) skeleton against a
      forward window from prev_end  -> high confidence, exact pairing.
  (2) if (1) fails, jump prev_end to the next STRONG structural anchor
      (a subpart-label line carrying a per-subpart [N] mark). This keeps the
      search monotonic and prevents the crawl-past-end cascade.
Answer region for question i = raw[start_i : start_{i+1}), trimmed at the first
"Examiners report" so the answer excludes examiner commentary.
"""
import os, re, json, difflib, time, bisect
import pypdfium2 as pdfium

SRC_ROOT = "/Users/lucas.ma/Downloads/dp learning/IB数学AA  HL 分章练习/IB数学AA-Mathmatics HL IB Question Bank"
MANIFEST = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/data/math_topic_manifest.json"
TITLE_LEAD = re.compile(r"^\s*hl\.?\s*p\w*r\s*\d+\s*p?\s*[\r\n]*", re.I)

def strip_title(t):
    return TITLE_LEAD.sub("", t or "").strip()
def anorm(s):
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()
def skeleton(qtext):
    t = strip_title(qtext)
    t = re.sub(r"\[\s*\d+\s*(?:marks?)?\s*\]", " ", t)
    return anorm(t)

CMD_WORD = re.compile(r"\b(find|show|prove|consider|let|given|express|write|calculate|determine|solve|state|derive|sketch|hence|using|obtain|deduce|expand|simplify|factorise|the |the)\b", re.I)

def anorm_map(s):
    """Return (hay, to_raw) where hay[i] maps to raw char index to_raw[i]."""
    hay = []; to_raw = []
    i = 0; n = len(s)
    while i < n:
        ch = s[i]
        if ch.isspace():
            if hay and hay[-1] != ' ':
                hay.append(' '); to_raw.append(i)
            while i < n and s[i].isspace():
                i += 1
        elif ch.isalnum():
            hay.append(ch.lower()); to_raw.append(i); i += 1
        else:
            i += 1
    return "".join(hay), to_raw

def build(ms_pdf):
    doc = pdfium.PdfDocument(ms_pdf)
    raw = "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
    hay, to_raw = anorm_map(raw)
    # strong anchors: subpart label line carrying a [N] mark, AND the text after the
    # label looks like a QUESTION (has a command word), not a solution ("a. A1 [3]").
    anchors = []
    for m in re.finditer(r"(?m)^\s*[a-z]\.\s.*?\[\s*\d+\s*(?:marks?)?\s*\]", raw):
        line = raw[m.start():m.start() + 200].split("\n")[0]
        after = re.sub(r"^\s*[a-z]\.\s", "", line)
        after = re.sub(r"\[\s*\d+\s*(?:marks?)?\s*\]", "", after)
        if CMD_WORD.search(after) or len(after.strip()) > 25:
            anchors.append(m.start())
    return raw, hay, to_raw, anchors

def locate(needle, hay, to_raw, start, window=14000, step=6):
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
            best_pos = to_raw[start + pos] if start + pos < len(to_raw) else start + pos
        pos += step
    return best_pos, best_score

def main():
    recs = json.load(open(MANIFEST))
    tn, paper = 1, "HL-paper1"
    sel = [r for r in recs if r['topic'] == f"Topic {tn}" and r['paper_type'] == paper]
    mspdf = os.path.join(SRC_ROOT, f"Topic {tn}", "markscheme-" + paper + ".pdf")
    raw, hay, to_raw, anchors = build(mspdf)
    n_anchor = len(anchors)
    print(f"hay={len(hay)} questions={len(sel)} strong_anchors={n_anchor}")

    t0 = time.time()
    starts = []          # RAW positions (for region extraction)
    method = []
    prev_hay = 0         # search start in HAY space
    ai = 0
    for r in sel:
        sk = skeleton(r['question_text'])
        best = (-1, 0.0)
        for ndl in (sk, sk[-90:]):
            if len(ndl) < 12:
                continue
            p, s = locate(ndl, hay, to_raw, prev_hay, window=14000, step=6)
            if s > best[1]:
                best = (p, s)
        pos, score = best
        if pos is not None and pos >= 0 and score >= 0.30:
            starts.append(pos)          # pos already converted to RAW by locate
            method.append('L')
            prev_hay = bisect.bisect_left(to_raw, pos) + 1
        else:
            # fallback: next strong anchor (RAW) after the previous raw start
            prev_raw = starts[-1] if starts else 0
            while ai < n_anchor and anchors[ai] <= prev_raw:
                ai += 1
            if ai < n_anchor:
                starts.append(anchors[ai]); method.append('A'); ai += 1
                prev_hay = bisect.bisect_left(to_raw, anchors[ai - 1]) + 1
            else:
                avg = len(raw) // max(1, len(sel))
                starts.append(prev_raw + avg); method.append('X')
                prev_hay = bisect.bisect_left(to_raw, starts[-1]) + 1
    print(f"locator={method.count('L')} anchor={method.count('A')} xfail={method.count('X')}")

    # build regions + stats
    bleed = 0
    samples = []
    for i, r in enumerate(sel):
        s = starts[i]
        e = starts[i + 1] if i + 1 < len(starts) else len(raw)
        region = raw[s:e]
        er = region.find("Examiners report")
        if er >= 0:
            region = region[:er]
        region = region.strip()
        if "Examiners report" in region:
            bleed += 1
        if i < 6 or r['source'].endswith(('q07','q25','q32','q44','q60','q90','q112')):
            samples.append((r['source'], method[i], len(region), region[:160]))
    print(f"TIME={time.time()-t0:.1f}s  BLEED(remaining)={bleed}/{len(sel)}")
    for src, m, ln, smp in samples:
        print(f"  [{src}] {m} len={ln}\n     {smp!r}")

if __name__ == "__main__":
    main()
