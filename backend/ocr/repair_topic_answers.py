#!/usr/bin/env python3
"""Repair topic-question ANSWERS only (questions untouched).

For each manifest question (in order) we locate its markscheme block:
  * Confident: fuzzy-local difflib match of the alphanumeric skeleton against a
    forward window in the clean markscheme (verified correct pairing).
  * Gap-fill: questions the locator can't match (heavily OCR-garbled skeletons)
    are assigned by linear interpolation between the neighbouring confident
    positions, so every region is monotonic, non-empty and in order.
Answer region = [start_i, start_{i+1}), trimmed at the first "Examiners report"
so examiner commentary is excluded. Answer images are re-rendered.

Usage: python3 repair_topic_answers.py <topic> <HL-paper1|HL-paper2|HL-paper3> [--apply]
Writes math_topic_manifest_repaired.json (or applies in place with --apply) plus
prints before/after stats.
"""
import os, re, sys, json, difflib, bisect, time
import pypdfium2 as pdfium
from PIL import Image

SRC_ROOT = "/Users/lucas.ma/Downloads/dp learning/IB数学AA  HL 分章练习/IB数学AA-Mathmatics HL IB Question Bank"
FIG_ROOT  = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/public/figures"
MANIFEST  = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/data/math_topic_manifest.json"
SCALE = 2.0
TITLE_LEAD = re.compile(r"^\s*hl\.?\s*p\w*r\s*\d+\s*p?\s*[\r\n]*", re.I)
CMD_WORD = re.compile(r"\b(find|show|prove|consider|let|given|express|write|calculate|determine|solve|state|derive|sketch|hence|using|obtain|deduce|expand|simplify|factorise|the)\b", re.I)

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

def anorm_map(s):
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

def build_ms(ms_pdf):
    doc = pdfium.PdfDocument(ms_pdf)
    raw_pages = [doc[i].get_textpage().get_text_range() for i in range(len(doc))]
    raw = "\n".join(raw_pages)
    hay, to_raw = anorm_map(raw)
    # page char starts (same convention as extract_math_topic.build_markscheme_index)
    page_char_starts = []
    cursor = 0
    for t in raw_pages:
        page_char_starts.append(cursor)
        cursor += len(t) + 1
    def pos_to_page(p):
        pi = 0
        for i, st in enumerate(page_char_starts):
            if st > p: break
            pi = i
        return pi
    # per-page char y-centres (lazily cached)
    page_ys = {}
    def get_ys(pi):
        if pi in page_ys:
            return page_ys[pi]
        tp = doc[pi].get_textpage()
        n = tp.count_chars()
        ys = [((cb[1]+cb[3])/2) if cb else 0 for cb in (tp.get_charbox(j) for j in range(n))]
        page_ys[pi] = ys
        return ys
    # strong prompt anchors (subpart + [N] + question-like text)
    anchors = []
    for m in re.finditer(r"(?m)^\s*[a-z]\.\s.*?\[\s*\d+\s*(?:marks?)?\s*\]", raw):
        line = raw[m.start():m.start()+200].split("\n")[0]
        after = re.sub(r"^\s*[a-z]\.\s", "", line)
        after = re.sub(r"\[\s*\d+\s*(?:marks?)?\s*\]", "", after)
        if CMD_WORD.search(after) or len(after.strip()) > 25:
            anchors.append(m.start())
    return doc, raw, hay, to_raw, page_char_starts, pos_to_page, get_ys, anchors

def locate(needle, hay, to_raw, start, window=14000, step=8):
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
            bp = start + pos
            best_pos = to_raw[bp] if bp < len(to_raw) else bp
        pos += step
    return best_pos, best_score

def render_answer(doc, raw_start, raw_end, page_char_starts, pos_to_page, get_ys, out_rel_base):
    """Render markscheme pages covering [raw_start, raw_end) to JPEGs. Returns list of rel paths."""
    paths = []
    if raw_end <= raw_start:
        return paths
    pi0 = pos_to_page(raw_start)
    pi1 = pos_to_page(raw_end - 1)
    for pi in range(pi0, pi1 + 1):
        ls = max(0, raw_start - page_char_starts[pi])
        le = min(len(doc[pi].get_textpage().get_text_range()), raw_end - page_char_starts[pi])
        if le <= ls:
            continue
        ys = get_ys(pi)
        if ls >= len(ys) or le > len(ys):
            continue
        sub = ys[ls:le]
        y_top = min(sub) - 12
        y_bot = max(sub) + 12
        img = doc[pi].render(scale=SCALE).to_pil()
        H = img.height
        py_top = max(0, H - int(y_bot * SCALE) - 6)
        py_bot = min(H, H - int(y_top * SCALE) + 6)
        crop = img.crop((0, py_top, img.width, py_bot)).convert("RGB")
        rel = out_rel_base.format(pi=pi + 1)
        out = os.path.join(FIG_ROOT, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        crop.save(out, "JPEG", quality=85)
        paths.append(rel)
    return paths

def repair(tn, paper, apply=False):
    mspdf = os.path.join(SRC_ROOT, f"Topic {tn}", "markscheme-" + paper + ".pdf")
    if not os.path.exists(mspdf):
        print(f"SKIP Topic {tn} {paper}: no markscheme pdf"); return
    recs = json.load(open(MANIFEST))
    sel = [r for r in recs if r['topic'] == f"Topic {tn}" and r['paper_type'] == paper]
    if not sel:
        print(f"SKIP Topic {tn} {paper}: no manifest records"); return
    doc, raw, hay, to_raw, pcs, p2p, get_ys, anchors = build_ms(mspdf)
    n = len(sel)
    avg = len(raw) // max(1, n)

    # Pass 1: confident locator
    starts = [None] * n
    scores = [0.0] * n
    prev_hay = 0
    for i, r in enumerate(sel):
        sk = skeleton(r['question_text'])
        best = (-1, 0.0)
        for ndl in (sk, sk[-90:]):
            if len(ndl) < 12: continue
            p, s = locate(ndl, hay, to_raw, prev_hay, window=14000, step=8)
            if s > best[1]:
                best = (p, s)
        pos, sc = best
        if pos >= 0 and sc >= 0.30:
            starts[i] = pos; scores[i] = sc
            prev_hay = bisect.bisect_left(to_raw, pos) + 1
        else:
            prev_hay = bisect.bisect_left(to_raw, (starts[i-1] if i and starts[i-1] else 0)) + 1

    # Pass 2: interpolate gaps between confident starts (monotonic, non-empty)
    def fill():
        # find first known
        known = [i for i in range(n) if starts[i] is not None]
        if not known:
            for i in range(n):
                starts[i] = i * avg
            return
        # before first known
        f0 = known[0]
        base = starts[f0] if f0 == 0 else max(0, starts[f0] - f0 * avg)
        for i in range(f0):
            starts[i] = base + i * ((starts[f0] - base) // max(1, f0)) if f0 else i * avg
        # between known
        for a, b in zip(known, known[1:]):
            if b == a + 1: continue
            span = (starts[b] - starts[a]) / (b - a)
            for k in range(a + 1, b):
                starts[k] = int(starts[a] + span * (k - a))
        # after last known
        la = known[-1]
        for i in range(la + 1, n):
            starts[i] = starts[la] + (i - la) * avg
    fill()

    # Build repaired records
    slug = paper.replace("-", "_").lower()
    tdir = os.path.join(FIG_ROOT, f"Topic_{tn}", slug)
    new_answers = {}
    before_bleed = 0
    after_bleed = 0
    empties = 0
    changed = 0
    fixed = 0
    regress = 0
    for i, r in enumerate(sel):
        s = starts[i]
        e = starts[i + 1] if i + 1 < n else len(raw)
        if e <= s:
            e = s + max(200, avg // 2)
        region = raw[s:e]
        er = region.find("Examiners report")
        if er >= 0:
            region = region[:er]
        ans = region.strip()
        cur = r.get('answer_text') or ""
        cur_bleeds = "Examiners report" in cur
        new_clean = "Examiners report" not in ans
        if cur_bleeds:
            before_bleed += 1
        if new_clean is False:
            after_bleed += 1
        if not ans:
            empties += 1
        # Decision: only replace a BROKEN (bleeding) current answer, and only when
        # the re-pair is confident (score>=0.6) and clean. Clean current answers are
        # always kept (avoid regressions the user explicitly warned against).
        use_new = bool(new_clean and len(ans) >= 40 and scores[i] >= 0.6 and cur_bleeds)
        imgs = []
        if use_new:
            # source ends with _qNN ; build a{i}_p{k}
            qnum = r['source'].rsplit('_q', 1)[-1]
            rel_base = f"Topic_{tn}/{slug}/a{qnum}_p{{pi}}.jpg"
            imgs = render_answer(doc, s, e, pcs, p2p, get_ys, rel_base)
            changed += 1; fixed += 1
        elif (not cur_bleeds) and new_clean and scores[i] >= 0.6 and len(ans) >= 40:
            regress += 1  # would have changed a clean current answer -> regression risk, NOT applied
        new_answers[r['source']] = (ans, imgs, scores[i], use_new)

    # Apply or save
    if apply:
        for r in recs:
            if r['source'] in new_answers:
                ans, imgs, _, use_new = new_answers[r['source']]
                if use_new:
                    r['answer_text'] = strip_title(ans)
                    r['answer_image'] = ",".join(imgs)
        json.dump(recs, open(MANIFEST, 'w'), ensure_ascii=False, indent=2)
        print(f"APPLIED to {MANIFEST}: {changed} answers rewritten")
    else:
        out = MANIFEST.replace(".json", "_repaired.json")
        json.dump({r['source']: {'answer_text': strip_title(new_answers[r['source']][0]),
                                 'answer_image': ",".join(new_answers[r['source']][1]),
                                 'score': new_answers[r['source']][2],
                                 'use_new': new_answers[r['source']][3]}
                   for r in sel}, open(out, 'w'), ensure_ascii=False, indent=2)
        print(f"Wrote {out}")
    print(f"Topic {tn} {paper}: n={n} before_bleed={before_bleed} changed={changed} "
          f"fixed={fixed} regress_risk={regress} after_bleed={after_bleed} empties={empties}")

if __name__ == "__main__":
    apply = "--apply" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    t0 = time.time()
    if args and args[0] == "all":
        tot_fixed = tot_regress = tot_bleed = tot_empty = 0
        for tn in range(1, 11):
            for paper in ["HL-paper1", "HL-paper2", "HL-paper3"]:
                repair(tn, paper, apply=apply)
        print(f"[ALL] done")
    else:
        tn = int(args[0]) if args else 1
        paper = args[1] if len(args) > 1 else "HL-paper1"
        repair(tn, paper, apply=apply)
    print(f"elapsed {time.time()-t0:.1f}s")
