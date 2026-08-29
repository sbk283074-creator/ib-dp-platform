#!/usr/bin/env python3
"""
Session 8 extractor — Computer Science HL Paper 2 (past 10 yrs, 2016May..2025Nov).
Text-layer extraction (pypdfium2). Produces a JSON manifest of question records
(question text + tightly-cropped question_image, answer text + tightly-cropped
answer_image) and writes the JPGs to backend/public/figures/cs_hl_p2/<slug>/.

CORRECTNESS CONTRACT (same as the proven CS P1 extractor):
  * Each top-level question gets a DISTINCT, NON-OVERLAPPING text span
    [N. start -> next N. start] via the consecutive 1..N walker.
  * Each question's image is cropped to its OWN vertical band on the page
    (via get_charbox top/bottom), so no question ever inherits a whole section.
  * Every question is tagged with the OPTION it belongs to (P2 is option-based,
    not Section A/B) by the last "Option X — Name" header before the question.
  * Verification guards run per paper: strictly-increasing spans, no duplicate
    question text, sane marks, >=1 image per record, every question has an option.

Idempotent: stable ids. The companion Node importer does DELETE+INSERT per paper.
No DB writes happen here — only files + manifest.
"""
import pypdfium2 as pdfium, os, re, json

ROOT   = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform"
SRC    = "/Users/lucas.ma/Downloads/dp learning/Computer Science-HL-Past Papers&Mark Schemes(1999.05~2025.05)"
FIG    = os.path.join(ROOT, "backend/public/figures")
MANIFEST = os.path.join(ROOT, "backend/data/cs_p2_manifest.json")

DPI = 150
SCALE = DPI / 72.0
PAD_PX = 10  # breathing room around each crop

# Question-paper top-level question start: "N. " at line start, not "N.M" decimals.
QP_NUMRE = re.compile(r'(?m)^\s*(\d+)\.(?!\d)\s')
# Marks: bare [N] (CS uses "[2]" not "[Maximum mark: N]").
MARKRE   = re.compile(r'\[\s*(\d+)\s*\]')

# Option header: "Option A — Databases", "Option B — Modelling and simulation", ...
OPT_HEAD = re.compile(r'Option\s+([A-D])\s*[—\-–]\s*([^\n]+)', re.I)

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
        if re.match(r'^–\s*\d+\s*–', s):          continue  # footer page number
        if re.match(r'^\d{4}–\d{4}$', s):          continue  # doc code line
        if s in ('Computer science', 'Higher level', 'Paper 1', 'Paper 2',
                 'Instructions to candidates'):
            continue
        out.append(line)
    # Trim option-transition noise that leaks into a question's tail/head:
    # standalone "Option X — Name" headers and "End of Option X" markers.
    while out and (OPT_HEAD.match(out[-1].strip()) or
                   re.match(r'^End of Option [A-D]\.?$', out[-1].strip())):
        out.pop()
    while out and (OPT_HEAD.match(out[0].strip()) or
                   re.match(r'^End of Option [A-D]\.?$', out[0].strip())):
        out.pop(0)
    return "\n".join(out)

def qp_marks(span):
    """Sum subpart [M] while ignoring array/matrix/index notation (CS-heavy)."""
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
    """True for charboxes with zero/near-zero width or height — pypdfium2 often
    returns such boxes for `\n`, line-break positions, or accented-glyph holes,
    and they can have a y-coordinate that doesn't reflect the actual line."""
    if box is None or len(box) < 4:
        return True
    x0, y0, x1, y1 = box
    return (x1 - x0) < 0.5 or (y1 - y0) < 0.5

def crop_box(doc, pi, start_abs, end_abs, off):
    """Return (top_pt, bot_pt, page_h_pt) for the question's band on page pi.

    Robust against:
      - pypdfium2 degenerate charboxes (zero-width / zero-height) — skipped.
      - page artifacts (page-number header "– X –", doc code "8824–6904",
        "Turn over" footer) that interleave into the question's char range.
        Chars in the top/bottom ~8% of the page are excluded so the band
        reflects only the question's actual content.
    """
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
        sb = tp.get_charbox(s_idx)
        eb = tp.get_charbox(e_idx)
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
    top_px = max(0, min(H, top_px))
    bot_px = max(0, min(H, bot_px))
    if bot_px <= top_px + 4:          # degenerate -> keep whole page
        crop = pil
    else:
        crop = pil.crop((0, top_px, W, bot_px))
    crop.save(outp, "JPEG", quality=85)
    return relp

def question_images(doc, qps, qpe, qst, qend, off, slug, n):
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
        # Skip pages where this question has no actual content (only page
        # header / footer / whitespace cross the range), to avoid swallowing
        # the next question's content into a near-full-page band.
        page_text = doc[pi].get_textpage().get_text_range()
        rel_start = max(0, start_abs - off[pi])
        rel_end   = min(len(page_text), end_abs - off[pi])
        if rel_end <= rel_start or not _page_has_q_content(page_text[rel_start:rel_end], n):
            continue
        top_pt, bot_pt, ph = crop_box(doc, pi, start_abs, end_abs, off)
        relp = f"cs_hl_p2/{slug}/q{n:02d}_p{pi+1}.jpg"
        imgs.append(render_crop(doc, pi, top_pt, bot_pt, ph, relp))
    return imgs

def answer_images(doc, mps, mpe, mst, mend, off, slug, n):
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
        rel_start = max(0, start_abs - off[pi])
        rel_end   = min(len(page_text), end_abs - off[pi])
        if rel_end <= rel_start or not _page_has_q_content(page_text[rel_start:rel_end], n):
            continue
        top_pt, bot_pt, ph = crop_box(doc, pi, start_abs, end_abs, off)
        relp = f"cs_hl_p2/{slug}/a{n:02d}_p{pi+1}.jpg"
        imgs.append(render_crop(doc, pi, top_pt, bot_pt, ph, relp))
    return imgs

_PAGE_HEADER  = re.compile(r'–\s*\d+\s*–')
_PAGE_CODE    = re.compile(r'\b\d{4}[–\-]\d{4}\b')

def _strip_page_artifacts(line):
    """Remove page header / doc code / footer tokens from `line`. A line that
    becomes empty after this is just a page artifact."""
    s = line.strip()
    s = _PAGE_HEADER.sub(' ', s)
    s = _PAGE_CODE.sub(' ', s)
    s = re.sub(r'\bturn over\b',  ' ', s, flags=re.I)
    s = re.sub(r'\bend of paper\b', ' ', s, flags=re.I)
    # "(Option A continued)", "End of Option A", "Answer all questions" — also
    # transitional page artifacts, not real question content.
    s = re.sub(r'\(\s*option\s+[a-d]\s*continued\s*\)', ' ', s, flags=re.I)
    s = re.sub(r'\banswer\s+all\s+questions\b\.?', ' ', s, flags=re.I)
    s = re.sub(r'\bsection\s+[ab]\b', ' ', s, flags=re.I)
    s = re.sub(r'\bcomputer\s+science\b', ' ', s, flags=re.I)
    s = re.sub(r'\b(?:higher|standard)\s+level\b', ' ', s, flags=re.I)
    s = re.sub(r'\bpaper\s+\d+\b', ' ', s, flags=re.I)
    s = re.sub(r'\b(end of option [a-d]|continued)\b\.?', ' ', s, flags=re.I)
    return s.strip()

def _page_has_q_content(snippet, n):
    """True if `snippet` (textpage text in this question's range on one page)
    contains real content — anything beyond page header / footer / doc code /
    pure whitespace."""
    for ln in snippet.splitlines():
        if _strip_page_artifacts(ln):
            return True
    return False

# ---------------------------------------------------------------------------
def qp_starts(qfull):
    """Consecutive 1..N walker over top-level question numbers."""
    matches = sorted(QP_NUMRE.finditer(qfull), key=lambda m: m.start())
    qstarts = {}
    expected = 1
    for m in matches:
        if int(m.group(1)) == expected:
            qstarts[expected] = m.start()
            expected += 1
    return qstarts

def parse_options(qfull, qstarts):
    """Map each question number -> 'Option X — Name' using the last option header
    before the question. Filters out page-footer artifacts."""
    heads = []
    for m in OPT_HEAD.finditer(qfull):
        letter = m.group(1).upper()
        name = m.group(2).strip()
        name = re.sub(r'\s+\d+\s*[–-]\s*\d+\s*$', '', name).strip()  # drop " 1 – 4" range
        if '/' in name:            # doc-code footer e.g. "M19/4/COMSC/..."
            continue
        if not re.search(r'[A-Za-z]', name):  # pure "6 – 2223–7012" footer
            continue
        heads.append((m.start(), letter, name))
    heads.sort()
    opt_map = {}
    for n in qstarts:
        pos = qstarts[n]
        chosen = None
        for hpos, letter, name in heads:
            if hpos <= pos:        # keep latest header at or before the question
                chosen = (letter, name)
            else:
                break
        if chosen:
            opt_map[n] = f"Option {chosen[0]} — {chosen[1]}"
    return opt_map

def ms_starts(mfull, N):
    """Anchor at the real question 1 — the first top-level '1.' whose first content
    is a subpart '(a)' (i.e. '1. (a)'), skipping any numbered marking-instructions
    preamble. Then per-number independent forward search."""
    m = re.search(r'(?m)^\s*1\.\s*(?:\(|\n\s*\()', mfull)
    if not m:
        m = re.search(r'(?m)^\s*1\.', mfull)
    if not m:
        return {}
    base = m.start()
    mstarts = {1: base}
    prev_end = m.end()
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
def process(qp_path, ms_path, slug, pretty):
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

    opt_map = parse_options(qfull, qstarts)
    mstarts = ms_starts(mfull, N)

    keys = sorted(qstarts)
    records = []
    warns = []
    seen_text = {}
    prev_qst = -1
    qp_total = 0
    opt_counts = {}
    for idx, n in enumerate(keys):
        qst = qstarts[n]
        qend = qstarts[keys[idx + 1]] if idx + 1 < len(keys) else len(qfull)
        if qst <= prev_qst:
            warns.append(f"Q{n}: non-increasing span start (real overlap)")
        prev_qst = qst
        qtext = clean(qfull[qst:qend])
        if not qtext.strip():
            warns.append(f"Q{n}: EMPTY text")
        if qtext in seen_text:
            warns.append(f"Q{n}: DUPLICATE text with Q{seen_text[qtext]}")
        else:
            seen_text[qtext] = n
        option = opt_map.get(n)
        if not option:
            warns.append(f"Q{n}: NO option tag")
            option = "Unknown"
        opt_counts[option] = opt_counts.get(option, 0) + 1
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
            mend = mstarts[keys[idx + 1]] if idx + 1 < len(keys) else len(mfull)
            mps = page_of(mst, moff)
            mpe = page_of(mend - 1, moff)
            atext = clean(mfull[mst:mend])
            a_imgs = answer_images(md, mps, mpe, mst, mend, moff, slug, n)
            marks = qp_m
        if marks == 0:
            warns.append(f"Q{n}: 0 marks")
        q_imgs = question_images(qd, qps, qpe, qst, qend, qoff, slug, n)
        if not q_imgs:
            warns.append(f"Q{n}: no question image")
        if not a_imgs:
            warns.append(f"Q{n}: no answer image")

        records.append({
            "id": f"CS_HL_P2_{slug}_q{n:02d}",
            "subject": "Computer Science", "level": "HL", "topic": "CS HL",
            "subtopic": None, "paper_type": "Paper 2",
            "command_term": None, "marks": int(marks), "difficulty": None,
            "question": qtext, "figure": None, "answer": atext, "explanation": None,
            "source": f"CS HL P2 · {pretty}", "tags": [option],
            "authored_by": "ib", "knowledge_point_ids": [],
            "answer_figure": None, "question_image": ",".join(q_imgs),
            "answer_image": ",".join(a_imgs), "figure_image": None,
            "book_id": None, "source_type": "paper", "category": "past",
            "review_status": "new",
        })

    qd.close(); md.close()
    mtot = sum(r["marks"] for r in records)
    mm = [r["marks"] for r in records] or [0]
    report = {
        "slug": slug, "N": N, "opt_counts": opt_counts,
        "marks_total": mtot, "qp_total": qp_total, "marks_min": min(mm),
        "marks_max": max(mm), "warns": warns,
    }
    return records, report

# ---------------------------------------------------------------------------
def scan_papers():
    papers = []
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
        key = (y, 5 if mon == "May" else 11)
        if key < (2016, 5) or key > (2025, 11):
            continue
        for fn in os.listdir(sdir):
            if "markscheme" in fn or "Spanish" in fn or "French" in fn or "case_study" in fn:
                continue
            if not (("paper_2" in fn) and ("HL" in fn) and fn.endswith(".pdf")):
                continue
            qp = os.path.join(sdir, fn)
            ms = os.path.join(sdir, fn[:-4] + "_markscheme.pdf")
            if not os.path.exists(ms):
                continue
            tz = re.search(r'TZ(\d)', fn)
            slug = f"{y}{mon[:3]}" + (f"_TZ{tz.group(1)}" if tz else "")
            pretty = f"{y} {mon}" + (f" TZ{tz.group(1)}" if tz else "")
            papers.append((qp, ms, slug, pretty))
    papers.sort(key=lambda p: (p[3], p[2]))
    return papers

# ---------------------------------------------------------------------------
def main():
    os.makedirs(FIG, exist_ok=True)
    papers = scan_papers()
    print(f"Discovered {len(papers)} CS HL P2 papers (past 10 yrs):")
    for p in papers:
        print("  ", p[2], "->", p[3])
    print()
    all_recs = []
    grand_warns = 0
    tot_q = 0
    for qp, ms, slug, pretty in papers:
        recs, rep = process(qp, ms, slug, pretty)
        all_recs.extend(recs)
        tot_q += rep["N"]
        grand_warns += len(rep["warns"])
        optstr = " ".join(f"{k.split('—')[0].strip()}={v}" for k, v in sorted(rep["opt_counts"].items()))
        flag = "  <-- CHECK" if rep["warns"] else ""
        print(f"  {slug:16s} N={rep['N']:2d}  [{optstr}]"
              f"  ms_tot={rep['marks_total']:3d} qp_tot={rep['qp_total']:3d}"
              f"  min={rep['marks_min']} max={rep['marks_max']}{flag}")
        for w in rep["warns"]:
            print("       !", w)
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(all_recs, f, ensure_ascii=False, indent=1)
    print(f"\nTOTAL questions: {len(all_recs)}  ({tot_q} per-paper sum)")
    print(f"TOTAL warnings:  {grand_warns}")
    print(f"Manifest -> {MANIFEST}")

if __name__ == "__main__":
    main()
