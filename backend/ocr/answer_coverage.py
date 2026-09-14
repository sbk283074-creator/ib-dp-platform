#!/usr/bin/env python3
"""answer_coverage.py — how close are the book questions to having real answers?

The book import stores every answer as the sentinel '__AI_FILL__' and leaves
answer_image NULL. This reports, per book, whether a companion answer PDF is
wired in book_registry.py and how many of the book's questions actually carry an
answer crop, so "answers are done" is a number rather than a claim.

It also flags the misleading combination: a book whose `has_answers` flag is 1
(the UI badges it "Has answers") while zero of its questions have an answer
image. That state is worse than has_answers=0, because it tells the student an
answer exists and then shows none.

Usage:
    python3 answer_coverage.py            # table + summary
    python3 answer_coverage.py --json     # machine-readable
Exit code is 1 if any book is in the misleading state, else 0.
"""
import os
import sys
import json
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import book_registry as R  # noqa: E402

DB = os.path.join(HERE, "..", "data", "app.db")


def collect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    counts = {
        r["book_id"]: (r["n"], r["answered"])
        for r in cur.execute(
            """SELECT book_id,
                      COUNT(*) AS n,
                      SUM(CASE WHEN answer_image IS NOT NULL AND answer_image != ''
                               THEN 1 ELSE 0 END) AS answered
                 FROM questions WHERE category = 'book' GROUP BY book_id"""
        )
    }
    books = {r["id"]: dict(r) for r in cur.execute("SELECT * FROM books")}
    con.close()
    return counts, books


def main():
    as_json = "--json" in sys.argv
    counts, books = collect()

    rows = []
    misleading = []
    for cfg in R.BOOKS:
        bid = cfg["id"]
        ap = cfg.get("answer_path")
        n, answered = counts.get(bid, (0, 0))
        db_book = books.get(bid, {})
        db_has = int(db_book.get("has_answers") or 0)
        reg_has = 1 if cfg.get("has_answers") else 0
        rows.append(
            dict(id=bid, title=cfg.get("title"), questions=n, answered=answered,
                 answer_pdf=bool(ap), answer_pdf_exists=bool(ap and os.path.exists(ap)),
                 registry_has_answers=reg_has, db_has_answers=db_has,
                 answer_source=cfg.get("answer_source"))
        )
        if db_has and answered == 0:
            misleading.append(bid)

    if as_json:
        print(json.dumps(dict(books=rows, misleading=misleading), indent=2, ensure_ascii=False))
        return 1 if misleading else 0

    print("%-18s %-5s %9s %9s  %s" % ("BOOK", "SRC", "QUESTIONS", "ANSWERED", "STATUS"))
    print("-" * 74)
    for r in sorted(rows, key=lambda x: (not x["answer_pdf"], x["id"])):
        if not r["answer_pdf"]:
            status = "no answer PDF found on disk"
        elif r["answered"] == 0:
            status = "source wired, extraction not run"
        elif r["answered"] < r["questions"]:
            status = "PARTIAL"
        else:
            status = "complete"
        if r["id"] in misleading:
            status = "MISLEADING: flag=1 but 0 answers"
        print("%-18s %-5s %9d %9d  %s" % (
            r["id"], "yes" if r["answer_pdf"] else "-",
            r["questions"], r["answered"], status))

    tot_q = sum(r["questions"] for r in rows)
    tot_a = sum(r["answered"] for r in rows)
    with_src = sum(1 for r in rows if r["answer_pdf"])
    print()
    print("books: %d   with a wired answer PDF: %d" % (len(rows), with_src))
    print("questions: %d   with an answer image: %d  (%.1f%%)"
          % (tot_q, tot_a, (100.0 * tot_a / tot_q) if tot_q else 0.0))
    if misleading:
        print("\nWARNING - flagged has_answers=1 with zero answers: %s" % ", ".join(misleading))
        print("The UI badges these 'Has answers'. Clear the flag or run the extraction.")
    return 1 if misleading else 0


if __name__ == "__main__":
    sys.exit(main())
