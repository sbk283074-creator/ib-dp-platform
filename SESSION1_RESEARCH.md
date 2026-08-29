# Session 1 Research — Math AA HL Paper 1 (Past Papers)

**Status:** RESEARCH ONLY — no extraction performed. Waiting for user command to start detection/scan.
**Date:** 2026-08-25
**Scope lock:** Analysis & Approaches HL (`analysis_and_approaches`), English language only, Paper 1.
**Source folder:** `/Users/lucas.ma/Downloads/dp learning/IB 数学 AA  HL 历年真题`

---

## 1. Scope reality (important gap to confirm)

The "past 10 years" target (per FINAL_PLAN = May 2016 → Nov 2025) **cannot be met literally for AA**, because:

- **AA did not exist before first exams in May 2021.** The new "Mathematics: analysis and approaches" curriculum replaced the old "Mathematics HL" guide. The archive's pre-2021 `Mathematics_paper_1__TZx_HL.pdf` files are the OLD Math HL, **not AA** → excluded per your "AA only" instruction.
- **2025 papers are not in the archive.** Newest file is `2024.11HL`. So 2025 is simply absent.

**Therefore Session 1 = the complete AA HL Paper 1 English set that exists: 2021 May → 2024.11.**

If you instead want the *old Math HL* P1 for 2016–2020 folded in, that is a separate variant (different curriculum, same extraction method) — say the word and I'll treat it as its own sub-session.

## 2. File inventory (13 question PDFs + 13 mark schemes, 1:1)

| # | Session | File (basename, identical across folders) | QP | MS |
|---|---------|-------------------------------------------|----|----|
| 1 | 2021 May TZ1 | `Mathematics_analysis_and_approaches_paper_1__TZ1_HL.pdf` | ✓ | ✓ |
| 2 | 2021 May TZ2 | `…_TZ2_HL.pdf` | ✓ | ✓ |
| 3 | 2021 Nov | `…_HL.pdf` | ✓ | ✓ |
| 4 | 2022 May TZ1 | `…_TZ1_HL.pdf` | ✓ | ✓ |
| 5 | 2022 May TZ2 | `…_TZ2_HL.pdf` | ✓ | ✓ |
| 6 | 2022 Nov | `…_HL.pdf` | ✓ | ✓ |
| 7 | 2023 May TZ1 | `…_TZ1_HL.pdf` | ✓ | ✓ |
| 8 | 2023 May TZ2 | `…_TZ2_HL.pdf` | ✓ | ✓ |
| 9 | 2023 Nov TZ1 | `…_TZ1_HL.pdf` | ✓ | ✓ |
| 10 | 2023 Nov TZ2 | `…_TZ2_HL.pdf` | ✓ | ✓ |
| 11 | 2024.5 TZ1 | `…_TZ1_HL.pdf` | ✓ | ✓ |
| 12 | 2024.5 TZ2 | `…_TZ2_HL.pdf` | ✓ | ✓ |
| 13 | 2024.11 | `…_HL.pdf` | ✓ | ✓ |

**Excluded (present in same folders, must be filtered out):** French/Spanish/German language variants (`_HL_French.pdf`, `_HL_Spanish.pdf`, `_HL_[German].pdf`), and the **Applications & Interpretation** variant (`Mathematics_applications_and_interpretation_*`).

**Per-paper shape:** 12 questions, ~110 total marks. Section A = Q1–Q9 (shorter, answer boxes), Section B = Q10–Q12 (longer, answer booklet). Mark scheme PDF is a separate file (`*_markscheme.pdf`), 1:1 with the question paper.

## 3. Document anatomy

**Question paper (QP):**
- Page 1: copyright + IB license. Page 2: session header + instructions (e.g. `M21/5/MATHX/HP1/ENG/TZ1/XX`, "No calculator", Section A/B).
- Questions are numbered `1. [Maximum mark: 5]` … `12. [Maximum mark: 20]`.
- Subparts use `(a)`, `(b)`, `(i)`, `(ii)` with inline marks like `[2]`.
- Diagrams referenced as "the following diagram" / "the diagram below" are drawn **inline** in the question block.

**Mark scheme (MS):**
- Pages 1–~7: front matter (copyright, "Instructions to Examiners", abbreviations M/A/R/AG/FT, examples).
- Then questions 1–12 in order, each starting with `N. ` (sometimes `N METHOD 1`, e.g. `2 METHOD 1`), with M1/A1 annotation lines and `Total [N marks]` at the end of each.

## 4. Text layer finding (the decisive one)

Probed with `pypdfium2` on 2021/2023/2024 papers:
- **Every page is born-digital TEXT** (non-trivial text on all pages) → text-layer extraction is reliable, no OCR needed.
- **Paper 1 contains ZERO raster images.** All figures (graphs, axes, geometric diagrams) are **vector paths** embedded in the page content stream.
- Render test: page 3 of 2021 May (Q1 with the `f(x)` graph) rasterizes to 1241×1754 px @150 DPI (~226 KB) — vector diagram + text captured together.

**Consequence for the text↔image relationship:** there are no separate image *files* to associate. The correct matching rule is **spatial, not file-based**: a question's image = the rendered raster band of the page region it occupies. Because the diagram is drawn inline within that region, rendering the region captures text **and** diagram in one image.

## 5. Text↔Image matching rule (proposed)

For each question, compute its vertical page span and render it to a JPG:

- Find the page where the question header `N. [Maximum mark: …]` appears.
- The question occupies from that header down to the next question header (or end of paper). Render **every page in that span**, cropped to the relevant band, concatenated vertically → one `question_image` JPG.
- This captures multi-page Section B questions (Q10–12 often span 2 pages) intact, including any vector diagram.
- Render at ~150 DPI (good balance of legibility vs. storage). Optional: also render the matched MS segment as a second image for the answer side (stored as `answer_image` or just kept as text).

No figure-caption parsing, no image-object matching needed — the diagram lives inside the text block by construction.

## 6. Text↔Answer (mark scheme) matching rule (VERIFIED)

The MS is a separate PDF. Pairing is **by question index**, not by content matching (the MS does NOT restate question stems verbatim — confirmed: QP stems not found in MS).

**Verified algorithm (tested on all 13 papers → exact 1:1):**

1. **QP segmentation** (trivial, reliable):
   `regex (?m)^\s*(\d+)\.\s*\[Maximum mark: (\d+)\]` → yields N questions with `question_number`, `marks`, `question_text` (stem up to next header).
2. **MS segmentation** (robust, paper-independent):
   - Anchor at the **last occurrence of `"Presentation of candidate work"`** (the final front-matter item, present in every AA MS; universal end-of-front-matter signal).
   - Walk line-start numbers with `regex (?m)^\s*(\d+)\b`, strictly increasing 1,2,3,…, **capped at N** (the QP question count).
   - This yields exactly N answer segments, indexed 1..N.
3. **Pair**: QP question `n` ↔ MS segment `n`.

**Why this handles the edge cases we hit:**
- 2024.11 MS uses uppercase `SECTION A` and its front matter numbers 1–10 collide with real questions → the "Presentation of candidate work" anchor skips all front matter.
- Some MS headers are `2 METHOD 1` (no dot) → `(?m)^\s*(\d+)\b` (number + word boundary) catches them, unlike `^\d+\.`.
- Nov papers contain a stray `13` line inside Q12's answer → capping the walk at N=12 prevents a phantom Q13 and keeps Q12's segment intact to end-of-MS.
- MS segments carry trailing page-header artifacts (`– 9 – M21/5/…/M`) → strip these during cleaning.

**Result:** all 13 papers → QP count == MS segment count == 12, with correct first/last lines. Pairing is exact.

## 7. Answer-side image structure (mark scheme) — RESEARCHED, important

The user asked specifically to check whether the **answer / mark scheme** contains images. It does.

**Probed all 13 MS PDFs with pypdfium2 (image objects, `get_px_size()` + `get_bounds()`):**

- **The QUESTION papers have 0 raster images** (diagrams are vector — confirmed earlier).
- **The MARK SCHEMES contain raster images.** Two distinct classes:
  1. **Diagram-sized images = 22 total across the 13 papers** (real answer figures). Representative sizes:
     318×375 (5.5% area), 543×525 (7.4%), 896×915 (17.5%), 839×693 (12.4%),
     1099×1120 (31.9%), 1546×723, 1851×1000 (21.3%), 1325×1377 (20.9%), 739×727 (11.5%),
     700×699 (10.5%) … These are the **worked-solution graphs/sketches/geometric figures**
     embedded in specific questions' answers.
  2. **Tiny 2×2 px "icons" = 32 total** (area ~0.1–2%). Negligible artifacts (tick/dot glyphs,
     anti-alias speckle). Safe to ignore.
- **Per-paper prevalence of real answer diagrams:** ~1–4 questions each. Examples of questions
  that carry an answer diagram: 2021 May TZ1 → Q1, Q2, Q6; 2021 Nov → Q4, Q10, Q12;
  2023 Nov TZ2 → Q3, Q10, Q11; 2024.5 TZ1 → Q4, Q5, Q7, Q8, Q12; etc. Roughly **14% of all
  questions (22 of 156) have an embedded answer diagram.**

**Implication:** answer text alone would LOSE ~22 diagrams (the exact thing the user warned about).
The correct matching rule for answer images:

- Each diagram-sized raster image lives on a specific MS page; attribute it to the question whose
  MS region (on that page) vertically contains the image's top position (refine within-page splits
  by question boundaries). Questions with no diagram-sized image and no vector diagram → no
  `answer_image` needed (text suffices).
- **Robust "both ways" fallback (recommended):** render the MS answer region (the page span of
  question n's solution) to an `answer_image` PNG. This single render captures BOTH embedded raster
  diagrams AND any vector sketch drawn in the solution — zero risk of missing a visual. Cost: a few
  hundred KB per question; harmless duplicate of the answer text for diagram-free questions.

**DB mapping (columns already exist):** `answer` ← MS solution text; `answer_image` ← rendered MS
region PNG path (or extracted diagram). (`answer_figure` / `figure_image` also exist if needed.)

## 8. Proposed extraction pipeline (to run AFTER approval)

For each of the 13 papers:
1. Load QP + MS with `pypdfium2`.
2. Segment QP → questions (number, marks, stem text, page span).
3. Render each question's page span → JPG (`question_image`).
4. Segment MS (capped at N) → answer text, pair by index.
5. Insert each question row:
   - `source_type = 'paper'`, `source = 'AA HL P1 · <year> <Month> <TZ>'` (e.g. `AA HL P1 · 2021 May TZ1`)
   - `category = 'past'`, `review_status = 'new'`
   - `question_number`, `marks`, `question` (text), `question_image` (rendered QP region)
   - `answer` (MS solution text), `answer_image` (rendered MS region — captures embedded diagrams)
   - A `book_id` per paper (one books row per paper) — *decision, see §9*.
6. **Idempotent:** DELETE+INSERT per paper (or upsert by stable manifest id = `source + question_number`) so re-runs never duplicate.

## 8. Sanity checks built in
- QP question count must equal MS segment count (==12 typically); fail the paper if not.
- Sum of `[Maximum mark: …]` should be ~110.
- Every inserted row gets `review_status='new'` → lands in the "New coming" review queue for you to check.

## 9. Open decisions for you
1. **Confirm the scope gap:** Session 1 = 2021 May → 2024.11 AA HL P1 only (13 papers). OK, or also include old Math HL 2016–2020 as a separate variant? (2025 not available.)
2. **book_id strategy:** one `books` row per paper (13 rows) vs. one row per session (1 row grouping all 13). I recommend **one row per paper** for clean per-paper filtering.
3. **Answer image:** research confirms ~22 real answer diagrams exist across the 13 papers, so answer
   text alone would lose them. Recommended: store **both** `answer` (text) **and** `answer_image`
   (rendered MS region) for every question — guaranteed completeness. Alternative: only render
   `answer_image` for the ~22 questions that actually contain a diagram-sized raster image (leaner
   storage, but risks missing any vector-only sketch). **Please confirm which.**

## 10. Risk register
| Risk | Status |
|------|--------|
| Non-AA / non-English files leaking in | Filename filter handles it (verified 13/13 English AA) |
| Raster images needing separate matching | N/A — Paper 1 has none; vector diagrams captured by region render |
| MS front-matter false question numbers | Solved via "Presentation of candidate work" anchor |
| `N METHOD` headers without dot | Solved via `(?m)^\s*(\d+)\b` |
| Stray number lines inside an answer | Solved via capping walk at N |
| Multi-page Section B questions | Handled by page-span concatenation |
| Re-run duplication | Handled by idempotent DELETE+INSERT / upsert |
| **Answer diagrams missed (text-only)** | SOLVED: MS contains 22 raster answer diagrams; store `answer_image` (rendered MS region) for every question |

---
*No data has been written to the database. This document is research only.*

## Status — EXTRACTION COMPLETE (2026-08-25)
User approved extraction with the recommended defaults (scope 2021 May→2024.11 AA only; one
books row per paper N/A since `questions` has no `book_id` FK; store both `answer` text + `answer_image`).
- **Extractor:** `backend/ocr/extract_paper_aa_p1.py` (pypdfium2 text-layer + page-region render).
  Writes JPGs to `backend/public/figures/paper_aa_hl_p1/<slug>/` and a manifest to
  `backend/data/paper_aa_p1_manifest.json`.
- **Importer:** `backend/ocr/import_paper_aa_p1.mjs` (uses `questionRepo.insertQuestion`;
  DELETE per source + INSERT OR REPLACE, idempotent).
- **Result:** 156 questions across 13 papers, all `category='past'`, `review_status='new'`.
  514 image files (question + answer regions) on disk, 0 missing references. Verified live
  via `GET /api/questions?category=past&review_status=new` → total 156.
- **Known minor issue (cosmetic, text only):** question/answer text retains page footers
  ("Please do not write on this page", "Turn over", session code "2221–7106", "12EP0x").
  Images are correct. Fix = extend `clean()` in the extractor and re-run (idempotent). Awaiting
  user go-ahead to apply, or proceed to next session.
- **Orphaned files:** `backend/public/figures/` still holds ~old screenshot-engine JPGs from the
  pre-wipe wrong-tool run (unreferenced by DB). Safe to delete on request.
