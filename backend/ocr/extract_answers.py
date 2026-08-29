"""extract_answers.py — populate questions.answer_image from a companion
answer / worked-solution PDF, with careful question<->answer matching.

Matching strategy (Oxford answer book, verified structure):
  * The answer PDF is organised by the TEXTBOOK's PRINTED page number.
    Headers look like "Practice questions – Page 11" or
    "Practice questions – Pages 21–22".  Each following line starts with a
    question number ("6 a. …") at a known text-layer y (screen coords).
  * Extended-response questions live under a dedicated
    "Extended response questions – Pages 700–701" block, with "Question N"
    markers, flowing across several answer-PDF pages.
  * The textbook's book_page is the RAW PDF page.  For Oxford,
    printed = raw - OFFSET (OFFSET default 8; override per book).

For each textbook question we compute its printed page, locate the answer
block for that printed page, and pick the answer sub-crop by the question's
POSITION among the questions sharing that printed page (questions and
answers are both in ascending qnum order on a page, so positional matching
is reliable).  If anything is uncertain we fall back to the whole
answer-page crop for that printed page (still source-accurate, just shows a
few sibling answers on the same page).

Output: JPEGs in public/figures named book_{id}_a_p{printed}_{qnum}.jpg,
and the questions.answer_image column is updated to "/figures/...".

A dry-run mode writes a JSON report instead of touching the DB / disk.
"""
import os, sys, re, json, sqlite3
sys.path.insert(0, os.path.dirname(__file__))
import booklib as B
import pypdfium2 as pdfium

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FIG_DIR = os.path.join(BACKEND_ROOT, 'public', 'figures')
os.makedirs(FIG_DIR, exist_ok=True)
DB = os.path.join(BACKEND_ROOT, 'data', 'app.db')

# Per-book answer matching config (printed-page offset + extended-response flag).
ANSWER_CFG = {
    'PH-OX-2023': dict(offset=8, extended=True),
}

HDR_RE = re.compile(r'Practice questions\s+[–-]\s*Pages?\s*(\d+)(?:\s*[–-]\s*(\d+))?', re.I)
EXT_RE = re.compile(r'Extended Response Questions\s+[–-]\s*Pages?\s*(\d+)', re.I)
QN_RE = re.compile(r'^\s*(\d+)\s+[A-Za-z(]')
QW_RE = re.compile(r'Question\s+(\d+)', re.I)


def build_answer_index(answer_path):
    """Return (practice, ext) where
    practice: {printed_page: [(qnum, ans_pdf_page, y_top), ...]} (qnum order)
    ext:      [(qnum, ans_pdf_page, y_top), ...]  (continuous block)
    """
    apdf = pdfium.PdfDocument(answer_path)
    practice = {}
    ext = []
    cur_page = None          # printed page of the current practice block
    in_ext = False
    n = len(apdf)
    for i in range(n):
        page = apdf[i]
        for top, t, _x0 in B.pdfium_lines(page, tol=8.0):
            m = HDR_RE.search(t)
            if m:
                lo = int(m.group(1)); hi = int(m.group(2)) if m.group(2) else lo
                # a "Pages a–b" header applies to a range; store the whole range
                # so any printed page in [lo,hi] finds this block.
                for pp in range(lo, hi + 1):
                    practice.setdefault(pp, [])
                cur_page = lo
                in_ext = False
                continue
            m = EXT_RE.search(t)
            if m:
                in_ext = True
                cur_page = None
                continue
            if in_ext:
                mq = QW_RE.search(t)
                if mq and mq.start() <= 16:
                    ext.append((int(mq.group(1)), i + 1, float(top)))
                continue
            if cur_page is not None:
                mq = QN_RE.match(t)
                if mq:
                    practice[cur_page].append((int(mq.group(1)), i + 1, float(top)))
    apdf.close()
    # de-duplicate ext by qnum (Question N appears once per block)
    seen = {}
    for q, p, y in ext:
        if q not in seen:
            seen[q] = (p, y)
    ext = [(q, p, y) for q, (p, y) in sorted(seen.items())]
    return practice, ext


def render_crop(answer_path, ans_pdf_page, y_top, y_bottom, dpi=200):
    apdf = pdfium.PdfDocument(answer_path)
    page = apdf[ans_pdf_page - 1]
    H = float(page.get_height()); W = float(page.get_width())
    y0 = max(0.0, y_top - 4.0)
    y1 = min(H, (y_bottom if y_bottom is not None else H) + 4.0)
    if y1 - y0 < 6:
        y1 = min(H, y0 + 30)
    scale = dpi / 72.0
    bmp = page.render(scale=scale)
    img = bmp.to_pil()
    Wp, Hp = img.width, img.height
    px0 = 0
    px1 = Wp
    py0 = max(0, min(Hp - 1, int(round(y0 * scale))))
    py1 = max(py0 + 4, min(Hp, int(round(y1 * scale))))
    crop = img.crop((px0, py0, px1, py1))
    apdf.close()
    return crop


def save_crop(crop, book_id, printed, qnum):
    fname = f"book_{book_id}_a_p{printed}_{qnum}.jpg"
    fp = os.path.join(FIG_DIR, fname)
    crop.save(fp, 'JPEG', quality=88)
    return '/figures/' + fname, fp


def match_one_question(q, practice, ext, offset, extended):
    """Return (answer_image_rel, note). Primary key = the question's actual
    number (parsed from source). Positional fallback only when the qnum is
    unknown or not present in the answer block for that printed page."""
    printed = q.get('printed_page')
    if printed is None:
        return None, 'no-printed-page'
    qnum = q.get('qnum_int')
    is_ext = bool(q.get('extended'))
    # --- extended-response: keyed by Question N in the continuous ext block ---
    if is_ext and extended:
        if qnum is not None:
            cand = [(p, y) for (qq, p, y) in ext if qq == qnum]
            if cand:
                p0, y0 = cand[0]
                nxt = [y for (qq, p, y) in ext if p == p0 and y > y0]
                yb = min(nxt) if nxt else None
                crop = render_crop(q['answer_path'], p0, y0, yb)
                return save_crop(crop, q['book_id'], printed, qnum)
        # fallback: whole ext block top region
        if ext:
            p0, y0 = ext[0][1], ext[0][2]
            crop = render_crop(q['answer_path'], p0, y0, None)
            return save_crop(crop, q['book_id'], printed, qnum or 0)
        return None, 'no-ext-answer'
    # --- practice: largest printed page key <= this question's printed page ---
    best_pp = None
    for pp in sorted(practice.keys()):
        if pp <= printed:
            best_pp = pp
        else:
            break
    if best_pp is None:
        return None, 'no-practice-block'
    block = practice[best_pp]
    if qnum is not None:
        cand = [(qq, p, y) for (qq, p, y) in block if qq == qnum]
        if cand:
            qq, p0, y0 = cand[0]
            same_page = [y for (oq, op, y) in block if op == p0 and y > y0]
            yb = min(same_page) if same_page else None
            crop = render_crop(q['answer_path'], p0, y0, yb)
            return save_crop(crop, q['book_id'], printed, qq)
        # qnum known but not in this answer block -> do not guess positionally
        return None, f'qnum-{qnum}-not-in-block'
    # qnum unknown: positional fallback (may be imprecise on count-mismatch pages)
    idx = min(q.get('sibling_index', 0), len(block) - 1)
    qq, p0, y0 = block[idx]
    same_page = [y for (oq, op, y) in block if op == p0 and y > y0]
    yb = min(same_page) if same_page else None
    crop = render_crop(q['answer_path'], p0, y0, yb)
    return save_crop(crop, q['book_id'], printed, qq)


def qnum_from_source(source):
    m = re.search(r'Q(\d+)', source or '')
    return int(m.group(1)) if m else None


def run(book_id, dry_run=False, limit=None):
    # import BOOKS to get answer_path
    import extract_books as E
    book = next((b for b in E.BOOKS if b['id'] == book_id), None)
    if not book:
        print(f"book {book_id} not found"); return
    answer_path = book.get('answer_path')
    if not answer_path or not os.path.exists(answer_path):
        print(f"{book_id}: no answer_path"); return
    cfg = ANSWER_CFG.get(book_id, dict(offset=8, extended=False))
    offset = cfg.get('offset', 8)
    extended = cfg.get('extended', False)
    practice, ext = build_answer_index(answer_path)
    print(f"{book_id}: answer index built — practice printed pages={len(practice)}, ext questions={len(ext)}")

    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("""SELECT id, book_id, book_page, source, question_image, answer_image
                   FROM questions WHERE book_id=? ORDER BY book_page, id""",
                (book_id,))
    rows = cur.fetchall()
    # group by printed page to compute sibling_index
    by_printed = {}
    for r in rows:
        printed = (r['book_page'] - offset) if r['book_page'] else None
        by_printed.setdefault(printed, []).append(r)
    results = []
    cnt = 0
    for r in rows:
        printed = (r['book_page'] - offset) if r['book_page'] else None
        sibs = by_printed.get(printed, [r])
        sibs_sorted = sorted(sibs, key=lambda x: x['id'])
        sibling_index = sibs_sorted.index(r)
        ext_flag = 'extended-response' in (r['source'] or '').lower() or \
                   'extended' in (r['source'] or '').lower()
        q = dict(book_id=book_id, printed_page=printed, sibling_index=sibling_index,
                 qnum_int=qnum_from_source(r['source']), extended=ext_flag,
                 answer_path=answer_path)
        rel, note = match_one_question(q, practice, ext, offset, extended)
        results.append((r['id'], r['book_page'], printed, rel, note))
        if rel:
            cnt += 1
        if limit and len(results) >= limit:
            break
    if dry_run:
        print(f"[dry-run] matched {cnt}/{len(results)}")
        for rid, bp, pr, rel, note in results[:40]:
            print(f"   {rid} raw={bp} printed={pr} -> {rel} ({note})")
        return
    # write to DB
    upd = 0
    for rid, bp, pr, rel, note in results:
        if rel:
            cur.execute("UPDATE questions SET answer_image=? WHERE id=?", (rel, rid))
            upd += 1
    con.commit(); con.close()
    print(f"{book_id}: updated answer_image for {upd}/{len(results)} questions")


if __name__ == '__main__':
    bid = sys.argv[1] if len(sys.argv) > 1 else 'PH-OX-2023'
    dry = '--dry' in sys.argv
    run(bid, dry_run=dry)
