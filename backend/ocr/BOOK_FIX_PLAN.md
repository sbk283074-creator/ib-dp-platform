# Book Re-Extraction & Answer-Screenshot Plan

> Owner: extraction pipeline (`backend/ocr/`)
> Status: **RESEARCH COMPLETE + PLAN** (this document supersedes `HODDER_FIX_PLAN.md`)
> Driven by user report: a physics textbook (Oxford 5ed `PH-OX-2023`) and a math
> textbook (Haese Core Topics HL 1 `MA-HAESE-CORE1`) have systematic extraction
> errors, and book answers are missing/unfilled.

## 0. TL;DR

| Book | Problem | Scope (measured) | Fix |
|---|---|---|---|
| `PH-OX-2023` (Oxford Physics 5ed, *text* book) | 3 error types: (1) multi-question merges, (2) non-questions extracted (IA pages, book index, "How do/How can" inquiry boxes), (3) solutions/answers extracted as questions | **DB proof**: rows exist for p705 (inquiry box), p706/p707 (IA), p709 (index/IA tail) — exactly the pages the user reported | Re-extract with per-book `exercise_patterns` + a new `page_exclude_re`; keep valid practice pages (p701/p702 etc.) |
| `MA-HAESE-CORE1` (Haese Core Topics HL 1, *text* book) | Question numbers printed in a different **colour/outline** are missing from the PDF text layer → adjacent questions merge into one crop | **45 pages** show an intra-page non-consecutive qnum jump (a missed number). p480 = `seq [13,14,16,17,18,19,20]` (Q15 missed → Q14+Q15 merged) — the exact case the user filed | Add a **visual qnum splitter** (render + connected-component detection in the left margin) — no OCR dependency |
| All book questions | `answer` is an unfilled sentinel (`__AI_FILL__` / `[Answer pending…]`); `answer_image` is **never** populated | `QuestionCard.tsx:287` already renders `answer_image`, but nothing writes it | New `extract_answers.py`: screenshot the matching solution book; generate when no match |

**Key code pointers**
- Gate / page classification: `booklib.py::is_exercise_page_pdfium` (L476) + `booklib.py::has_toc_dots` (L531).
- Question-number → band split: `booklib.py::question_bands_pdfium` (L903) → `_line_start_number` (L148).
- Per-book driver: `extract_books.py::extract_text_book_pdfium` (L224) + registry `BOOKS` (L64).
- Re-import (preserves `well_down`): `reimport_book.py`.
- Existing text-answer pairers (set `answer`, **not** `answer_image`): `pair_answers.py`, `rebuild_physics_answers.py`.

---

## 1. Research findings

### 1.1 `PH-OX-2023` — three error types (with DB evidence)

Current DB state: 182 questions, `book_page` 19→709. Queried the reported range:

| DB `book_page` | Printed (=PDF−8) | Content (verified via text layer) | Error type |
|---|---|---|---|
| 673 | 665 | Theme E section / questions | (mixed) |
| 701 | 693 | "Practice questions" | **valid** (keep) |
| 705 | 697 | "How do emission spectra provide information about…" — inquiry box | **2 (non-question)** |
| 706 | 698 | IA region | **2** |
| 707 | 699 | "End-of-the-theme questions" (valid) **+ bogus Q100** | **2/3** |
| 709 | 701 | IA/answers tail (2 rows, no qnum) | **2** |
| 713 | 705 | "Approaching your internal assessment" / "Internal assessment structure" | **2** |

So the bug is **over-inclusion**: the gate (`is_exercise_page_pdfium`) lets info/solution/index pages through because (a) `PH-OX-2023` has **no custom `exercise_patterns`** (falls back to `PRACTICE_PATTERNS`, which doesn't match Oxford's "Practice questions / Extended-response questions / Topic N questions / End-of-theme questions" headings), so it relies purely on `min_markers=4` left-margin numbers; and (b) a page that is a *continuation* of a preceding valid exercise page is accepted even when it is actually an IA/index page — the continuation logic leaks. The index leaked via `_bare_dot` (L211) matching dot-leader-ish lines; the inquiry boxes leaked because they contain numbered items.

### 1.2 `MA-HAESE-CORE1` — colored-number merge (mechanism confirmed)

Rendered the reported "Review set 17B" page (PDF p480; Haese is **1-up**, so book page = PDF page, *not* 2-up as previously assumed). In the Q18 region the text layer contains **only body text** ("behaviour.", "b State:", "i the period") — **no digit**. The number "18" is an outlined/coloured vector glyph pypdfium cannot read as text, so `_line_start_number` (L148) never sees it, `_filter_monotonic` drops the gap, and Q17's band extends across Q18 (measured `h≈138pt` vs normal `h≈43pt`).

Full-book scan (`diag_haese_merge2.py`): **45 review-set/exercise pages** have an intra-page non-consecutive qnum jump (gap>1), each a missed coloured/outlined number → a merged question. Representative: p480 `[13,14,16,17,18,19,20]` (Q15 missed), p128 `[13..17,19,20,21]` (Q18 missed), p482 `[13,14,16,17,18,19,20]`.

### 1.3 Answer-book structures (researched — needed for screenshot mapping)

Both companion answer PDFs are **text-based** (verified via `get_text_range`).

- **Oxford `Physics - ANSWERS` (`PH-OX-2023.answer_path`)** — 53 pages, TOC by Theme:
  `Theme A – Space, Time, and Motion – Page 2`, `Theme B – … – Page 17`,
  `Theme C – Wave Behaviour – Page 27`, … Within a Theme, answers are grouped by
  **`Practice questions – Page N`** (N = the textbook's *printed* page) → qnum/subpart.
  → Map by **(Theme, printed_page, qnum)**.
- **Haese `WORKED SOLUTIONS` (`MA-HAESE-CORE1.answer_path`)** — 860 pages, mirrors the
  textbook chapter-by-chapter. Each solution page is labelled
  `Chapter 17 (Trigonometric functions) Review set 17B` + a per-question number.
  "Review set 17B" solutions occupy PDF pp 851–860. → Map by **(book_section, qnum)**.

Both are mappable. The UI already displays `answer_image` (`QuestionCard.tsx:287`), so
populating that column is sufficient to surface answers.

---

## 2. Root causes (code level)

1. **Over-inclusion gate** — `is_exercise_page_pdfium` (L476) accepts any page with
   `>=min_markers` left-margin numbers, and the `gate_numbered` continuation branch (in
   `extract_text_book_pdfium` L273) accepts a 'numbered' page that *follows* a real
   exercise page even when it is an IA/index page. No per-book exclude list exists.
2. **Missing coloured qnums** — `_line_start_number` (L148) only reads the *text layer*;
   outlined/coloured numbers have no text-layer glyph, so they are invisible to banding.
3. **Index leak** — `has_toc_dots` (L531) needs ≥6 dot-leader rows; the Oxford index
   layout dodged it, and `_bare_dot` (L211) admitted index entries.
4. **Answers never filled as images** — `extract_text_book_pdfium` sets `answer_image=None`
   (L547) and only ever writes `answer`/`explanation` placeholders; no module screenshots
   the companion answer PDFs.

---

## 3. Fix plan

### 3.A `PH-OX-2023` — re-extract with correct gating

**Changes in `extract_books.py` (registry entry `PH-OX-2023`, ~L80):**
- Add `exercise_patterns` matching Oxford's real practice headings:
  `practice questions`, `extended-response questions`, `topic \d+ questions`,
  `end-of-the-theme questions`, `test yourself`, `mixed review`, `review`.
- Add a new per-book field **`page_exclude_re`** (regex) and thread it through
  `is_exercise_page_pdfium` (new optional param, checked over the *whole* page, not just
  the first 400/600 chars). For Oxford physics:
  `r'(how (can|do)\b.{0,40}(provide|relate|explain|help|suggest))|approaching your internal assessment|internal assessment|^\s*(index|glossary)\b'`.
- Keep `gate_numbered=True` but make `page_exclude_re` win even over continuation (reject
  excluded pages regardless of `prev_classified`).
- Raise `has_toc_dots` robustness / add an explicit index-page reject (first line is
  `Index`/`index` with many short leader rows).

**Validate before import:** `python reimport_book.py --book PH-OX-2023 --dry-run`,
inspect `book_json/PH-OX-2023.json`: assert **0** rows whose source page is 705/706/707/709/713
and that valid pages 701/702 are still present. Then drop `--dry-run` to re-import
(`reimport_book` preserves `well_down` and the 6 open reports).

### 3.B `MA-HAESE-CORE1` — visual qnum splitter (no OCR needed)

**New function `visual_qnum_tops(page, cfg)` in `booklib.py`:**
1. Render the page to a PIL image at modest DPI (≈110).
2. Restrict to the far-left number column (`x` in `[0, ~num_col]` where `num_col` ≈ the
   smallest x0 seen among text-based qnum candidates, or `qnum_margin*W`).
3. Find connected components of "ink" (any non-background pixel — catches coloured AND
   black AND outlined numbers) whose height ∈ `[0.6,1.4]×` the median text-qnum height.
4. Return their centroid y (converted to PDF pts). These are candidate qnum tops that the
   text layer missed.

**Wire-in** in `extract_text_book_pdfium` (L301–364): build the candidate list as the
union of text-based candidates (existing `question_bands_pdfium`) **and** `visual_qnum_tops`;
sort by y; dedupe (drop visual tops within a few pt of a text candidate); re-run band
splitting on the merged list. This makes the splitter colour-agnostic and also more robust
for black numbers.

**Validate:** `diag_haese_merge2.py` should drop from **45 → ~0** pages with intra-page gaps
(allow a handful of genuine non-consecutive sets). Then `python reimport_book.py --book
MA-HAESE-CORE1` (preserves `well_down`).

> Note: this also fixes the broader class the user flagged ("the colour of the number
> sometimes are different") across the whole book, not just p482.

### 3.C Answers — screenshot the solution books (`extract_answers.py`, NEW)

A new module that, per book, opens `answer_path` and attaches an `answer_image` to each
question:
- **Oxford (`PH-OX-2023`):** build a Theme→start-page index from the answers TOC (p1).
  For a question, convert its stored `book_page` (PDF) to **printed = PDF−8**, locate the
  Theme block, then the `Practice questions – Page N` block (N=printed), then the qnum
  (from `source` suffix `Qk`); render the region from that qnum line to the next qnum/
  subpart line → crop → `answer_image`.
- **Haese (`MA-HAESE-CORE1`):** find `Chapter X (…) <book_section>` in the worked-solutions
  PDF, then the qnum block; render → `answer_image`. Match key = `(book_section, qnum)`.
- **Attach:** `UPDATE questions SET answer_image=? WHERE book_id=? AND <match key>`.
- **Generate-when-missing:** if `answer_path` is `None` (HODDER-2019, OXFORD-2019) or a
  qnum has no match in the solution book, run the AI answer generator (reuse the existing
  `__AI_FILL__` sentinel path) to write `answer` + `explanation` text. Confirm with user
  before bulk AI-generation (see §6).
- **UI:** no change required — `QuestionCard.tsx:287` already renders `answer_image`.

---

## 4. Sequencing / gating (do NOT disturb the in-flight pipeline)

1. **Let the current paper pipeline finish first**: engine re-run (`H1eJAb`, ~51 topic
   papers) → `node import_shots.mjs` → `_task2_delete_orphans.py --execute`. Verify status
   before touching book rows.
2. **3.A** PH-OX-2023 re-extraction (dry-run → inspect → import). Independent of steps 3/4.
3. **3.B** MA-HAESE-CORE1 visual splitter (dry-run → inspect → import). Preserves `well_down`.
4. **3.C** `extract_answers.py` for PH-OX-2023 + MA-HAESE-CORE1; then generate for no-key
   books. Run after 3.A/3.B so `book_page`/`book_section`/`source` are final.
5. Restart backend on :3099; re-verify in the UI (the reported pages + a sample of answers).

---

## 5. Validation / acceptance

- `PH-OX-2023`: 0 DB rows whose source page ∈ {705,706,707,709,713}; 0 intra-page qnum gaps
  on remaining practice pages; valid pages 701/702 retained.
- `MA-HAESE-CORE1`: `diag_haese_merge2.py` → 0 (or near-0) pages with intra-page gaps.
- Answers: report coverage % of book questions with `answer_image` (or generated `answer`).
- Spot-check the user's exact reports render correctly: `PH-OX-2023` p701/p702 questions;
  `MA-HAESE-CORE1` "Review set 17B" Q14/Q15 as **separate** crops; answers visible on both.

---

## 6. Open questions for the user

1. **Oxford practice vocabulary** — please confirm my proposed `exercise_patterns` list
   matches the book, so we don't drop valid pages (701/702) or keep invalid ones. The
   headings I saw: "Practice questions", "Extended-response questions", "Topic N questions",
   "End-of-the-theme questions".
2. **Answers** — OK to **AI-generate** `answer`/`explanation` for the no-answer-book books
   (`MA-HODDER-2019`, `MA-OXFORD-2019`) and for any qnum with no match in its solution book?
3. **Visual qnum** — I plan a connected-component (colour-agnostic, no OCR) splitter. OK, or
   do you prefer installing `easyocr` for explicit digit OCR? (Connected-component avoids the
   `easyocr` install + model download and is sufficient here.)
4. **Re-extraction replaces rows** — re-importing `PH-OX-2023` / `MA-HAESE-CORE1` DELETEs and
   re-INSERTs those books' rows. `reimport_book` preserves `well_down` + the open reports, but
   confirm this is acceptable (vs. an additive diff).
5. **Pipeline** — confirm the paper engine re-run / `import_shots` / orphan-deletion finished
   before we re-extract books (§4 step 1).

---

## Appendix — diagnostic scripts created this session
- `diag_haese_color.py`, `diag_haese_find.py`, `diag_haese_scan.py`, `diag_haese_merge2.py`
  — confirm the coloured-qnum merge + quantify (45 pages).
- `diag_answerbooks.py` — confirm both answer PDFs are text-based + their layout.
- `_render_pages.py` — render arbitrary PDF pages to `/tmp/render`.
