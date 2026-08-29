# SESSION 4 RESEARCH — Physics HL Paper 1 (past papers)

> **Status: RESEARCH ONLY.** No Physics Paper 1 extraction, manifest write, image render,
> or DB import has been started. This follows `FINAL_PLAN.md` Rule #3. Wait for `start` /
> `scan` / `detect` before Phase B.
>
> This session researches the Physics **HL** source set currently available in
> `Physics-HL-Past Papers&Mark Schemes(1999.05~2025.11)`. A separate Physics SL source
> set was not present in that folder and is not silently invented.

---

## 1. Scope and inventory

FINAL_PLAN defines the past-paper window as **May 2016 through November 2025**. The source
folder has no 2020 May examination folder (the May 2020 session was cancelled/absent), so
there are **34 English question-paper PDFs**, each with a paired English mark scheme:

- **2016–2024 old-format Paper 1:** 24 files × 40 multiple-choice questions = **960 records**.
- **2025 new-guide Paper 1A:** 5 files × 40 multiple-choice questions = **200 records**.
- **2025 new-guide Paper 1B:** 5 files, with 2 or 3 top-level structured questions per file =
  **12 records** if one DB record represents one top-level question and retains all subparts.
- Expected total under this record model: **1,172 records**.

Translation duplicates are excluded (French, Spanish, German). The source inventory is:

| Session | English Paper 1 files |
|---|---|
| 2016 May | `Physics_paper_1__HL.pdf` |
| 2016 Nov | `Physics_paper_1__HL.pdf` |
| 2017 May | `Physics_paper_1__TZ1_HL.pdf`, `Physics_paper_1__TZ2_HL.pdf` |
| 2017 Nov | `Physics_paper_1__HL.pdf` |
| 2018 May | `Physics_paper_1__TZ1_HL.pdf`, `Physics_paper_1__TZ2_HL.pdf` |
| 2018 Nov | `Physics_paper_1__HL.pdf` |
| 2019 May | `Physics_paper_1__TZ1_HL.pdf`, `Physics_paper_1__TZ2_HL.pdf` |
| 2019 Nov | `Physics_paper_1__HL.pdf` |
| 2020 Nov | `Physics_paper_1__HL.pdf` |
| 2021 May | `Physics_paper_1__TZ1_HL.pdf`, `Physics_paper_1__TZ2_HL.pdf` |
| 2022 May | `Physics_paper_1__TZ1_HL.pdf`, `Physics_paper_1__TZ2_HL.pdf` |
| 2022 Nov | `Physics_paper_1__HL.pdf` |
| 2023 May | `Physics_paper_1__TZ1_HL.pdf`, `Physics_paper_1__TZ2_HL.pdf` |
| 2023 Nov | `Physics_paper_1__TZ1_HL.pdf`, `Physics_paper_1__TZ2_HL.pdf` |
| 2024 May | `Physics_paper_1__TZ1_HL.pdf`, `Physics_paper_1__TZ2_HL.pdf` |
| 2024 Nov | `Physics_paper_1__HL.pdf` |
| 2025 May | `Physics_paper_1A_TZ1_HL.pdf`, `1A_TZ2_HL.pdf`, `1A_TZ3_HL.pdf`; `1B_TZ1_HL.pdf`, `1B_TZ2_HL.pdf`, `1B_TZ3_HL.pdf` |
| 2025 Nov | `Physics_paper_1A_TZ1_HL.pdf`, `1A_TZ3_HL.pdf`; `1B_TZ1_HL.pdf`, `1B_TZ3_HL.pdf` |

All 34 files have an English mark scheme using the matching filename plus
`_markscheme.pdf`. 2025 November has TZ1 and TZ3 in this source set; TZ2 is not present.

---

## 2. Text-layer viability

Representative probes covered the old format (2016), the old-format modern paper (2024),
and the new 2025 1A/1B formats. All are born-digital PDFs, not scanned page images.

| material | finding |
|---|---|
| 2016–2024 Paper 1 QP | Text layer present; 40 questions; maximum mark is `[40 marks]`. QP pages observed: roughly 17–29. |
| 2016–2024 mark schemes | Text layer present; compact answer-key grid, normally 2–3 pages. Rows contain entries such as `1. B`, `16. C`, …; unused 41–60 slots appear as dashes even though the paper has 40 questions. |
| 2025 Paper 1A QP | Text layer present; 40 multiple-choice questions; maximum mark `[40 marks]`. QP has a separate 1A paper title. |
| 2025 Paper 1A mark scheme | Compact answer-key grid, same qnum→A/B/C/D mapping as the old format. |
| 2025 Paper 1B QP | Text layer present; calculator-required structured/data-analysis paper; maximum `[20 marks]`; top-level question count varies by zone paper: 3 in 2025.05 TZ1 and 2025.11 TZ1, 2 in 2025.05 TZ2/TZ3 and 2025.11 TZ3. |
| 2025 Paper 1B mark scheme | Text layer present; detailed table with `Question`, `Answers`, `Notes`, `Total` columns. Rows are smallest subparts (`1 a`, `1 b i`, etc.), not one row per top-level question. |

### Question-header detector research

The simple line-start pattern is insufficient because pypdfium2 sometimes emits the next
question immediately after an answer-option line, separated by the PDF object-order marker
U+FFFE rather than a newline. Example cases found:

- 2017 May TZ2: Q20 follows Q19's option text on the same extracted line.
- 2020 Nov: Q23 follows Q22's option text on the same extracted line.
- 2023 Nov: Q21 follows Q20's option text on the same extracted line.

A safe QP candidate detector for the old format and 2025 1A is:

```python
qp_qhead = re.compile(
    r'(?m)(?:^|[\\r\\n\\ufffe])\\s*(\\d{1,2})\\.(?!\\d)\\s+'
)
```

The strict walker accepts only `num == expected` (1→40). This was tested against all 24
old-format QPs and all five 2025 1A QPs: **40/40 on every file**. The U+FFFE alternative is
important; the old line-anchored detector falsely stalled on the three inline-header cases.

For 2025 1B, use the same separator-aware pattern but stop at the last consecutive top-level
question (`1`, `2`, optionally `3`) rather than assuming 40. Subparts `(a)`, `(b)(i)`, etc.
remain inside the top-level question record.

---

## 3. Paper structure and answer structure

### A. Old format (2016–2024) and new 2025 Paper 1A

- Paper is entirely multiple choice.
- **40 top-level questions**, numbered `1.` through `40.`.
- Each question contains a stem, often a diagram/graph/equation, followed by choices A–D.
- No subpart records; one DB question corresponds to one MC item.
- The QP instruction says to answer on a separate answer sheet.
- The mark scheme is not a narrative solution: it is a compact answer key. The stable mapping
  is `qnum → one of A/B/C/D`.
- For the normalized answer text, store a direct answer such as `1. B` (option key), while
  the screenshot remains the visual source of the exact question and answer key.

### B. New 2025 Paper 1B

Paper 1B is structurally different and must not be forced through the 40-MC extractor:

- It is a **20-mark structured/data-analysis paper**, still part of the 2-hour Paper 1A + 1B
  sitting and calculator-required.
- Questions are long and multi-page, with subparts and answer boxes.
- Top-level counts by file are:

| file | top-level Qs | structure observed |
|---|---:|---|
| 2025 May TZ1 | 3 | Q1 measurement/uncertainty; Q2 refraction/graph; Q3 Earth magnetic field |
| 2025 May TZ2 | 2 | Q1 resistivity/uncertainty; Q2 ideal-gas graph/data |
| 2025 May TZ3 | 2 | Q1 nail-depth experiment; Q2 double-slit wavelength experiment |
| 2025 Nov TZ1 | 3 | Q1 measurement/uncertainty; Q2–Q3 structured investigations |
| 2025 Nov TZ3 | 2 | Q1 density/viscosity investigation; Q2 Stefan–Boltzmann investigation |

- The question paper includes `(Question N continued)` and deliberate blank answer pages
  saying `Please do not write on this page. Answers written on this page will not be marked.`
- The mark scheme groups multiple rows under each top-level question, with granular rows such
  as `1 a`, `1 b i`, `1 c ii`. It includes accepted alternatives, notes, ECF guidance, and
  per-subpart totals. The correct DB record model is one record per top-level Q1/Q2/Q3,
  concatenating all its mark-scheme subpart rows into that record's normalized `answer` text.
- One 2025 May TZ2 mark scheme uses a compact table header `Q Answers Notes Total` and no dot
  in its first-column rows (`1 a`), while other 1B mark schemes use `Question Answers Notes Total`
  and forms such as `1. a`. The extractor must support both table-header/row variants.

---

## 4. Text ↔ image relationship

### Question papers

Figures, graphs, diagrams, tables, and answer-choice layouts are inline with the question
stems. They are not separate caption-number files. The text layer contains labels and chart
text, but it is not a reliable visual representation of the layout or math/physics symbols.

The PDF object probe found **36 raster image objects across 6 QPs** in the 34-file inventory,
including fragmented/tilled diagram assets in some 2025 papers. The rest of the diagrams are
vector PDF content. Therefore a text-only record would lose visual information even when the
text layer is present.

### Mark schemes

- Old-format and 2025 1A key pages are primarily text/tabular answer keys.
- 2025 1B mark schemes are detailed tables; at least three raster image objects were found in
  two 1B mark schemes (2025 May TZ2/TZ3). These may be answer graphs/diagrams and must not be
  discarded.
- The rendered answer image remains the source of truth for graph/diagram marking points and
  table layout, even when normalized answer text is available.

### Matching rule for extraction

1. **QP:** detect each top-level header on the text layer, using the separator-aware regex and
   strict monotonic walker. Use the question's text coordinates/page span to render a
   question-region screenshot. Because old/P1A pages often contain multiple MC questions, do
   **not** rely on a whole-page-only crop if it would make the record ambiguous: crop the
   question's vertical band on each page and expand the band to include inline vector/raster
   objects. Keep the U+FFFE header case in the detector.
2. **Old/P1A answer:** parse the compact MS grid into `qnum → A/B/C/D`. Store that normalized
   mapping as answer text. Render the MS key page(s) containing the mapping as `answer_image`;
   multiple questions may legitimately reference the same key page.
3. **2025 1B answer:** find the first mark-scheme table after the instruction/rubric pages;
   group rows by top-level qnum (`1`, `2`, optionally `3`) while retaining all subpart labels,
   accepted alternatives, notes, and totals in answer text. Render the corresponding MS table
   page span as `answer_image`. Do not let rubric lines 1–14 before the table become questions.
4. **Blank spacer pages:** exclude intentional `Please do not write on this page` pages from
   answer-image lists unless a real diagram/object is present; they contain no answer content.
5. Stable IDs should include format and zone to prevent collisions, for example:
   - `PHYS_HL_P1_<slug>_qNN` for old/P1A MC records
   - `PHYS_HL_P1B_<slug>_qNN` for structured 2025 P1B records
6. Keep **both** normalized text and screenshot fields in every record, per FINAL_PLAN Rule #5.
   Do not populate separate `figure_image` fields merely because a figure is inline; the
   question-region screenshot is the authoritative visual attachment.

---

## 5. Verification plan after approval

- Inventory assertion: 34 QP/MS pairs, no missing English mark scheme.
- Old/P1A detection assertion: 29 files × 40 MC questions = 1,160 records.
  (24 old-format files + 5 Paper 1A files.)
- P1B detection assertion: 5 files × (3, 2, 2, 3, 2) = 12 top-level records.
- Expected total: **1,172 records**.
- Every record must have nonempty `question` and `answer` text.
- Every record must have both `question_image` and `answer_image` references, and every referenced
  file must exist on disk.
- Old/P1A answer invariant: each qnum 1–40 has exactly one parsed A/B/C/D choice.
- P1B answer invariant: each top-level qnum's answer starts with its own qnum and includes all
  expected subpart rows; no rubric instruction row is treated as a question.
- No residual PUA math/physics glyphs after normalization, or explicitly report any unmapped
  codepoints.
- DB rows should be `category='past'`, `review_status='new'`, `paper_type='Paper 1'`, with
  `Paper 1B` retained in the source/ID distinction.
- Stop after verification and hand back the counts/anomalies for review.

---

## 6. Decision gate

This document completes Phase A research. **No Physics Paper 1 extraction has started.**

The main implementation decision is the two-format extractor:

- old/P1A: 40 MC records + compact answer-key parser;
- 2025 P1B: 2–3 top-level structured records + detailed mark-scheme table parser.

Reply `start` / `scan` / `detect` to approve Phase B, or specify whether to include a future
Physics SL source set when it becomes available.
