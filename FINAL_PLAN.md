# FINAL PLAN — IB DP Question Bank Clean Rebuild

> **Status:** DB wiped (2026-08-24, 13,651 → 0 questions, 9 → 0 books; a 10th source book
> MA-PEARSON-2019 was added 2026-08-25, see §7). This file is the
> single source of truth for all future import sessions. Read it before starting any session.
>
> **Progress (2026-08-27 end-of-day update):** Sessions **0–11** base window + topics COMPLETE — *but note the original #7–9 "CS full 1999–2025" was wrong; only 2016–2025 P1/P2 (+0 P3) were actually in the DB.* **Sessions 12–17 (Math + Physics full history) DONE** (~2,424 added). **CS past gap-fill DONE 2026-08-27** — 544 rows added (P1 old 316 + P2 old 140 + P3 88); **2013 Nov P1 skipped per Rule #8** (markscheme mis-sequenced). See §10. **Session 18 (Math AA questions) DONE.** **Sessions 19–28 = the 10 books (pending)** — next actionable = Book 1 (MA-HODDER-2019) or CS Oxford 2025 (Book 9) per your direction.
>
> **Added 2026-08-27:** New source `Math AA questions.pdf` (1,590 pp, Pestle question-bank export) — **moved to Session 18** (in front of the books); the 10 book sessions renumbered 19–28. Has a mark scheme on the last hundreds of pages. See §8.

> **Added 2026-08-27 (expansion):** User wants ALL past papers, not just ~10 years. Gap quantified from the live DB vs the source folders: Physics HL missing **1999→2015** (source has 1999→2025); Mathematics HL missing **1995→2020 + 2024** (source has 1995→2024, tagged "Math HL" pre-2019 / "AA HL" 2019+). **CS past was NOT actually full** — only 2016–2025 P1/P2 were imported by #7–9; **1999–2015 P1/P2 and the ENTIRE P3 were missing.** That CS gap was filled 2026-08-27 (see §10); 2013 Nov P1 skipped per Rule #8. HL-only (no SL/AI past sources exist). See §9.
>
> **Operating contract (hard rules):**
> 1. **One session at a time. Never parallelise.** One subject/paper-type chunk = one session.
> 2. **STOP-AND-WAIT after every session.** When a session's extraction finishes, I stop and
>    present the result. I do **not** start the next session until you give the go-ahead.
> 3. **Research-first gate.** Every session opens with a research phase: study the material's
>    structure AND the text↔image relationship. I show the research, then wait for your command
>    to start detection/scan. No extraction happens before you approve.
> 4. **Idempotent, reversible.** Re-runs must be DELETE+INSERT (or upsert by stable id). Keep the
>    `app_pre_wipe_*` backup until the whole rebuild is verified.
> 5. **Past papers (and Math/Physics topic): ALWAYS keep BOTH the rendered page screenshot
>    (`question_image` / `answer_image`) AND the normalized text layer.** Past-paper structure
>    is clear, and both are needed — the screenshot is the visual source of truth (figures, layout,
>    exact notation), the text is for search, copy-paste, and math-normalized readability. Never
>    drop either, even if one looks "good enough". The DB row carries `question`/`answer` (text)
>    AND `question_image`/`answer_image` (comma-separated JPG paths under
>    `backend/public/figures/<paper>/`).

---

## 1. The session list (strict order)

| # | Session | Material | Extraction method |
|---|---------|----------|------------------|
| 0 | **DB wipe (DONE)** | all tables | — |
| 1 | Math — Paper 1 — past (DONE: 2021–2023 only) | AA/AI × HL/SL | text-layer |
| 2 | Math — Paper 2 — past (DONE: 2021–2023 only) | AA/AI × HL/SL | text-layer |
| 3 | Math — Paper 3 — past (DONE: 2021–2023 only) | AA/AI × HL/SL | text-layer |
| 4 | Physics — Paper 1 — past (DONE: 2016–2025) | HL/SL | text-layer |
| 5 | Physics — Paper 2 — past (DONE: 2016–2025) | HL/SL | text-layer |
| 6 | Physics — Paper 3 — past (DONE: 2016–2025) | HL/SL (options) | text-layer |
| 7 | CS — Paper 1 — past (base 2016–2025 from #7; **1999–2015 band added 2026-08-27 gap-fill**, 316 rows — 2013 Nov P1 skipped per Rule #8) | HL/SL | text-layer |
| 8 | CS — Paper 2 — past (base 2016–2020 + 2023–2025 from #8; **2000–2015 band added 2026-08-27 gap-fill**, 140 rows) | HL/SL | text-layer |
| 9 | CS — Paper 3 — past (**ENTIRE history added 2026-08-27 gap-fill**, 88 rows — 2023 May TZ1 skipped per Rule #8) | HL only | text-layer |
| 10 | Math — Topic questions (DONE) | per-topic/chapter | text-layer |
| 11 | Physics — Topic questions (DONE) | per-topic/chapter | text-layer |
| 12 | **Math — Paper 1 — FULL HISTORY (DONE: 2008–2024, 613 rows)** | AA HL 2021–2024 (156) + Math HL 2008–2020 (457) | text-layer (generalized Q/MS walker) |
| 13 | **Math — Paper 2 — FULL HISTORY (DONE: 2008–2024, 619 rows)** | AA HL 2021–2024 (155) + Math HL 2008–2020 (464) | text-layer (generalized Q/MS walker) |
| 14 | **Math — Paper 3 — FULL HISTORY (DONE: 2008–2024, 144 rows)** | AA HL 2021–2024 (24) + Math HL 2008–2020 (120) | text-layer (generalized Q/MS walker; floor N>=3) |
| 15 | **Physics — Paper 1 — FULL HISTORY (DONE: 2000–2015 added, 1,600 rows)** | HL 2000–2015 archive MCQ (2016–2025 already in #4) | text-layer (consolidated `extract_physics_old.py`) |
| 16 | **Physics — Paper 2 — FULL HISTORY (DONE: 2000–2015 added, 297 rows)** | HL 2000–2015 section-prefixed (A1./B1.) | text-layer |
| 17 | **Physics — Paper 3 — FULL HISTORY (DONE: 2000–2015 added, 770 rows)** | HL 2000–2015 option-prefixed (D/E/F/G…) | text-layer |
| 18 | Math AA questions (Pestle export) (DONE) | Math AA question-bank, born-digital | text-layer |
| 19 | Book 1 — MA-HODDER-2019 | Math AA HL Hodder | screenshot/old way |
| 20 | Book 2 — MA-HAESE-CORE1 | Math AA Haese Core 1 | screenshot/old way |
| 21 | Book 3 — MA-HAESE-AA2 | Math AA Haese AA2 | screenshot/old way |
| 22 | Book 4 — MA-OXFORD-2019 | Math AA HL Oxford | screenshot/old way |
| 23 | Book 5 — MA-HODDER-WB | Math AA Haese Workbook | screenshot/old way |
| 24 | Book 6 — PH-OX-2023 | Physics Oxford 5ed (TEXT) | screenshot/old way |
| 25 | Book 7 — PH-TSOKOS-WB | Physics Tsokos Workbook (scanned) | screenshot/old way |
| 26 | Book 8 — PH-CAMB-WB | Physics Cambridge Workbook (scanned) | screenshot/old way |
| 27 | Book 9 — CS-OX-2025 | CS Oxford 2025 | screenshot/old way |
| 28 | Book 10 — MA-PEARSON-2019 | Math AA HL Pearson 2019 (scanned, 1009pp) | screenshot/old way (OCR) |

**Book order is my choice** (foundational → applied, subject-balanced): Math core first (5 books:
Hodder, Haese Core1, Haese AA2, Oxford, **Pearson 2019**), then Physics (3), then CS (1), with 1 Math
workbook. Reorder freely before Session 19 — just tell me.

**CS has no topic-question session** (per the earlier hybrid decision: CS past *topic* questions are
not text-based and are out of scope for now). Only Math + Physics topic questions are imported.

---

## 2. Per-session workflow (every session follows exactly this)

### Phase A — Research (NO extraction yet)
1. **Inventory the source PDFs** for the session: list every file, its year/session
   (e.g. `2024 May`, `2024 November`), variant (AA/AI, HL/SL), and paper number.
2. **Probe the text layer** of 2–3 representative PDFs with `pypdfium2` — confirm it is
   born-digital TEXT (not scanned). *(Feasibility finding: Math/Physics/CS papers from ~2000/2002
   onward are text-based; only the oldest scanned outliers are not — and "past 10 years" is safely
   inside the text era for all three subjects.)*
3. **Map the question structure**: how questions are numbered (e.g. `1.`, `2. (a) (b)`, `Question 3`,
   per-section `1.`, `2.`), command terms, marks, subparts, and where each paper ends (mark scheme
   separate file, or combined).
4. **Research the text↔image relationship (critical for correct matching):**
   - Are figures inline in the question text, or on a separate page referenced by "Fig. 1"?
   - Does the text layer contain figure captions / labels we can anchor to?
   - For answers: is there a separate mark scheme with its own figures? How are answer figures
     keyed back to the question?
   - Decide the **matching rule** (e.g. "figure whose caption number == question number, rendered
     from the same page span as the question band").
5. **Show the research** (file inventory, text-sample, structure map, text↔image matching rule) and
   **STOP**. Wait for your command: `start` / `scan` / `detect`.

### Phase B — Extract (only after your approval)
6. **Text-layer path** (papers + Math/Physics topic): reuse `backend/ocr/booklib.py` patterns —
   segment by question-number regex on the text layer, render each question band to a JPG for
   `question_image`, attach the matched figure as `figure_image`/`answer_image` per the Phase-A rule.
   Store answer **text** from the mark scheme (TEXT-anchored, per the user directive), keyed by
   (paper, page, qnum).
7. **Book path** (the 9 books): use the existing `extract_books.py` / `reimport_book.py` (the
   "old way" — screenshot crops + `answer_image` from companion answer PDFs). PH-OX-2023 and
   MA-HAESE-CORE1 already have their gating/coloured-number fixes in place.
8. **Insert** via `insertQuestion` — which **auto-derives `category`** (book/past/topic/ai) and
   **defaults `review_status='new'`**, so every imported row lands in the "New coming" queue.
9. **Verify via DB queries**, never by eye (agent cannot view images): row counts per source,
   distinct figures, sample `question` text for sanity, matching coverage (questions with expected
   figure vs actual).

### Phase C — Hand back
10. Report counts + coverage + any anomalies, then **STOP**. You review in the app's "New coming"
    view, tell me adjustments, and give the go-ahead for the next session.

---

## 3. Extraction methodology

- **Past papers + Math/Physics topic = TEXT-LAYER** (the screenshot engine `run_corpus.py` was the
  root cause of "errors everywhere" — it is replaced by text extraction). Accurate, verifiable,
  and re-runnable. **Per Rule #5, every record keeps BOTH the rendered screenshot
  (`question_image`/`answer_image`) AND the text — never one without the other.**
- **Books = existing `extract_books.py` / `reimport_book.py`** (screenshot crops + answer images).
- **CS Paper 3** = the pre-release *case study* (HL only); research must confirm the yearly
  case-study PDFs and how they pair with the exam paper.
- All writes idempotent: re-running a session re-imports (DELETE+INSERT per book / upsert by stable
  manifest id for papers), so a bad session can be redone without manual cleanup.

## 4. "New coming" review loop (built into the app)

- Every fresh import is `review_status='new'` → visible under the **"New coming"** filter.
- You check each batch; click **✓ Mark reviewed** to set `review_status='done'`.
- Legacy rows are `NULL` (pre-rebuild), so the queue only ever shows *this* rebuild's imports.

## 5. Scope notes / open items (resolve during Phase A of the relevant session)

- **"Past 10 years"** definition: May 2016 → November 2025 (20 exam sessions). Math spans the
  pre-2019 (Math HL/SL) and post-2019 (AA/AI) guides — research must enumerate both and their
  paper structures. Physics/CS also span guide changes; confirm boundaries live.
- **Math variants**: AA-HL, AA-SL, AI-HL, AI-SL — each has P1/P2 (and P3 for HL). Treat as separate
  extracts within the session; do not merge across variants.
- **Physics P3** = options (A–D under the old guide; consolidated under the 2025 guide) — research
  the option structure per year.
- **CS P3** is HL case-study only.
- The 3 *scanned* workbooks (PH-TSOKOS-WB, PH-CAMB-WB, MA-HODDER-WB) rely on the screenshot/visual
  path; if OCR/visual splitting is needed it must be confirmed in Phase A of Sessions 18–20.

## 6. Do NOT

- Do not start the next session before approval.
- Do not parallelise sessions or scripts.
- Do not touch `knowledge_points`, `paper_templates`, `collections`, `exam_papers`, `topics`.
- Do not delete the `app_pre_wipe_*` backup until the whole rebuild is signed off.

---

## 7. Added 2026-08-25 — Book 10 (MA-PEARSON-2019)

- **Source file:** `../Mathematics HL - Analysis and Approaches (Pearson 2019).pdf`
  (in the parent `dp learning/` folder, **NOT** inside `ib-dp-platform/`).
  1,009 pages, ~484 MB, **scanned** (no text layer — probed 3 pages, 0 text).
  → Must use the **screenshot/old-way** extraction (OCR or visual band-splitting),
  same as the other books. It **cannot** use the text-layer path.
- **Companion answer source:** `../Pearson solutions/` — 16 chapter PDFs
  (Chapter 1–16; the ` (1)`-suffixed files are duplicate downloads — keep one copy each).
  Use as the `answer_image`/answer-text source for Book 10, mirroring how CS-OX used its
  companion answers book. Confirm the chapter↔question keying rule in Phase A of Session 22.
- **Why appended as Book 10 / Session 22:** keeps the original 9-book order untouched.
  If you'd rather it sit inside the Math-core group (e.g. alongside Hodder/Oxford), say so and
  I'll renumber the book list.
- **Note on `category`:** books import as `category='book'` via `insertQuestion` (auto-derived),
  so it becomes reviewable under the "New coming" queue like every other book session.

---

## 8. Added 2026-08-27 — Session 12: Math AA questions (Pestle export)

- **Source file:** `../Math AA questions.pdf` (in the parent `dp learning/` folder, **NOT** inside `ib-dp-platform/`). 1,590 pages, ~15.6 MB. Born-digital PDF exported from the `https://pestle.pages.dev/app/` question-bank (footer reads `Page X of 1,590`). Each PDF page = one Letter sheet, clean vector text + crisp figures (NOT a scanned book — the earlier "scanned" suspicion came from a probe that only sampled 8 pages).
- **Extraction method:** **text-layer** (NOT screenshot). The PDF is born-digital; the text layer is present and math glyphs render correctly. But see the hard research problem below.
- **The hard research problem (why the user flagged it):**
  - The Pestle export paginates by **sheet, not by question**, so **many questions are split across a page boundary**: the question text/header starts on page N and the figure + the remainder continue on page N+1.
  - **Confirmed example (PDF pp 0 → 1):** question `SPM.2.SL.TZ0.7` starts at the bottom of page 0 (opening text "Adam sets out for a hike…" + the start of a compass/N-arrow figure). Its figure is **literally sliced across the page break** — the triangle diagram and the N/B/C points finish on page 1, which then carries the subparts a–e. The figure is cut in half by the turning page = "even the graphic is affected by the turning page".
  - Therefore `question_image` cannot be a single page crop; it must be a **cross-page stitched render**. And `figure_image` for any split figure must **recombine the two page-halves into one figure**, not capture only one slice.
- **Phase A (research-first gate, BEFORE any extraction):**
  1. **Question detection across pages** — recognise a question whose header sits on page N but whose body + figure continue on page N+1 (likely signal: a question header near the bottom of a page whose subparts/figure continue on the next).
  2. **Figure stitching** — for a figure split across a page break, recombine the two page slices into one `figure_image` (vertical concat with overlap removal, or detect the cut-line).
  3. **`question_image` rendering strategy** — render the full span (page N tail + page N+1 head) as one image, or stitch the two page crops.
  4. **Question ID grammar** — headers look like `SPM.<n>.SL.TZ<x>.<y>` (e.g. `SPM.1.SL.TZ0.8`, `SPM.2.SL.TZ0.7`). Confirm the full grammar so question IDs are stable + unique (idempotent re-import).
  5. **Quantify** total question count + pages-per-question distribution (single vs 2-page vs ≥3-page).
  6. **Answer source** — **the export DOES include a mark scheme on the last hundreds of pages** (user-confirmed). So this is NOT questions-only. Research must confirm how the mark scheme is keyed back to each question (same `SPM.<…>` ID? grouped per paper?) and attach the answer text (and any answer figures) accordingly — like the past-paper flow — not `__AI_FILL__`.
- **Phase A findings (researched 2026-08-27, research-first gate met):**
  1. **Total questions = 746** (distinct question-ID headers in the question region, pages 0–586).
  2. **ID grammar = TWO families** (the original `SPM\.\d+\.(SL|HL)\.TZ\d+\.\w+` regex caught only 18/746 because real past-paper IDs use a second grammar):
     - `SPM.<paper>.<SL|HL>.TZ<tz>.<num>` — **18** "sample/test" questions (e.g. `SPM.1.SL.TZ0.8`, `SPM.2.SL.TZ0.7`).
     - `<YY>[MN].<paper>.<SL|HL|AHL>.TZ<tz>.<num>` — **728** real past-paper questions (e.g. `22M.2.AHL.TZ2.10`, `17M.1.SL.TZ1.S_9`, `18N.2.AHL.TZ0.H_9`). The trailing token carries an inline **topic tag**: `_H`/`_T`/`_S`/`_HSP` (HL / Trig / Stats / HL-SP) — e.g. `H_9` = HL topic, Q9. Stable-id regex: `(SPM\.\d+\.(?:SL|HL)\.TZ\d+\.\w+|\d{2}[MN]\.\d+\.(?:SL|HL|AHL)\.TZ\d+\.\w+)`. IDs are unique → safe for idempotent re-import.
  3. **Mark scheme IS present and keyed 1:1 by the SAME ID** (resolves the earlier `__AI_FILL__` assumption). MS region = **pages 587–1589**; the `Markschemes` divider title sits on page 587. Distinct MS IDs = **746**, with **zero orphans in either direction** (every question has an MS; every MS has a question). **Keying rule: join question ↔ MS by the exact ID string — no lookup table needed.** MS uses IB notation (`(M1)A1`, `[N marks]`, `valid approach`, `Award`, `METHOD`) and carries answer figures where needed.
  4. **Pages-per-question distribution** (header-to-header spans, question region):
     - 1 page (exclusive): **415**
     - 2 pages: **70** · 3 pages: **6** · 4 pages: **1** · 5 pages: **2**
     - 0-page "shared" (2+ headers on one sheet, question fully contained): **252**
     - **Cross-page (span ≥ 2) = 79 questions** — the figure-slicing risk set. Longest: `SPM.1.SL.TZ0.9` (4 pp), `22M.3.AHL.TZ1.2` (5 pp).
  5. **Cross-page figure stitching — method confirmed, QUANTITATIVE COUNT PENDING.** A question straddles a page break when span ≥ 2. A programmatic figure-detector was built: render the boundary page-pair → mask out text-char bounding boxes (`get_textpage().get_chars()`) → remaining ink = figure; a **straddle** = a figure on the lower page reaching the bottom edge AND a figure on the upper page starting at the top edge. **The straddle count (how many of the 79 slice a figure vs text-only overflow) could NOT be computed this turn — the sandbox shell died (exit 127) before the scan ran.** `figures.py` is written + ready at `/tmp/maq_probe/figures.py`; it is the **first validation step of Phase B**.
  6. **`question_image` / `figure_image` plan:** for each question, render its full page-span (head of first page → tail of last page) into one JPG for `question_image`; for any split figure, stitch the two page-halves into one `figure_image`. Per Rule #5 keep BOTH the stitched screenshot AND normalized text (text-layer math glyphs are correct → store `question`/`answer` directly; still apply `normalize_math()` PUA→Unicode for safety).
- **Placement note:** moved to **Session 18** (in front of the books) per user request 2026-08-27; the 10 book sessions were renumbered 19–28. `BOOK_FIX_PLAN.md` references books by code (PH-OX-2023, MA-HAESE-CORE1), not by session number, so no edits were needed there.
- **`category`:** `insertQuestion` auto-derives; closest fit is `past` (question-bank export, not a textbook and not the official topic set). Final choice to be confirmed in Phase A.

---

## 9. Added 2026-08-27 — Full-history past-paper expansion (Sessions 12–17)

**Why:** the user wants ALL past papers, not just the ~10-year window that Sessions 1–11 covered.

**Current state (live DB, 2026-08-27) — what's in vs what the sources hold:**

| Subject | In DB (HL) | Source folders span | Missing |
|---|---|---|---|
| Physics | 2016M→2025N (1,827 rows) | `Physics-HL-Past Papers&Mark Schemes(1999.05~2025.11)/` 1999→2025 | **1999→2015** (~33 exam sessions; 2020 May absent everywhere — COVID) |
| Mathematics | 2021M→2023N (335 rows) | `IB 数学 AA  HL 历年真题/` → `2024.5HL`, `2024.11HL` + `IB 数学 HL 真题（2006-23）/<YYYY Month>/` 1995→2023 | **1995→2020 + 2024** (~50 exam sessions) |
| CS | 2016M→2025N P1/P2 only + 0 P3 (563 rows) → **now full 1999→2025 (1,107 rows) after 2026-08-27 gap-fill** | `Computer Science-HL-Past Papers&Mark Schemes(1999.05~2025.05)/` 1999→2025 | was **1999→2015 P1/P2 + ALL P3** (~36 exam sessions) → **filled 2026-08-27** (544 added; 2013 Nov P1 skipped per Rule #8) |

> **Scope = HL only.** No SL / AI past-paper source folders exist in the workspace, so "all past papers" = all *HL* past papers available. If SL/AI sources exist elsewhere, point me at them and I'll add sessions.

**Source map (verified 2026-08-27):**
- **Physics:** `…/Physics-HL-Past Papers&Mark Schemes(1999.05~2025.11)/<YYYY Month Examination Session>/` — each year holds `Physics_paper_{1,2,3}_HL.pdf` + `…_markscheme.pdf` (older years, **no TZ in filename**) and, from ~2016 on, `Physics_paper_{1,2,3}__TZ1_HL.pdf` + `…_TZ2_HL.pdf` + `…_markscheme.pdf`. **Exclude `_French` / `_Spanish` variants** (English HL only).
- **Math:** `…/IB 数学 AA  HL 历年真题/` contains `2024.5HL/`, `2024.11HL/` (AA HL 2024) and the subfolder `IB 数学 HL 真题（2006-23）/<YYYY Month>/` holding **1995→2023** (the folder name says 2006-23 but actually starts at 1995). Pre-2019 years are the old **"Math HL"** guide (no AA/AI split); 2019+ are AA HL.

**Sessions (reuse the existing text-layer + screenshot pipeline — "the similar process"):**
- **#12 — Math P1 FULL HISTORY (DONE 2026-08-27, 613 rows):** AA HL 2021–2024 (156, incl. the previously-missing 2024) + Math HL 2008–2020 (457). New extractor `ocr/extract_math_hl_old_p1.py` derives the question COUNT from the markscheme and walks the QP by numbered questions (handles 2001–2006 no-`[Maximum mark]` / 2017–2019 per-paper-total / 2007–2016 & 2020–2024 modern uniformly). New importer `ocr/import_math_hl_old_p1.mjs`.
- **#13 — Math P2 FULL HISTORY (DONE 2026-08-27, 619 rows):** AA HL 2021–2024 (155) + Math HL 2008–2020 (464). Reused `extract_math_hl_old_p2.py` + `import_math_hl_old_p2.mjs`.
- **#14 — Math P3 FULL HISTORY (DONE 2026-08-27, 144 rows):** AA HL 2021–2024 (24) + Math HL 2008–2020 (120). Reused `extract_math_hl_old_p3.py` + `import_math_hl_old_p3.mjs`. P3 floor lowered to N>=3 (old P3 papers legitimately have only 4–5 questions); the `q==m==N` guard still blocks real garbage. **1 genuine skip:** 2018 Nov TZ0 (no markscheme file found).
- **Standing skip-rule (user 2026-08-27, now operating-contract Rule #8):** for EVERY subject, years that can't be reliably segmented are skipped — **NOT** OCR'd or given a custom MS-splitter. So **Math HL 2001–2007 and 1995–2000 are permanently OUT of scope** (old MS not delimited; 1995–2000 scanned). The reliable Math HL history band is **2008–2024** (1,376 rows across P1/P2/P3). This rule applies to Physics #15–17 too: skip old/complicated years, don't build bespoke parsers.
- **#15 / #16 / #17 — Physics P1 / P2 / P3 FULL HISTORY (DONE 2026-08-27, 2,667 rows):** added archive band **2000–2015** (DB had 2016–2025). New consolidated `ocr/extract_physics_old.py` + `ocr/import_physics_old.mjs`. Key findings: (a) **1999 is fully scanned** (text layer = 0) → skipped per Rule #8; (b) old P1 is MCQ but the markscheme key uses an en-dash `–` for unassessed items — parser accepts exactly 40 entries (letters or dashes); (c) old P2 questions are **section-prefixed** `A1.`/`B1.` (numbers RESET per section) and old P3 are **option-prefixed** (`D1.`/`E1.`…, old option letters D–J); both mirrored exactly by their markschemes. Result: **P1 1,600 + P2 297 + P3 770 = 2,667** new rows, all with answer + marks + images. **19 papers SKIPped** (Rule #8) — scattered genuine-reliability failures (a few P1 header/key gaps, 2013–2015 P2/P3 MS/Q misalignment). Totals now: Physics HL past P1=2,772 / P2=566 / P3=1,156.

**Idempotency (safe re-run):** the existing importers are DELETE+INSERT / upsert by stable manifest id. Pointing a session at the *full* year range re-imports the already-present years (2016–2025 Physics, 2021–2023 Math) with no change, and adds the older-year ids. The good data is never overwritten by the new batch.

**Phase A research gate (per session, BEFORE extraction — research-first rule):**
1. Probe text layer of 2–3 **old-year** PDFs (e.g. Physics 1999, Math 1997): confirm born-digital text. Plan note: papers from ~2000/2002 onward are text-based; **1999 and earlier may be scanned** → would need the screenshot/OCR path. Flag if so.
2. Old Physics: filenames lack TZ — decide how to derive TZ (many old papers are single/edition "TZ0"). Confirm `_markscheme.pdf` pairing.
3. Old Math "Math HL" pre-2019: question numbering, marks, command terms, subparts; settle the **id grammar** (`MATH_HL_P1_1997May_TZ?_qNN`?) and tagging (subject=`Mathematics`, level=`HL`; record the guide era in `source`/`topic` so it's filterable). Confirm 1995–1998 are text or scanned.
4. Confirm 2020 May is universally absent → skip silently, don't error.
5. Exclude non-English Physics variants (`_French`/`_Spanish`).
6. Keep `category='past'`; keep BOTH `question_image`/`answer_image` screenshots AND the normalized text (Rule #5).

**Expected volume:** Physics +1999–2015 ≈ up to ~2,000–2,400 added rows; Math +1995–2020 + 2024 ≈ a few thousand added rows. Total DB likely reaches ~11k–13k questions.

**Execution order:** one session at a time, STOP-AND-WAIT after each (present counts/coverage, wait for go-ahead). Start with **#12 (Math P1 full history)** once you approve the research plan. These are numbered 12–17 (past-paper phase, before the books at 19–28).

---

## 10. Added 2026-08-27 — CS past gap-fill (corrects the false "CS full" in #7–9)

**Why it was needed:** The original #7–9 were logged as "CS full 1999–2025" but only imported
**2016–2025 P1 (300) + 2016–2020 & 2023–2025 P2 (263) = 563 rows; P3 = 0.** The 1999–2015 P1/P2
band and the **entire** P3 history (case-study paper) were missing. User clarified (2026-08-27):
*"I want the CS past papers that weren't included."*

**Source:** `Computer Science-HL-Past Papers&Mark Schemes(1999.05~2025.05)/<YYYY Month Examination Session>/`
— same `paper_{1,2,3}_HL.pdf` + `…_markscheme.pdf` layout as Math/Physics (older years no TZ in filename).
Note: 2021/2022 source folders contain **only** Paper 1 + Paper 3 (no Paper 2 file) → no real P2 gap there.

**Deliverables (reusable Session-7 CS extractor, generalized):**
- `ocr/extract_cs_missing.py` — CLI `p1|p2|p3`; hardened `ms_starts()` (anchors on `Mark Allocation` / `Section A` / `Maximum total` / `Total N marks`; skips a leading `1.` that is a "follow the markscheme" instruction; broadened `MARKRE` to `[N]` / `[N mark]` / `[N marks]`).
- `ocr/import_cs_missing.mjs` — idempotent DELETE+INSERT per `source`; **CLI arg is `process.argv[2]`** (was a bug using `[1]` = script path).
- Manifests: `backend/data/cs_p1_old_manifest.json` (316), `cs_p2_old_manifest.json` (140), `cs_p3_manifest.json` (88).

**Result (live DB, 2026-08-27):** CS past now **P1=616 / P2=403 / P3=88 = 1,107 rows** (was 563).
- P1 old: 316 rows (2000 Nov → 2015 Nov, 19 papers; **2013 Nov P1 excluded** — see skip below).
- P2 old: 140 rows (2000 Nov → 2015 Nov, 20 papers).
- P3: 88 rows (2000 Nov → 2025 May TZ3, 22 papers; **2023 May TZ1 skipped** — markscheme repeats the question prompt instead of numbering answers).
- Coverage after cleanup: **0 empty answers, 0 missing images** (3,768 distinct figures, all on disk). 8 rows have `marks=0` (old papers where the mark count couldn't be extracted; answer text + image still present — acceptable).
- All 544 newly added rows flagged `review_status='new'`.

**Skips (standing Rule #8 — incompatible markscheme layout, skip rather than ship broken data):**
- **CS HL Paper 1 · 2013 November (entire paper, 17 Qs):** markscheme mis-sequenced — Q3's answer (a parity/checksum comparison table + `3. (a)(b)`) sits at the *top of page 4, before* the `SECTION A Total` / `1.`/`2.` numbering. The linear `1→2→3` walk captured only `{1,2}`, so q02 over-inclusively spanned to end-of-markscheme and q03–q17 had no answer. Removed all 17 rows + orphaned figures; excluded from manifest + added to `SKIP = {("p1","2013Nov")}` so re-extraction won't recreate it.
- **CS HL Paper 3 · 2023 May TZ1:** markscheme uses 0 line-start `1.` (repeats the prompt, no answer numbering) → `ms_starts` returns no anchorable starts → skipped wholesale.

**Verification:** import ran with backend stopped (avoid WAL lock); post-import DB counts + coverage + 0-missing-figure check all pass; API (`/api/questions?subject=CS&category=past&paper_type=Paper 3`) returns rows with `question_image`/`answer_image` + answer text; a sample figure served as `image/jpeg` (HTTP 200). Backend is agent-spawned and gets reaped by the sandbox when idle — relaunch with `cd backend && setsid sh start_backend.sh` for live serving.
