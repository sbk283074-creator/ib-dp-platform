#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
reimport_book.py — Re-extract a single book and REPLACE its question rows
in the platform database (backend/data/app.db) atomically.

Why this is needed:
  * The /api/books/import endpoint uses INSERT OR REPLACE by question id.
    A buggy re-run that produced MORE rows than the previous good run would
    leave orphan rows (e.g. CS-OX-2025-Q1..Q119 replaced but Q120..Q312
    from the old run kept).  So we must DELETE the old book rows first.
  * Better-sqlite3 (the server) reads on every query, so a brief
    DELETE+INSERT in one transaction from a separate sqlite3 connection is
    safe — SQLite serialises writers.

Usage:
  python reimport_book.py --book CS-OX-2025
  python reimport_book.py --book MA-HODDER-WB           # scanned workbook
  python reimport_book.py --book MA-OXFORD-2019 --dry-run  # just extract, no DB write

Steps:
  1. Resolve book in extract_books.BOOKS or extract_books_scanned.SCANNED_BOOKS.
  2. Extract (text or scanned) -> in-memory question list.
  3. Open app.db, DELETE FROM questions WHERE book_id=? AND source_type='book'.
  4. INSERT every question (mirroring backend/src/questionRepo.js columns).
  5. UPSERT the books row with total_questions = len.
"""
import os, sys, json, argparse, time, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

APP_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'app.db'))

# --- DB column set: must mirror backend/src/questionRepo.js insertQuestion
DB_COLS = [
    'id', 'subject', 'level', 'topic', 'subtopic', 'paper_type', 'command_term',
    'marks', 'difficulty', 'question', 'figure', 'answer', 'explanation',
    'source', 'tags', 'authored_by', 'created_at', 'knowledge_point_ids',
    'definition_basis', 'answer_figure', 'question_image', 'answer_image',
    'figure_image', 'book_id', 'book_section', 'book_page', 'in_book_order',
    'source_type',
]


def to_row(q):
    """Adapt an extractor question dict to the DB row (28 cols)."""
    import datetime as _dt
    return {
        'id': q['id'],
        'subject': q['subject'],
        'level': q.get('level'),
        'topic': q.get('topic'),
        'subtopic': q.get('subtopic'),
        'paper_type': q.get('paper_type'),
        'command_term': q.get('command_term'),
        'marks': q.get('marks'),
        'difficulty': q.get('difficulty'),
        'question': q.get('question'),
        'figure': q.get('figure'),
        'answer': q.get('answer'),
        'explanation': q.get('explanation'),
        'source': q.get('source'),
        'tags': json.dumps(q.get('tags') or []),
        'authored_by': q.get('authored_by') or 'import',
        'created_at': q.get('created_at') or _dt.datetime.utcnow().isoformat() + 'Z',
        'knowledge_point_ids': json.dumps(q.get('knowledge_point_ids') or []),
        'definition_basis': q.get('definition_basis'),
        'answer_figure': q.get('answer_figure'),
        'question_image': q.get('question_image'),
        'answer_image': q.get('answer_image'),
        'figure_image': q.get('figure_image'),
        'book_id': q.get('book_id'),
        'book_section': q.get('book_section'),
        'book_page': q.get('book_page'),
        'in_book_order': q.get('in_book_order') or 0,
        'source_type': q.get('source_type') or 'book',
    }


def find_book(bookid):
    import importlib
    eb = importlib.import_module('extract_books')
    for b in eb.BOOKS:
        if b['id'] == bookid and not b.get('skip_extract'):
            if b.get('scanned'):
                # scanned book — look it up in the scanned registry (may
                # differ in seg/options).  Only import the scanned module
                # when actually needed, since it pulls numpy/easyocr.
                try:
                    ebs = importlib.import_module('extract_books_scanned')
                    sb = next((x for x in ebs.SCANNED_BOOKS if x['id'] == bookid), None)
                    return ('scanned', sb or b)
                except Exception:
                    return ('scanned', b)
            return ('text', b)
    # fallback: scanned registry (only when not found in the text list)
    try:
        ebs = importlib.import_module('extract_books_scanned')
        for b in ebs.SCANNED_BOOKS:
            if b['id'] == bookid:
                return ('scanned', b)
    except Exception:
        pass
    return (None, None)


def extract_text(book, dry_run=False):
    import extract_books as eb
    return eb.extract_text_book_pdfium(book, dry_run=dry_run)


def extract_scanned(book, dry_run=False):
    import extract_books_scanned as ebs
    reader = ebs.build_reader()
    try:
        return ebs.extract_scanned_book(book, reader, dry_run=dry_run)
    finally:
        try:
            del reader
        except Exception:
            pass


def reimport(bookid, dry_run=False, verbose=True):
    kind, book = find_book(bookid)
    if not book:
        print(f"[reimport] book {bookid} not found in any registry"); return 1
    if verbose:
        print(f"[reimport] {bookid}  kind={kind}  title={book['title']}")
    t0 = time.time()
    if kind == 'text':
        res = extract_text(book, dry_run=dry_run)
    else:
        res = extract_scanned(book, dry_run=dry_run)
    questions = res['questions']
    book_meta = res['book']
    if verbose:
        print(f"[reimport] extracted {len(questions)} questions in {time.time()-t0:.1f}s")
    if dry_run:
        print(f"[reimport] DRY RUN — not writing DB")
        # still write book_json so the operator can inspect
        out = os.path.join(os.path.dirname(__file__), 'book_json', f"{bookid}.json")
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        print(f"[reimport] wrote {out}")
        return 0
    if not os.path.exists(APP_DB):
        print(f"[reimport] app.db not found: {APP_DB}"); return 2
    import sqlite3
    con = sqlite3.connect(APP_DB, timeout=15)
    try:
        cur = con.cursor()
        # 1) DELETE old book rows
        cur.execute('DELETE FROM questions WHERE book_id = ? AND source_type = ?',
                    (bookid, 'book'))
        n_del = cur.rowcount
        if verbose:
            print(f"[reimport] deleted {n_del} old rows for {bookid}")
        # 2) UPSERT book row
        cur.execute('''
            INSERT OR REPLACE INTO books
              (id, subject, title, publisher, edition, has_answers,
               answer_source, cover_path, total_questions, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,COALESCE((SELECT created_at FROM books WHERE id=?),?))
        ''', (
            book_meta['id'], book_meta['subject'], book_meta['title'],
            book_meta.get('publisher'), book_meta.get('edition'),
            1 if book_meta.get('has_answers') else 0,
            book_meta.get('answer_source'), book_meta.get('cover_path'),
            len(questions), book_meta['id'], book_meta.get('created_at') or '',
        ))
        # 3) INSERT questions
        placeholders = ','.join('?' * len(DB_COLS))
        ins_sql = f"INSERT OR REPLACE INTO questions ({','.join(DB_COLS)}) VALUES ({placeholders})"
        rows = [tuple(to_row(q).get(c) for c in DB_COLS) for q in questions]
        cur.executemany(ins_sql, rows)
        con.commit()
        if verbose:
            print(f"[reimport] inserted {len(rows)} rows; total in DB for {bookid} = "
                  f"{cur.execute('select count(*) from questions where book_id=? and source_type=\"book\"', (bookid,)).fetchone()[0]}")
    finally:
        con.close()
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--book', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    sys.exit(reimport(args.book, dry_run=args.dry_run))


if __name__ == '__main__':
    main()
