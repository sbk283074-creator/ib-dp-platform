#!/usr/bin/env python3
"""
CS past-paper gap extractor (text-layer, pypdfium2).

Fills the CS 真题 NOT yet in the DB:
  * p1  -> old Paper 1  (2000 Nov .. 2015)            [DB already has 2016..2025]
  * p2  -> old Paper 2  (2000 Nov .. 2015) + 2021 + 2022 gap years
  * p3  -> ENTIRE Paper 3 (case-study paper; DB has 0 rows)

Reuses the proven Session-7 logic from extract_cs_p1.py, generalized per paper type,
with a hardened markscheme anchor (handles the "General marking instructions 1.
Follow the markscheme..." preamble that appears before the real answers in Paper 3
markschemes).

Per-question: stores cleaned text AND a tightly-cropped page-span JPG for both
question_image and answer_image (Rule #5). Idempotent stable ids; the companion
Node importer DELETE+INSERTs per source so re-runs are safe.

Usage:
  python extract_cs_missing.py p1
  python extract_cs_missing.py p2
  python extract_cs_missing.py p3
"""
import pypdfium2 as pdfium, os, re, json, sys

ROOT   = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform"
SRC    = "/Users/lucas.ma/Downloads/dp learning/Computer Science-HL-Past Papers&Mark Schemes(1999.05~2025.05)"
FIG    = os.path.join(ROOT, "backend/public/figures")
MANIFEST = {
    "p1": os.path.join(ROOT, "backend/data/cs_p1_old_manifest.json"),
    "p2": os.path.join(ROOT, "backend/data/cs_p2_old_manifest.json"),
    "p3": os.path.join(ROOT, "backend/data/cs_p3_manifest.json"),
}
PT = {
    "p1": ("Paper 1", "CS_HL_P1", "cs_hl_p1"),
    "p2": ("Paper 2", "CS_HL_P2", "cs_hl_p2"),
    "p3": ("Paper 3", "CS_HL_P3", "cs_hl_p3"),
}

DPI = 150
SCALE = DPI / 72.0
PAD_PX = 10

QP_NUMRE = re.compile(r'(?m)^\s*(\d+)\.(?!\d)\s')
# CS marks appear as bare "[2]" (modern) OR "[2 marks]" / "[2 mark]" (older papers).
MARKRE   = re.compile(r'\[\s*(\d+)\s*(?:mark|marks)?\s*\]')
AWARDRE  = re.compile(r'Award\s*\[\s*(\d+)\s*max', re.I)

def ms_marks(span):
    vals = [int(x) for x in AWARDRE.findall(span)]
    return sum(vals) if vals else None

# ---------------------------------------------------------------------------
def load(path):
    d = pdfium.PdfDocument(path)
    pages = [d[i].get_textpage().get_text_range() for i in range(len(d))]
    full = "\n".join(pages)
    return d, pages, full

def page_of(pos, off):
    for i in range(len(off) - 1):
        if off[i] <= pos < off[i + 1]:
            return i
    return len(off) - 2

def clean(text):
    out = []
    for line in text.splitlines():
        s = line.strip()
        if re.match(r'^–\s*\d+\s*–', s):          continue
        if re.match(r'^\d{4}–\d{4}$', s):          continue
        if s in ('Computer science', 'Higher level', 'Paper 1', 'Paper 2', 'Paper 3',
                 'Instructions to candidates'):
            continue
        # exam code headers like M05/5/COMSC/HP1/ENG/TZ0/XX/M+
        if re.search(r'/COMSC/|/ENG/|TZ[0-3]|/HP[123]/', s):
            continue
        out.append(line)
    return "\n".join(out)

def qp_marks(span):
    lines = span.splitlines()
    pure = []
    for line in lines:
        bs = list(MARKRE.finditer(line))
        pure.append(len(bs) == 1 and line.strip() == bs[0].group(0) if bs else False)
    total = 0
    for li, line in enumerate(lines):
        bs = list(MARKRE.finditer(line))
        if len(bs) != 1:
            continue
        m = bs[0]; s = m.start()
        if s > 0 and line[s - 1].isalnum():
            continue
        if line.strip() == m.group(0):
            if (li > 0 and pure[li - 1]) or (li < len(lines) - 1 and pure[li + 1]):
                continue
        else:
            if line[m.end():].strip() != '':
                continue
        before = line[:s].rstrip().split()[-1] if line[:s].strip() else ''
        if before.lower() in ('figure', 'fig'):
            continue
        if before and before.isupper() and '_' in before:
            continue
        total += int(m.group(1))
    return total

# ---------------------------------------------------------------------------
def _is_degenerate_box(box):
    if box is None or len(box) < 4:
        return True
    x0, y0, x1, y1 = box
    return (x1 - x0) < 0.5 or (y1 - y0) < 0.5

def crop_box(doc, pi, start_abs, end_abs, off):
    page = doc[pi]
    pw, ph = page.get_size()
    tp = page.get_textpage()
    n = tp.count_chars()
    s_idx = max(0, min(n - 1, start_abs - off[pi]))
    e_idx = max(0, min(n - 1, end_abs - off[pi]))
    while s_idx < n and _is_degenerate_box(tp.get_charbox(s_idx)):
        s_idx += 1
    while e_idx > s_idx and _is_degenerate_box(tp.get_charbox(e_idx)):
        e_idx -= 1
    if s_idx >= n or e_idx < s_idx:
        return 0.0, ph, ph
    top_threshold = 0.92 * ph
    bot_threshold = 0.08 * ph
    top_y, bot_y = None, None
    for i in range(s_idx, e_idx + 1):
        cb = tp.get_charbox(i)
        if cb is None:
            continue
        if (cb[2] - cb[0]) < 0.5 or (cb[3] - cb[1]) < 0.5:
            continue
        y0, y1 = cb[1], cb[3]
        if y1 > top_threshold or y0 < bot_threshold:
            continue
        if top_y is None or y1 > top_y:
            top_y = y1
        if bot_y is None or y0 < bot_y:
            bot_y = y0
    if top_y is None or bot_y is None:
        sb = tp.get_charbox(s_idx); eb = tp.get_charbox(e_idx)
        return sb[3], eb[1], ph
    return top_y, bot_y, ph

def render_crop(doc, pi, top_pt, bot_pt, ph, relp):
    outp = os.path.join(FIG, relp)
    if os.path.exists(outp):
        return relp
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    pil = doc[pi].render(scale=SCALE).to_pil()
    W, H = pil.size
    top_px = int(round(H - top_pt * SCALE)) - PAD_PX
    bot_px = int(round(H - bot_pt * SCALE)) + PAD_PX
    top_px = max(0, min(H, top_px)); bot_px = max(0, min(H, bot_px))
    if bot_px <= top_px + 4:
        crop = pil
    else:
        crop = pil.crop((0, top_px, W, bot_px))
    crop.save(outp, "JPEG", quality=85)
    return relp

def question_images(doc, qps, qpe, qst, qend, off, rel, n):
    imgs = []
    for pi in range(qps, qpe + 1):
        if pi == qps and pi == qpe:
            start_abs, end_abs = qst, qend - 1
        elif pi == qps:
            start_abs, end_abs = qst, off[pi + 1] - 1
        elif pi == qpe:
            start_abs, end_abs = off[pi], qend - 1
        else:
            start_abs, end_abs = off[pi], off[pi + 1] - 1
        page_text = doc[pi].get_textpage().get_text_range()
        rel_start = max(0, start_abs - off[pi]); rel_end = min(len(page_text), end_abs - off[pi])
        if rel_end <= rel_start or not _page_has_q_content(page_text[rel_start:rel_end], n):
            continue
        top_pt, bot_pt, ph = crop_box(doc, pi, start_abs, end_abs, off)
        relp = f"{rel}/q{n:02d}_p{pi+1}.jpg"
        imgs.append(render_crop(doc, pi, top_pt, bot_pt, ph, relp))
    return imgs

def answer_images(doc, mps, mpe, mst, mend, off, rel, n):
    imgs = []
    for pi in range(mps, mpe + 1):
        if pi == mps and pi == mpe:
            start_abs, end_abs = mst, mend - 1
        elif pi == mps:
            start_abs, end_abs = mst, off[pi + 1] - 1
        elif pi == mpe:
            start_abs, end_abs = off[pi], mend - 1
        else:
            start_abs, end_abs = off[pi], off[pi + 1] - 1
        page_text = doc[pi].get_textpage().get_text_range()
        rel_start = max(0, start_abs - off[pi]); rel_end = min(len(page_text), end_abs - off[pi])
        if rel_end <= rel_start or not _page_has_q_content(page_text[rel_start:rel_end], n):
            continue
        top_pt, bot_pt, ph = crop_box(doc, pi, start_abs, end_abs, off)
        relp = f"{rel}/a{n:02d}_p{pi+1}.jpg"
        imgs.append(render_crop(doc, pi, top_pt, bot_pt, ph, relp))
    return imgs

_PAGE_HEADER  = re.compile(r'–\s*\d+\s*–')
_PAGE_CODE    = re.compile(r'\b\d{4}[–\-]\d{4}\b')

def _strip_page_artifacts(line):
    s = line.strip()
    s = _PAGE_HEADER.sub(' ', s)
    s = _PAGE_CODE.sub(' ', s)
    s = re.sub(r'\bturn over\b',  ' ', s, flags=re.I)
    s = re.sub(r'\bend of paper\b', ' ', s, flags=re.I)
    s = re.sub(r'\(\s*option\s+[a-d]\s*continued\s*\)', ' ', s, flags=re.I)
    s = re.sub(r'\banswer\s+all\s+questions\b\.?', ' ', s, flags=re.I)
    s = re.sub(r'\bsection\s+[ab]\b', ' ', s, flags=re.I)
    s = re.sub(r'\bcomputer\s+science\b', ' ', s, flags=re.I)
    s = re.sub(r'\b(?:higher|standard)\s+level\b', ' ', s, flags=re.I)
    s = re.sub(r'\bpaper\s+\d+\b', ' ', s, flags=re.I)
    s = re.sub(r'\b(end of option [a-d]|continued)\b\.?', ' ', s, flags=re.I)
    return s.strip()

def _page_has_q_content(snippet, n):
    for ln in snippet.splitlines():
        if _strip_page_artifacts(ln):
            return True
    return False

# ---------------------------------------------------------------------------
def qp_starts(qfull):
    matches = sorted(QP_NUMRE.finditer(qfull), key=lambda m: m.start())
    qstarts = {}
    expected = 1
    for m in matches:
        if int(m.group(1)) == expected:
            qstarts[expected] = m.start()
            expected += 1
    return qstarts

def ms_starts(mfull, N):
    """Anchor at the last pre-answer header, then walk 1..N forward.

    Hardened vs. the original: also anchors on 'Mark allocation' / 'Maximum
    mark' / 'Total N marks' (these sit right before the answers in Paper 3
    markschemes), and — in the no-anchor fallback — skips any leading '1.'
    that is a marking-instruction ('Follow the markscheme'), not a real answer.
    """
    anchors = ["Maximum total", "Maximum mark", "Section A",
               "Mark allocation", "Mark Allocation",
               "Total 30 marks", "Total 25 marks", "Total 20 marks",
               "Total 15 marks", "Total 10 marks"]
    anchor_base = -1
    for kw in anchors:
        p = mfull.find(kw)
        if p > anchor_base:
            anchor_base = p
    region_start = anchor_base + 1 if anchor_base >= 0 else 0
    region = mfull[region_start:]

    # candidate "1." positions inside the region
    cands = [m.start() + region_start for m in re.finditer(r'(?m)^\s*1\.', region)]
    if not cands:
        return {}
    # pick the first "1." that is NOT a marking instruction
    base = None
    for c in cands:
        line = mfull[c:c + 60]
        if re.search(r'follow\s+the\s+markscheme', line, re.I):
            continue
        base = c
        break
    if base is None:
        base = cands[0]

    prev_end = base
    mstarts = {1: base}
    expected = 2
    while expected <= N:
        pat = re.compile(r'(?m)^\s*' + str(expected) + r'(?:\.|\s)(?!\d)')
        mm = pat.search(mfull, prev_end)
        if not mm:
            break
        mstarts[expected] = mm.start()
        prev_end = mm.end()
        expected += 1
    return mstarts

# ---------------------------------------------------------------------------
def process(qp_path, ms_path, slug, pretty, ptkey):
    paper_type, prefix, figrel = PT[ptkey]
    qd, qpages, qfull = load(qp_path)
    md, mpages, mfull = load(ms_path)

    qstarts = qp_starts(qfull)
    N = len(qstarts)
    if N == 0:
        qd.close(); md.close()
        return [], {"slug": slug, "N": 0, "err": "no QP questions found"}

    qoff = [0]
    for t in qpages: qoff.append(qoff[-1] + len(t) + 1)
    moff = [0]
    for t in mpages: moff.append(moff[-1] + len(t) + 1)

    secB = -1
    for m in re.finditer(r'Section B', qfull):
        if m.start() > qstarts[1]:
            secB = max(secB, m.start())
    mstarts = ms_starts(mfull, N)
    if not mstarts:
        # Markscheme uses an incompatible layout (e.g. repeats the question
        # prompt instead of numbering answers) -> cannot anchor answers
        # reliably. Skip per standing Rule #8 rather than ship empty answers.
        qd.close(); md.close()
        return [], {"slug": slug, "N": N, "skipped": "no anchorable answer starts in markscheme"}

    keys = sorted(qstarts)
    records = []
    warns = []
    seen_text = {}
    prev_qst = -1
    qp_total = 0
    for idx, n in enumerate(keys):
        qst = qstarts[n]
        qend = qstarts[keys[idx + 1]] if idx + 1 < len(keys) else len(qfull)
        if qst <= prev_qst:
            warns.append(f"Q{n}: non-increasing span start")
        prev_qst = qst
        qtext = clean(qfull[qst:qend])
        if not qtext.strip():
            warns.append(f"Q{n}: EMPTY text")
        if qtext in seen_text:
            warns.append(f"Q{n}: DUPLICATE text with Q{seen_text[qtext]}")
        else:
            seen_text[qtext] = n
        section = "Section B" if (secB > 0 and qst > secB) else "Section A"
        qp_m = qp_marks(qfull[qst:qend])
        qp_total += qp_m

        qps = page_of(qst, qoff)
        qpe = page_of(qend - 1, qoff)
        mst = mstarts.get(n)
        if mst is None:
            atext = ""; a_imgs = []
            marks = qp_m
            warns.append(f"Q{n}: no markscheme start")
        else:
            nxt = [k for k in mstarts if k > n]
            mend = mstarts[min(nxt)] if nxt else len(mfull)
            mps = page_of(mst, moff)
            mpe = page_of(mend - 1, moff)
            atext = clean(mfull[mst:mend])
            a_imgs = answer_images(md, mps, mpe, mst, mend, moff, f"{figrel}/{slug}", n)
            ms_m = ms_marks(atext)
            marks = qp_m or ms_m or 0
        if marks == 0:
            warns.append(f"Q{n}: 0 marks")
        q_imgs = question_images(qd, qps, qpe, qst, qend, qoff, f"{figrel}/{slug}", n)
        if not q_imgs:
            warns.append(f"Q{n}: no question image")
        if not a_imgs:
            warns.append(f"Q{n}: no answer image")

        records.append({
            "id": f"{prefix}_{slug}_q{n:02d}",
            "subject": "Computer Science", "level": "HL", "topic": "CS HL",
            "subtopic": None, "paper_type": paper_type,
            "command_term": None, "marks": int(marks), "difficulty": None,
            "question": qtext, "figure": None, "answer": atext, "explanation": None,
            "source": f"CS HL {paper_type} · {pretty}", "tags": [section],
            "authored_by": "ib", "knowledge_point_ids": [],
            "answer_figure": None, "question_image": ",".join(q_imgs),
            "answer_image": ",".join(a_imgs), "figure_image": None,
            "book_id": None, "source_type": "paper", "category": "past",
            "review_status": "new",
        })

    qd.close(); md.close()
    sec_a = sum(1 for r in records if r["tags"] == ["Section A"])
    sec_b = N - sec_a
    mtot = sum(r["marks"] for r in records)
    mm = [r["marks"] for r in records] or [0]
    report = {"slug": slug, "N": N, "secA": sec_a, "secB": sec_b,
              "marks_total": mtot, "qp_total": qp_total,
              "marks_min": min(mm), "marks_max": max(mm), "warns": warns}
    return records, report

# ---------------------------------------------------------------------------
def in_scope(y, mo, mode):
    if mode == "p1":
        return y <= 2015
    if mode == "p2":
        return y <= 2015 or y == 2021 or y == 2022
    if mode == "p3":
        return True
    return False

# Papers whose markscheme has an incompatible / mis-sequenced layout that cannot
# be reliably segmented (answer blocks out of order, e.g. Q3's answer placed
# before the SECTION A Total / 1,2 numbering). Per standing Rule #8 these are
# skipped entirely rather than shipped with broken/empty answers.
SKIP = {("p1", "2013Nov")}

def scan_papers(mode):
    papers = []
    np_ = {"p1": "1", "p2": "2", "p3": "3"}[mode]
    for session in sorted(os.listdir(SRC)):
        sdir = os.path.join(SRC, session)
        if not os.path.isdir(sdir):
            continue
        ym = None
        m = re.match(r'(\d{4})\.(\d{2})$', session)
        if m:
            y, mo = int(m.group(1)), int(m.group(2))
            ym = (y, "May" if mo == 5 else "Nov" if mo == 11 else None)
        else:
            m = re.match(r'(\d{4}) (May|November) Examination Session', session)
            if m:
                ym = (int(m.group(1)), m.group(2))
        if not ym or ym[1] is None:
            continue
        y, mon = ym
        if not in_scope(y, mon, mode):
            continue
        for fn in os.listdir(sdir):
            low = fn.lower()
            if "markscheme" in low or "spanish" in low or "french" in low:
                continue
            if mode == "p3" and "case_study" in low:
                continue
            if not (f"paper_{np_}" in low and "hl" in low and fn.endswith(".pdf")):
                continue
            if mode != "p3" and "case_study" in low:
                continue
            qp = os.path.join(sdir, fn)
            ms = os.path.join(sdir, fn[:-4] + "_markscheme.pdf")
            if not os.path.exists(ms):
                continue
            tz = re.search(r'TZ(\d)', fn)
            slug = f"{y}{mon[:3]}" + (f"_TZ{tz.group(1)}" if tz else "")
            pretty = f"{y} {mon}" + (f" TZ{tz.group(1)}" if tz else "")
            if (mode, slug) in SKIP:
                continue
            papers.append((qp, ms, slug, pretty))
    papers.sort(key=lambda p: (p[3], p[2]))
    return papers

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "p3"
    if mode not in PT:
        print("usage: extract_cs_missing.py [p1|p2|p3]"); raise SystemExit(1)
    os.makedirs(FIG, exist_ok=True)
    papers = scan_papers(mode)
    print(f"[{mode}] Discovered {len(papers)} CS HL {PT[mode][0]} papers in scope:")
    for p in papers:
        print("  ", p[2], "->", p[3])
    print()
    all_recs = []
    grand_warns = 0
    tot_q = 0
    skipped = 0
    for qp, ms, slug, pretty in papers:
        recs, rep = process(qp, ms, slug, pretty, mode)
        if "warns" not in rep:
            skipped += 1
            reason = rep.get("skipped") or rep.get("err") or "no data"
            print(f"  {slug:16s} SKIPPED: {reason}")
            continue
        all_recs.extend(recs)
        tot_q += rep["N"]
        grand_warns += len(rep["warns"])
        flag = "  <-- CHECK" if rep["warns"] else ""
        print(f"  {slug:16s} N={rep['N']:2d}  A={rep.get('secA',0):2d} B={rep.get('secB',0):2d}"
              f"  ms_tot={rep.get('marks_total',0):3d} qp_tot={rep.get('qp_total',0):3d}"
              f"  min={rep.get('marks_min',0)} max={rep.get('marks_max',0)}{flag}")
        for w in rep["warns"][:6]:
            print("       !", w)
    with open(MANIFEST[mode], "w", encoding="utf-8") as f:
        json.dump(all_recs, f, ensure_ascii=False, indent=1)
    print(f"\nTOTAL questions: {len(all_recs)}  ({tot_q} per-paper sum)")
    print(f"SKIPPED papers:  {skipped}")
    print(f"TOTAL warnings:  {grand_warns}")
    print(f"Manifest -> {MANIFEST[mode]}")

if __name__ == "__main__":
    main()
