# Textbook (book) import — hands-on audit

Date: 2026-09-13 · Scope: `category='book'` in `backend/data/app.db` (7,304 rows, 19 books)
Method: direct DB inspection + **manual inspection of actual crop images** (montages viewed by eye) + cross-check against the **source PDF text layer**. No reliance on `verify_bank.mjs` alone.

---

## Verdict (short)

The textbook import is a **raw, image-only import with no answers and frequent crop errors.**
It is **not trustworthy as a study source in its current state.**

| Aspect | State |
|---|---|
| Answers (`answer` / `answer_image`) | ❌ **100% missing** — all `__AI_FILL__`, `answer_image` NULL |
| Question text (`question`) | ❌ 100% placeholder `"[See question image. …]"` (no searchable text) |
| Question crops (`question_image`) | ⚠️ present, but **merge 2–8 questions** and sometimes capture non-question content |
| Marks / difficulty / topic | ❌ all NULL / generic (`topic='Exercises'`) |
| Review state | all `review_status='new'`, `well_down=0` |
| Book/page/section metadata | ✅ present & consistent; `books.total_questions` matches actual |

---

## 1. Answers — completely missing (critical)

Direct DB counts:

```
book rows                              : 7304
book rows with answer = '__AI_FILL__'  : 7304   (100%)
book rows with real answer text        : 0
book rows with answer_image            : 0
books.has_answers = 1                  : 0 / 19
```

- `answer` **and** `explanation` are both the literal sentinel `__AI_FILL__` on every row.
- This is a **documented, known gap**: `BOOK_FIX_PLAN.md` §0 states *"answer is an unfilled sentinel (`__AI_FILL__`); `answer_image` is never populated"* and planned a new `extract_answers.py`.
- `extract_answers.py` exists (2026-08-30) but was **never run to populate** the DB.
- **Answer sources DO exist** (43 answer/solution PDFs found), e.g.:
  - `IBID/Mathematics Higher Level (CORE) - ANSWERS - …2004.pdf`
  - `IBID/Mathematics HL Core - ANSWERS - …2017.pdf`
  - `Physics-HLSL-Oxford Textbook…/Physics - ANSWERS - …2023 [semi-official].pdf`
  - `Tsokos 7th edition Workbook ANSWERS.pdf`
  - `CAMBRIDGE/Mathematics HL - Solutions Manual - …2016.pdf`
  - `HL Workbook/…Exam Practice Workbook - ANSWERS - Hodder 2021.pdf`
- **`book_registry.py` has no `answer_path` field**, so nothing maps a book to its answer PDF → the answer pipeline was never wired.

## 2. Question text — placeholder only (critical for search)

Every row: `question = "[See question image. Source: <book>, <section>.]"`.
The real question exists **only in the image**, so book questions cannot be searched/filtered by content. (Contrast: past-paper rows carry real text.)

## 3. Question crops — merges + non-question content (major)

Verified **by eye** (montages) and confirmed against the **source PDF text layer**.

**Merges (multiple distinct numbered questions in one crop):**

| Book | Crop | Contains |
|---|---|---|
| CS-OXFORD-2025 | `q0001` | Q1 **+ Q2** |
| CS-OXFORD-2025 | `q0002` | Q3 **+ Q4** |
| MA-HAESE-AA2 | `q0003` | Q3 **+ Q4** |
| MA-CAMBRIDGE-2012 | `q0001` | Q1 **+ Q2** |
| MA-CAMBRIDGE-2012 | `q0002` | Q3 **+ Q4** |
| PH-TSOKOS-CB | `q0002` | Q12 **+ Q13 + Q14** |
| PH-TSOKOS-CB | `q0003` | Q15 **+ Q16 + Q17 + Q18** |
| PH-CAMBRIDGE-WB | `q0001` | Q3 **+ Q4** |
| MA-OXFORD-2019 | `q0002` | Q1…**Q8** |

Source cross-check (proves they are distinct questions):
- CS-OXFORD-2025 PDF p.47 text: `1. … 2. … 3. … 4. … 5. … 6. … 7. … [8 = number absent] … 9. … 10. …`
- PH-TSOKOS-CB PDF p.32 text: `12 Two balls… / 13 A particle… / 14 The graph… / 15 Your brand-new…`

DB undercount proof: **CS-OXFORD-2025 page 47 = 10 DB rows, but ~14 questions** in the source.

**Root cause (confirmed):** question numbers set in a coloured/outlined style are **absent from the PDF text layer** (e.g. CS Q8's number is missing). The segmenter detects the remaining numbers, so a band runs from one detected number to the next detected number — swallowing the skipped question. This is exactly the mechanism `BOOK_FIX_PLAN.md` §1.2 described for Haese ("45 pages show an intra-page qnum jump"). The planned fix (**`visual_qnum_tops` connected-component splitter**) was **never implemented** — `grep visual_qnum booklib.py` → empty.

**Non-question content in crops:**
- MA-CAMBRIDGE-2012 `q0007` = a "Topic 1: Algebra" divider page (not a question).
- MA-CAMBRIDGE-2012 `q0100` = Q5+Q6 over a **handwritten-annotation background**.
- PH-CAMBRIDGE-WB `q0002` = a "TIP" instruction box (not a question).
- MA-IBID-2004 `q0001` = a worked-solution fragment (`{x: |x+1| > 1} = …`), not a question.

## 4. Metadata

- `marks` = NULL, `difficulty` = NULL on all 7,304 rows.
- `topic` = `'Exercises'` (generic), `subtopic` = `book_section`.
- `review_status` = `'new'`, `well_down` = 0 on all rows (nothing reviewed).

## 5. Orphaned images

`public/figures/book2/` holds **12,938 files** but only **7,304** are referenced (≈1 per question). The extra ~5,634 are a second naming scheme (`<book>_q_<n>_<p>.jpg`, e.g. `MA-CAMBRIDGE-2012_q_100_2.jpg`) **not referenced by the DB** — dead weight / evidence of a superseded pass.

## 6. What IS correct

- 19 books; `books.total_questions` matches the actual per-book row count for **every** book.
- Every `question_image` resolves on disk; `book_section` / `book_page` / `in_book_order` / `source` (`#N (p.P)`) are present and internally consistent.
- Crops themselves are legible and correctly framed **when they contain exactly one question** (e.g. MA-HODDER-WB q0001/q0002, MA-HAESE-AA2 q0001/q0002, MA-HAESE-CORE1 q0001).

---

## Recommended next steps (in order)

1. **Wire + run the answer pipeline.** Add `answer_path` to `book_registry.py` for the books that have answer PDFs; run `extract_answers.py` to populate `answer_image` (and/or `answer` text). 8+ books have a matching answer/solution PDF today.
2. **Fix the merges** — implement the planned `visual_qnum_tops` colour-agnostic splitter in `booklib.py`, then re-extract the affected books (Haese, Cambridge, Oxford, CS, Tsokos).
3. **Purge non-question crops** (divider/TIP/worked-solution pages) — extend `page_exclude_re` and add a "first token is not a question number" reject.
4. **Store real question text** (from the text layer) so books are searchable, or accept image-only by design and document it.
5. **Delete the orphaned `<book>_q_<n>_<p>.jpg`** files (or map them) once the scheme is unified.
6. Re-run `verify_bank.mjs` and add a book-specific answer-coverage check.

> Note: `MASTER_PLAN.md` (2026-08-24) intended answers to be attached **in the same job**; the current state does not meet that.
