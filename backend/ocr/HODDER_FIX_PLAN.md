# HODDER Textbook Questions — Special Fix Plan

> Owner: extraction pipeline (`backend/ocr/`)
> Status: PLAN + diagnosis done (see "Diagnosis" §3)
> Driven by user report: HODDER questions (math + physics) sometimes merge multiple
> questions into one crop, and sometimes contain no complete question.

## 0. TL;DR
- The HODDER **math textbook** `MA-HODDER-2019` is a TEXT PDF. Its current extraction
  is **clean** (dry-run → 324 questions, 0 merged, 0 incomplete). No fix needed there.
- The defects the user sees are in **image-based** questions. Every HODDER/physics
  workbook row stores the question as an **image crop** (`question = "[See question image…]"`,
  `question_image` present on disk). The "merged / incomplete" problem is in those crops,
  produced by the **scanned** pipeline (`extract_books_scanned.py`).
- There is **no physics HODDER book** in the registry. The physics books the user hits are
  the scanned workbooks `PH-CAMB-WB`, `PH-TSOKOS-WB`, `PH-OX-2023` (Cambridge / Tsokos / Oxford).
  They share the exact same defect class.
- The scanned pipeline needs `easyocr` (NOT installed in this env) → that is the blocker
  for re-extracting the workbooks and for OCR-ing their real question text.

## 1. Current data (DB `app.db`, source_type='book')
| book_id | kind | Qs | qimg | qtext | answer col | explanation |
|---|---|---|---|---|---|---|
| MA-HODDER-2019 | text | 324 | 324 | 324 | `__AI_FILL__` (324) | `__AI_FILL__` (324) |
| MA-HODDER-WB | **scanned** | 486 | 486 | 486* | `[Answer pending…]` (486) | filled |
| PH-CAMB-WB | **scanned** | 226 | 226 | 226* | `[Answer pending…]` | filled |
| PH-TSOKOS-WB | **scanned** | 600 | 600 | 600* | `[Answer pending…]` | filled |
| PH-OX-2023 | text | 182 | 182 | 182 | empty | filled |
| MA-OXFORD-2019 | text | 473 | 473 | 473 | `__AI_FILL__` (473) | `__AI_FILL__` (473) |
| MA-HAESE-AA2 / CORE1 | text | 999 / 643 | — | — | empty | filled |

`*qtext` for scanned books = literal `"[See question image. Source: …, page N.]"` — NOT OCR text.

## 2. Reports status (the 6 the user filed)
- 5 × `merged` on `MA-HAESE-CORE1`: **Q636, Q638, Q639, Q640, Q641** (all `status=open`).
- 1 × `missing-part` on `MATH-2024.5-P2-TZ1-q04` (v-t diagram clipped; `status=open`).
- The **"one still combining two questions"** = **`MA-HAESE-CORE1-Q636`**
  (detail: *"Two questions(14, 15 together!!!!!!!!!!!!!!"*). It is a **Haese Core** question,
  not HODDER — but it is the same merge-defect class as the HODDER images.

## 3. Diagnosis (done this session)
- `python reimport_book.py --book MA-HODDER-2019 --dry-run` → 324 questions, 0 merged,
  0 incomplete (heuristic: ≥2 top-level qnums / non-sentence-ending tail). **Text book is clean.**
- Inspected scanned HODDER/physics rows: `question_image` files **exist on disk**; `question`
  is a placeholder; `answer` is `[Answer pending…]`. Sample crops are 1 question per page
  (Q1@p4, Q2@p7, Q3@p12) — i.e. the *obvious* merges are not in those samples; the user's
  merged cases are likely sporadic (2 questions on one scanned page, or a clipped tail).
- **Regression trap:** re-running `reimport_book` on `MA-HODDER-2019` would REPLACE the 324
  image+text rows with 324 **text-only** rows (its `extract_text` path emits no `question_image`).
  Do NOT re-run the text book via reimport_book without first adding image generation.

## 4. Fix plan

### A. MA-HODDER-2019 (TEXT) — NO ACTION (already clean)
- Keep as-is. If images are desired, add a screenshot pass (don't let reimport_book drop them).

### B. Scanned workbooks (MA-HODDER-WB, PH-CAMB-WB, PH-TSOKOS-WB) — THE REAL FIX
Blocked on `easyocr`. Unblock:
1. `pip install numpy easyocr` (in the managed venv) — downloads OCR models (~hundreds of MB).
2. `python reimport_book.py --book MA-HODDER-WB --dry-run` → inspect `book_json/MA-HODDER-WB.json`.
   Quantify merge (a crop whose detected qnums ≥2) and clip (crop shorter than median / tail cut).
3. Tune `extract_books_scanned.py`: `is_answer_page()`, page-region detection, and the
   per-question crop boundaries so 2 questions never land in one crop and tails aren't clipped.
4. Re-extract + re-import (reimport_book preserves `well_down`). Re-verify merged rate ≈ 0.
5. Answers: these books HAVE answer-key PDFs (`answer_path`) → run the answer-matcher so
   `[Answer pending…]` is replaced with real answers.

### C. Answers (user question "why no answers?")
Root cause: `answer` is an **unfilled sentinel** for most books
(`__AI_FILL__` or `[Answer pending…]`). The fillers exist per-type —
`pair_answers.py` (Haese), `rebuild_physics_answers.py` (physics) — but only partially ran
(most books have `explanation`, not `answer`). No-key books (HODDER-2019, OXFORD-2019) were
never filled at all.
- Run `pair_answers.py` (Haese) → populate `answer` from worked solutions.
- Run `rebuild_physics_answers.py` (physics) → populate `answer` from answer-key PDFs.
- No-key books: AI-generate answers, or promote `explanation` → `answer` (confirm with user).
- **UX**: `QuestionCard.tsx` hides answers behind a "Show answer" toggle (default hidden).
  Even when filled, users must click to reveal. Recommend auto-revealing on book/practice
  pages or a global "reveal answers" setting.

## 5. Sequencing / gating (do not disturb the import pipeline)
1. Engine re-run for topic papers — **RUNNING in background** (task `H1eJAb`);
   finishes ~51 remaining topic PDFs (~2–4 h).
2. After (1): `node import_shots.mjs` (upserts manifest → adds new image questions).
3. After (2): `_task2_delete_orphans.py --execute` (removes the 8,053 text-only paper rows).
4. HODDER/workbook re-extraction (B) runs after `easyocr` is installed (independent of 1–3).
5. Restart backend on :3099 after all DB writes.

## 6. Open questions for user
- Can you point me to **one specific merged HODDER question** (ID or screenshot)? That lets me
  confirm whether it's the scanned-workbook crop vs. something else before I install `easyocr`.
- For no-key books (HODDER-2019, OXFORD-2019): OK to **AI-generate** answers, or prefer
  **promoting `explanation` → `answer`**?
- OK to **auto-reveal answers** in the UI (remove the default-hidden toggle) for book questions?
