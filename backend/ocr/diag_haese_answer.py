"""Validate the Haese answer-matching approach (read-only).

Keying: worked solutions are organised by Review set.  Textbook `source`
strings only carry `pN Qn`, so we derive each question's review set by
scanning the TEXTBOOK PDF for the most recent "Review set XY" header above
its page, then match on (review_set, qnum) against the worked-solutions PDF.
"""
import re, os, sqlite3
import booklib as B
import pypdfium2 as pdfium
import extract_books as E

book = next(b for b in E.BOOKS if b['id'] == 'MA-HAESE-CORE1')
text_path = book['path']
ans_path = book['answer_path']
DP = os.path.dirname(os.path.dirname(text_path))  # not used

RS_RE = re.compile(r'Review\s+set\s+(\d+[A-Z]?)', re.I)
QN_RE = re.compile(r'^\s*(\d+)\s+[A-Za-z(]')


def scan_textbook_rs(text_path):
    """Return {book_page(1-based): review_set_name} carried forward."""
    tpdf = pdfium.PdfDocument(text_path)
    n = len(tpdf)
    page_rs = {}
    cur = None
    for i in range(n):
        page = tpdf[i]
        for top, t, _x0 in B.pdfium_lines(page, tol=8.0):
            m = RS_RE.search(t)
            if m and m.start() <= 30:
                cur = m.group(1).upper()
        page_rs[i + 1] = cur
    tpdf.close()
    return page_rs


def build_haese_index(ans_path):
    """Return { (review_set, qnum): (ans_pdf_page, y_top) } plus per-page qnum
    list for crop boundaries."""
    apdf = pdfium.PdfDocument(ans_path)
    n = len(apdf)
    index = {}
    page_qnums = {}  # ans_pdf_page -> [(y, qnum)]
    cur = None
    for i in range(n):
        page = apdf[i]
        pp = i + 1
        for top, t, _x0 in B.pdfium_lines(page, tol=8.0):
            mh = RS_RE.search(t)
            if mh and mh.start() <= 30:
                cur = mh.group(1).upper()
                continue
            mq = QN_RE.match(t)
            if mq and cur is not None:
                q = int(mq.group(1))
                key = (cur, q)
                if key not in index:
                    index[key] = (pp, float(top))
                page_qnums.setdefault(pp, []).append((float(top), q))
    apdf.close()
    return index, page_qnums


def main():
    page_rs = scan_textbook_rs(text_path)
    print(f"textbook pages scanned; review-set pages covered: "
          f"{sum(1 for v in page_rs.values() if v)}/{len(page_rs)}")
    # show a few rs transitions
    prev = None
    trans = []
    for p in sorted(page_rs):
        if page_rs[p] != prev:
            trans.append((p, prev, page_rs[p]))
            prev = page_rs[p]
    print("first transitions:", trans[:12])

    index, page_qnums = build_haese_index(ans_path)
    print(f"worked-solutions index size: {len(index)} (rs,qnum) keys")

    db = os.path.join(os.path.dirname(__file__), '..', 'data', 'app.db')
    con = sqlite3.connect(db); cur = con.cursor()
    cur.execute("""SELECT id, book_page, source FROM questions
                   WHERE book_id='MA-HAESE-CORE1' ORDER BY book_page, id""")
    rows = cur.fetchall()
    con.close()

    matched = 0
    missing = []
    qn_re = re.compile(r'Q(\d+)')
    for rid, bp, src in rows:
        m = qn_re.search(src or '')
        qnum = int(m.group(1)) if m else None
        rs = page_rs.get(bp)
        if qnum is None or rs is None:
            missing.append((bp, src, 'no-qnum-or-rs'))
            continue
        if (rs, qnum) in index:
            matched += 1
        else:
            missing.append((bp, src, f'rs={rs} q={qnum} NOT-in-solutions'))
    print(f"\n=== MATCH RESULT: {matched}/{len(rows)} textbook questions matched ===")
    # group missing by reason
    from collections import Counter
    c = Counter(r[2].split(' NOT')[0].split(' rs=')[0] if 'NOT' in r[2] else r[2] for r in missing)
    print("missing reasons:", dict(c))
    print("\nfirst 30 unmatched:")
    for bp, src, why in missing[:30]:
        print(f"  bp={bp} {src!r} -> {why}")


if __name__ == '__main__':
    main()
