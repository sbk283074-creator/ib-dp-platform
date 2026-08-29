"""extract_answers_haese.py — populate answer_image for Haese WORKED SOLUTIONS.

Haese worked solutions are organised by Review set, NOT by textbook printed
page.  The questions.topic column already carries the review-set name
(e.g. 'Trigonometric Functions — Review set 17B'), so we derive each
question's review set directly from it (no fragile textbook-PDF scan).

Worked-solution page structure (verified):
  * Each review set has a header line "Chapter N (...) Review set XY" (the
    "Review set" token may appear past column 30, so it is matched anywhere).
  * Question starts are lines at the LEFT MARGIN beginning with a 1-2 digit
    number: either "N a" / "N b" (part letter), "N(" , or a BARE "N" on its
    own line.  Sub-parts ("a.", "b.") start with a letter, not a digit, so
    they are not mistaken for question starts.  Body numbers ("= 36") and
    page footers ("130 Chapter 17 ...") are excluded.
  * The pages are TWO-COLUMN, so we capture each start's x0 and crop within the
    same column (down to the next start in that column, else page bottom).

Matching: exact (review_set, qnum) from the textbook source.  If a qnum is
not found in the worked solutions (detection gap), we fall back to positional
matching within the review set (k-th textbook question <-> k-th detected
start), which is robust once question counts align after the coloured-number
extraction fix.
"""
import os, sys, re, sqlite3
import booklib as B
import pypdfium2 as pdfium
import extract_books as E

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FIG_DIR = os.path.join(BACKEND_ROOT, 'public', 'figures')
os.makedirs(FIG_DIR, exist_ok=True)
DB = os.path.join(BACKEND_ROOT, 'data', 'app.db')

BOOK_ID = 'MA-HAESE-CORE1'
RS_RE = re.compile(r'Review\s+set\s+(\d+[A-Z]?)', re.I)
# question start: number then part-letter / "(" / bare-number(end of line)
QN_RE = re.compile(r'^\s*(\d{1,2})\s*(?:[a-eA-E(]|[.)]?\s*$)')
CH_RE = re.compile(r'^\s*Chapter\s+(\d+)', re.I)
MAX_QNUM = 60  # review sets rarely exceed ~36 questions


def rs_from_topic(topic):
    if not topic:
        return None
    m = RS_RE.search(topic)
    return m.group(1).upper() if m else None


def qnum_from_source(source):
    m = re.search(r'Q(\d+)', source or '')
    return int(m.group(1)) if m else None


def build_haese_index(ans_path):
    """Return (index, page_starts) where
       index:       {(rs, qnum): (ans_pdf_page, y_top, x0)}
       page_starts: {ans_pdf_page: [(y_top, x0, qnum), ...]}  (sorted by y)
    Only the FIRST occurrence of a (rs, qnum) is kept for the index; page_starts
    keeps every detected start (for column-aware crop boundaries)."""
    apdf = pdfium.PdfDocument(ans_path)
    n = len(apdf)
    index = {}
    page_starts = {}
    cur = None
    for i in range(n):
        pp = i + 1
        page = apdf[i]
        W = float(page.get_width())
        for top, t, x0 in B.pdfium_lines(page, tol=8.0):
            low = t.lower()
            if 'chapter' in low or 'review' in low:
                # header / page-footer line; never a question start
                mh = RS_RE.search(t)
                if mh:
                    cur = mh.group(1).upper()
                elif CH_RE.match(t) and 'review' not in low:
                    cur = None
                continue
            mq = QN_RE.match(t)
            if not mq:
                continue
            q = int(mq.group(1))
            if q < 1 or q > MAX_QNUM:
                continue
            rest = t[mq.end():].strip()
            is_bare = (rest == '' or rest in '.)')
            # bare numbers must sit at the left margin (mid-page bare digits are
            # almost always equation results, not question numbers)
            if is_bare and x0 > 0.25 * W:
                continue
            if cur is None:
                continue
            key = (cur, q)
            if key not in index:
                index[key] = (pp, float(top), x0)
            page_starts.setdefault(pp, []).append((float(top), x0, q))
    apdf.close()
    for pp in page_starts:
        page_starts[pp].sort()
    return index, page_starts


def render_crop(answer_path, ans_pdf_page, y_top, y_bottom, dpi=200):
    apdf = pdfium.PdfDocument(answer_path)
    page = apdf[ans_pdf_page - 1]
    H = float(page.get_height())
    y0 = max(0.0, y_top - 4.0)
    y1 = min(H, (y_bottom if y_bottom is not None else H) + 4.0)
    if y1 - y0 < 6:
        y1 = min(H, y0 + 40)
    scale = dpi / 72.0
    img = page.render(scale=scale).to_pil()
    Wp, Hp = img.width, img.height
    py0 = max(0, int(round(y0 * scale)))
    py1 = max(py0 + 4, min(Hp, int(round(y1 * scale))))
    crop = img.crop((0, py0, Wp, py1))
    apdf.close()
    return crop


def save_crop(crop, bp, rs, qnum):
    fname = f"book_{BOOK_ID}_a_p{bp}_{qnum}.jpg"
    fp = os.path.join(FIG_DIR, fname)
    crop.save(fp, 'JPEG', quality=88)
    return '/figures/' + fname, fp


def run(dry_run=False, limit=None):
    book = next(b for b in E.BOOKS if b['id'] == BOOK_ID)
    ans_path = book['answer_path']
    index, page_starts = build_haese_index(ans_path)
    print(f"Haese index: {len(index)} (rs,qnum) keys across "
          f"{len(set(k[0] for k in index))} review sets")

    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("""SELECT id, book_page, source, topic FROM questions
                   WHERE book_id=? ORDER BY book_page, id""", (BOOK_ID,))
    rows = cur.fetchall()

    # group textbook questions by review set (in book order) for positional fallback
    by_rs = {}
    for r in rows:
        rs = rs_from_topic(r['topic'])
        if rs is None:
            continue
        by_rs.setdefault(rs, []).append(r)

    # detected worked-solution starts per review set, in page/y order (one per
    # unique qnum) — used for the positional fallback.
    starts_for_rs = {}
    for (rs, q) in index:
        pp, y0, x0 = index[(rs, q)]
        starts_for_rs.setdefault(rs, []).append((pp, y0, x0))
    for rs in starts_for_rs:
        starts_for_rs[rs].sort()

    results = []
    cnt = 0
    for r in rows:
        bp = r['book_page']
        qnum = qnum_from_source(r['source'])
        rs = rs_from_topic(r['topic'])
        if qnum is None or rs is None:
            results.append((r['id'], bp, None, 'no-qnum-or-rs'))
            continue
        note = 'ok'
        pp = y0 = x0 = None
        if (rs, qnum) in index:
            pp, y0, x0 = index[(rs, qnum)]
        else:
            # positional fallback: the qnum-th detected start within the set
            fb = starts_for_rs.get(rs)
            if fb is not None and 1 <= qnum <= len(fb):
                pp, y0, x0 = fb[qnum - 1]
                note = 'positional'
        if pp is None:
            results.append((r['id'], bp, None, f'{rs} q={qnum} not-in-solutions'))
            continue
        # column-aware next boundary
        Wp = Wp_of(ans_path, pp)
        side_left = x0 < 0.5 * Wp
        nxt = [yy for (yy, xx, qq) in page_starts.get(pp, [])
               if ((xx < 0.5 * Wp) == side_left) and yy > y0]
        yb = min(nxt) if nxt else None
        rel = None
        if not dry_run:
            crop = render_crop(ans_path, pp, y0, yb)
            rel, _fp = save_crop(crop, bp, rs, qnum)
        else:
            rel = f'/figures/book_{BOOK_ID}_a_p{bp}_{qnum}.jpg'
        results.append((r['id'], bp, rel, note))
        cnt += 1

    if dry_run:
        from collections import Counter
        c = Counter(note for (_, _, _, note) in results)
        print(f"[dry-run] matched {cnt}/{len(results)}  notes={dict(c)}")
        miss = [(bp, note) for (_, bp, rel, note) in results if rel is None][:30]
        print("unmatched sample:", miss)
        return
    upd = 0
    for rid, bp, rel, note in results:
        if rel:
            cur.execute("UPDATE questions SET answer_image=? WHERE id=?", (rel, rid))
            upd += 1
    con.commit(); con.close()
    print(f"Haese: updated answer_image for {upd}/{len(results)} questions")


# ---- helpers ----
_WCACHE = {}
def Wp_of(ans_path, pp):
    if (ans_path, pp) not in _WCACHE:
        apdf = pdfium.PdfDocument(ans_path)
        _WCACHE[(ans_path, pp)] = float(apdf[pp - 1].get_width())
        apdf.close()
    return _WCACHE[(ans_path, pp)]


if __name__ == '__main__':
    dry = '--dry' in sys.argv
    run(dry_run=dry)
