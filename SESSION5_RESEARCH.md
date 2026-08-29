# SESSION 5 RESEARCH — Physics HL Paper 2 (past papers)

> **Status: RESEARCH ONLY.** No Physics Paper 2 extraction, manifest write, image render,
> or DB import has been started. This follows `FINAL_PLAN.md` Rule #3. Wait for `start` /
> `scan` / `detect` before Phase B.
>
> This session covers the available Physics **HL** source set. No Physics SL source folder
> is present in the project, so SL is not silently invented.

---

## 1. Scope and source inventory

The FINAL_PLAN past-paper window is May 2016 through November 2025. The source folder has no
2020 May directory (May 2020 was cancelled/absent). Translation duplicates are excluded.
There are **29 English Paper 2 question-paper / mark-scheme pairs**, all paired by the same
filename plus `_markscheme.pdf`.

| Session | English Paper 2 files | QP questions per file | Max |
|---|---|---:|---:|
| 2016 May | `Physics_paper_2__HL.pdf` | 11 | 95 |
| 2016 Nov | `Physics_paper_2__HL.pdf` | 11 | 95 |
| 2017 May | `Physics_paper_2__TZ1_HL.pdf`, `…TZ2_HL.pdf` | 9, 8 | 95 |
| 2017 Nov | `Physics_paper_2__HL.pdf` | 8 | 95 |
| 2018 May | `Physics_paper_2__TZ1_HL.pdf`, `…TZ2_HL.pdf` | 8, 9 | 95 |
| 2018 Nov | `Physics_paper_2__HL.pdf` | 9 | 95 |
| 2019 May | `Physics_paper_2__TZ1_HL.pdf`, `…TZ2_HL.pdf` | 8, 11 | 90 |
| 2019 Nov | `Physics_paper_2__HL.pdf` | 11 | 90 |
| 2020 Nov | `Physics_paper_2__HL.pdf` | 10 | 90 |
| 2021 May | `Physics_paper_2__TZ1_HL.pdf`, `…TZ2_HL.pdf` | 10, 10 | 90 |
| 2022 May | `Physics_paper_2__TZ1_HL.pdf`, `…TZ2_HL.pdf` | 9, 9 | 90 |
| 2022 Nov | `Physics_paper_2__HL.pdf` | 10 | 90 |
| 2023 May | `Physics_paper_2__TZ1_HL.pdf`, `…TZ2_HL.pdf` | 8, 9 | 90 |
| 2023 Nov | `Physics_paper_2__TZ1_HL.pdf`, `…TZ2_HL.pdf` | 8, 8 | 90 |
| 2024 May | `Physics_paper_2__TZ1_HL.pdf`, `…TZ2_HL.pdf` | 11, 10 | 90 |
| 2024 Nov | `Physics_paper_2__HL.pdf` | 11 | 90 |
| 2025 May | `Physics_paper_2_TZ1_HL.pdf`, `…TZ2_HL.pdf`, `…TZ3_HL.pdf` | 9, 8, 8 | 90 |
| 2025 Nov | `Physics_paper_2_TZ1_HL.pdf`, `…TZ3_HL.pdf` | 8, 10 | 90 |

Expected top-level records, using one DB record per numbered question: **269**.

The count is variable by session because Paper 2 is a structured written paper: each paper
allocates its total marks differently across long questions. It is not a fixed 40-question
multiple-choice format like old Paper 1.

---

## 2. Text-layer and PDF-object viability

Representative probes covered 2016, 2021, 2024, and 2025 files; the full 29-file probe then
checked counts and page/object signals.

| signal | finding |
|---|---|
| QP text layer | Born-digital text in all 29; no scanned-paper exception found. QP pages range 20–33. |
| MS text layer | Born-digital text in all 29; MS pages range 14–27. |
| QP raster objects | Very sparse: **6 raster image objects across 3 QPs** in the 29-file inventory. Most diagrams/graphs are vector PDF content. |
| MS raster objects | Common enough to matter: **many MS files contain embedded raster answer graphs/diagrams** (the probe found up to 16 objects in one 2025 MS; 2025 TZ3 had 13). Keep full answer screenshots. |
| Spacer pages | QP contains intentional `Please do not write on this page` answer-space pages in many sessions. MS spacer pages were not observed in the same form. |
| PUA symbols | QP PUA is low (0–13 per file); MS PUA can be substantial (0–381 per file). Use the Physics normalization map; rendered screenshots remain visual truth. |

**Conclusion:** Paper 2 is text-extractable, but text alone is not sufficient. Per FINAL_PLAN
Rule #5, every record must keep both normalized text and rendered question/answer images.

---

## 3. Question structure and detection rule

### Question-paper structure

- Questions are numbered sequentially from `1.` to the paper's final question.
- Number of top-level questions varies from **8 to 11**.
- Questions are long and multi-part. Subparts include `(a)`, `(b)`, `(i)`, `(ii)`, diagrams,
  graphs, calculations, explanations, and data analysis.
- Some older papers have only a few questions marked with `(a)` while other questions are
  single stems with their own internal parts. The top-level numbered question remains the
  correct DB unit.
- 2025 papers continue the same top-level model; they are not Paper 1B-style separate papers.
- QP maximum is 95 marks through 2018 and 90 marks from 2019 onward.

### Validated QP header detector

pypdfium2 sometimes emits adjacent PDF text objects separated by U+FFFE rather than a newline.
The validated candidate pattern is:

```python
qp_head = re.compile(
    r'(?m)(?:^|[\\r\\n\\ufffe])\\s*(\\d{1,2})\\.(?!\\d)\\s+(?=[A-Z(])'
)
```

The strict monotonic walker accepts only `num == expected`, starting at 1 and stopping at the
last consecutive number. This resolved the expected sequential count for **all 29 QPs**:

```text
29/29 files balanced; QP count total = 269
```

The `(?=[A-Z(])` guard allows normal stems and headers beginning with `(a)`, while excluding
numeric diagram labels and decimal-like text.

### Mark-scheme structure

The mark scheme is a detailed table, not a compact answer key. It contains:

```text
Question | Answers | Notes | Total
```

Rows refer to the smallest subpart, for example:

```text
1 a i
1 b ii
2. a
3 d i
```

Both row styles occur:

- `1. (a)` / `1. a i`
- `1 a` / `1 a i`

Some papers use `ALTERNATE 1`, `ALTERNATE 2`, `OR`, ECF guidance, and `[n]` totals.
Rubric/instruction pages appear before the first actual answer table. The safe MS rule is:

1. Find the first `Question Answers Notes Total` (or equivalent table header) after the
   introductory rubric pages.
2. Scan rows with a separator-aware pattern accepting both dotted and no-dot forms:

```python
ms_row = re.compile(
    r'(?m)(?:^|[\\r\\n\\ufffe])\\s*(\\d{1,2})\\.?\\s+(?=[a-z(])'
)
```

3. Use the strict expected-number walker to identify the first row for top-level Q1, then the
   first row for Q2, and so on. Repeated rows with the same number are subparts within that
   question, not new question boundaries.

The corrected detector resolves the first top-level row for every expected question in all
29 mark schemes: **29/29 balanced, 269/269 answer spans**.

---

## 4. Text ↔ image relationship and matching rule

### Question images

Physics Paper 2 questions contain inline diagrams, graphs, circuit layouts, tables, and
calculation notation. Most are vector PDF objects, so an object-only raster search is not a
sufficient matching method. The screenshot must cover the whole question band across all pages.

Use this page-band rule:

- Start at the question's detected text header/page coordinate.
- End immediately before the next top-level question header; for the last question, use the
  final QP page.
- Render a full-width vertical crop for every page in that span.
- Exclude pages whose only content is the deliberate `Please do not write on this page` answer
  spacer, unless a real figure/object is present.
- Keep all page crops comma-separated in `question_image`.

This captures graphs and vector diagrams even when the text layer omits or garbles their visual
layout. A figure is not stored separately in `figure_image`; the question-band screenshot is
the authoritative attachment.

### Answer images

The mark scheme's text answer is keyed by the same top-level question number, but its rows are
subparts. Group all mark-scheme text from the first row belonging to Qn up to the first row
belonging to Q(n+1). Render the corresponding MS page span as `answer_image`.

- Preserve all subparts, alternatives, notes, ECF instructions, and totals in normalized
  `answer` text.
- Do not attach only the first answer row; a Paper 2 answer often spans multiple MS pages.
- Keep raster/vector answer graphs and diagrams through the full MS page-band screenshot.
- Do not include introductory rubric pages before the answer table.
- If a question's MS span includes a page with a real answer figure, retain it even if its text
  is short. Only omit truly blank/spacer pages.

### Stable matching key

Each record should use a stable ID such as:

```text
PHYS_HL_P2_<slug>_qNN
```

The same `<slug>` must include session and zone, for example:

```text
2024May_TZ1
2025May_TZ3
2025Nov_TZ1
```

The match is therefore `(source PDF, top-level qnum)` → `(QP text/page band, MS text/page band)`.
No figure-caption-number heuristic is needed because all figures are inline within the respective
question or answer page spans.

---

## 5. Verification plan after approval

- Inventory: **29 QP/MS pairs**, no missing English mark scheme.
- QP detector: 29/29 files resolve their expected sequential top-level counts.
- MS detector: 29/29 files resolve the same top-level count after the table header; total answer spans = 269.
- Expected imported records: **269**.
- Every record must have nonempty question and answer text.
- Every record must have both `question_image` and `answer_image` references, with all referenced
  files existing on disk.
- Answer alignment invariant: the first top-level MS row in each answer span must equal its own
  qnum; later repeated subpart rows must remain inside that span.
- Normalize Physics PUA glyphs; report any unmapped codepoints. Images remain source of truth.
- DB rows should be `category='past'`, `review_status='new'`, `paper_type='Paper 2'`, and
  `source = "Physics HL P2 · <session/zone>"`.
- Keep Math and Physics Paper 1/P3 rows untouched.

---

## 6. Decision gate

This completes Phase A research. **No Physics Paper 2 extraction has started.**

The approved extraction design is one unified top-level-question pipeline for all 29 files:
separator-aware QP headers, variable 8–11 question counts, rubric-anchored MS top-level spans,
full-width multi-page QP/MS screenshots, normalized text, and idempotent import.

Reply `start` / `scan` / `detect` to begin Phase B, or specify an adjustment first.
