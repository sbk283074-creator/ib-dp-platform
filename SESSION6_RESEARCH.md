# SESSION 6 RESEARCH — Physics HL Paper 3 (past papers)

> **Status: RESEARCH ONLY.** No Physics Paper 3 extraction, manifest write, image render,
> or DB import has been started. This follows `FINAL_PLAN.md` Rule #3. Wait for `start` /
> `scan` / `detect` before Phase B.
>
> This session covers the English Physics **HL** Paper 3 files actually present in
> `Physics-HL-Past Papers&Mark Schemes(1999.05~2025.11)`. No Physics SL source folder was
> present, and missing local sessions are not silently invented.

---

## 1. Source inventory and availability

The FINAL_PLAN window is May 2016 through November 2025. The local source folder contains
**19 English Paper 3 question-paper / mark-scheme pairs**, all with matching `_markscheme.pdf`
files. Translation duplicates are excluded.

The local folder has **no Paper 3 files** for:

- 2021 May
- 2021 November
- 2022 May
- 2022 November
- 2025 May
- 2025 November

This is a source-availability finding, not an assumption that no assessment material existed;
those sessions simply cannot be extracted from the current local folder.

### Option ranges and expected top-level records

Paper 3 has Section A (answer both questions) plus Section B (answer one of four options). The
question-paper files contain all four options, so the proposed question-bank model is to retain
**all available options as separate records**, with the option encoded in the source/ID. This
makes every available question searchable; it does not imply that a student answered all four
options in one sitting.

| Session/file | Section A | Option A | Option B | Option C | Option D | all-option records |
|---|---:|---:|---:|---:|---:|---:|
| 2016 May | 1–2 | 3–7 | 8–11 | 12–16 | 17–21 | 21 |
| 2016 Nov | 1–3 | 4–9 | 10–14 | 15–20 | 21–25 | 24 |
| 2017 May TZ1 | 1–2 | 3–6 | 7–10 | 11–13 | 14–17 | 17 |
| 2017 May TZ2 | 1–2 | 3–7 | 8–11 | 12–16 | 17–20 | 20 |
| 2017 Nov | 1–3 | 4–8 | 9–12 | 13–16 | 17–20 | 19 |
| 2018 May TZ1 | 1–2 | 3–7 | 8–11 | 12–14 | 15–19 | 19 |
| 2018 May TZ2 | 1–2 | 3–7 | 8–11 | 12–15 | 16–19 | 19 |
| 2018 Nov | 1–2 | 3–7 | 8–11 | 12–16 | 17–21 | 21 |
| 2019 May TZ1 | 1–2 | 3–7 | 8–11 | 12–16 | 17–20 | 20 |
| 2019 May TZ2 | 1–3 | 4–9 | 10–14 | 15–17 | 18–22 | 21 |
| 2019 Nov | 1–2 | 3–6 | 7–10 | 11–14 | 15–17 | 17 |
| 2020 Nov | 1–2 | 3–7 | 8–12 | 13–18 | 19–24 | 24 |
| 2023 May TZ1 | 1–2 | 3–7 | 8–11 | 12–14 | 15–19 | 19 |
| 2023 May TZ2 | 1–2 | 3–7 | 8–11 | 12–15 | 16–20 | 20 |
| 2023 Nov TZ1 | 1–2 | 3–7 | 8–11 | 12–16 | 17–20 | 20 |
| 2023 Nov TZ2 | 1–2 | 3–7 | 8–11 | 12–16 | 17–20 | 20 |
| 2024 May TZ1 | 1–2 | 3–7 | 8–12 | 13–16 | 17–20 | 20 |
| 2024 May TZ2 | 1–2 | 3–7 | 8–11 | 12–16 | 17–21 | 21 |
| 2024 Nov | 1–2 | 3–7 | 8–11 | 12–16 | 17–21 | 21 |

Expected total under the all-options model: **386 top-level question records**. The 2017 November paper has three Section A questions (`1–3`), which accounts for the extra record relative to a two-question assumption.

---

## 2. Text-layer viability and PDF objects

Probes covered 2016, 2017, 2018, 2019, 2020, 2023, and 2024 examples; the full 19-file
probe checked page counts and embedded object signals.

| signal | finding |
|---|---|
| QP text layer | Born-digital text in all 19 QPs; no scanned-paper exception found. QP length is roughly 32–45 pages. |
| MS text layer | Born-digital text in all 19 mark schemes; MS length is roughly 22–33 pages. |
| QP raster objects | Sparse: only a small number of raster objects in a few QPs; most diagrams/graphs are vector PDF content. |
| MS raster objects | Common and important: many MS files contain answer graphs/diagrams, with up to 22 objects in one 2023 MS probe. |
| QP spacer pages | Many QPs include intentional `Please do not write on this page` pages between sections/options. |
| MS spacer pages | No equivalent blank answer-page pattern was observed in the representative MS probes. |
| PUA symbols | QP PUA is low; MS PUA is much higher and requires the Physics normalization map. |

**Conclusion:** Paper 3 is text-extractable, but text alone loses diagrams, graphs, graph-drawing
answers, and table layout. Per FINAL_PLAN Rule #5, every record must retain normalized text plus
rendered `question_image` and `answer_image`.

---

## 3. Paper 3 question structure

### Section A

- Section A contains two or three top-level questions depending on the session.
- The instruction table gives the exact range, normally `1–2`, with some sessions using `1–3`.
- Questions are experimental/data-analysis questions: line of best fit, uncertainty, graph
  interpretation, measured quantities, and evaluation of methods.
- They are long and multi-page, with subparts `(a)`, `(b)(i)`, `(b)(ii)`, etc.

### Section B

- Section B contains four options:
  - **Option A — Relativity**
  - **Option B — Engineering physics** (some older files shorten this to Engineering)
  - **Option C — Imaging**
  - **Option D — Astrophysics**
- Candidates answer all questions from one option, but the PDF contains all four options.
- Option question numbers continue after Section A and are not reset to 1. For example:
  `1–2` in Section A, then `3–7` in Option A, `8–11` in Option B, and so on.
- Option lengths vary by session. The range table above is the authoritative inventory.
- Option continuation pages use labels such as:
  - `(Option A continued)`
  - `(Option A, question 5 continued)`
  - `End of Option A`
- Deliberate blank pages can occur inside long options and say `Please do not write on this page`.

### Validated QP top-level detector

The safe candidate detector is:

```python
qp_head = re.compile(
    r'(?m)(?:^|[\\r\\n\\ufffe])\\s*(\\d{1,2})\\.(?!\\d)\\s+(?=[A-Z(])'
)
```

However, unlike Paper 1/Paper 2, Paper 3 cannot be validated by one simple `1→N` walk
because the PDF contains four option blocks and some PDF text layers expose diagram numbers
as false candidates. The correct validation is:

1. Read the option range table from the first instruction pages.
2. Detect Section A using its declared range.
3. Detect each option within its own page/section block and declared numeric range.
4. Accept exactly the expected question numbers in that block.
5. Reject duplicate false hits from diagrams or references. Examples seen during probing:
   - a duplicate `2` inside 2023 November text
   - a duplicate `21` in 2024 May TZ2 text

Using the declared ranges, all 19 QPs balance to the 386-record all-options total.

---

## 4. Mark-scheme answer structure

The mark schemes use detailed answer tables:

```text
Question | Answers | Notes | Total
```

They include:

- all Section A subparts
- all four options
- subpart rows such as `1 a i`, `3. b`, `14. c ii`
- accepted alternatives and alternate methods
- ECF guidance
- `[n]` totals and `max` totals
- graph/diagram marking instructions

The MS repeats `Question Answers Notes Total` at page boundaries. It also uses the same top-level
question numbers as the QP, but each qnum can have many subpart rows and spans multiple pages.

### Answer matching rule

The answer must be segmented by **option block plus top-level qnum**, not by qnum alone:

```text
(source PDF, Section A, q01)
(source PDF, Option A, q03)
(source PDF, Option A, q04)
...
(source PDF, Option B, q08)
...
(source PDF, Option D, q21)
```

This prevents a repeated/continued qnum or a numeric diagram fragment from stealing a later
answer span. Within each block:

1. Locate the `Section A` or `Option X` answer-table block.
2. Find the first top-level row in the declared qnum range.
3. Keep repeated subpart rows with the same qnum inside that record.
4. End immediately before the next expected top-level qnum in the same block.
5. End the final qnum at `End of Option X` or the actual end of the answer table.

The mark scheme therefore maps by `(option, qnum)`, not qnum alone.

### Recommended record identity

```text
PHYS_HL_P3_<session>_A_q01
PHYS_HL_P3_<session>_A_q03
PHYS_HL_P3_<session>_B_q08
PHYS_HL_P3_<session>_C_q12
PHYS_HL_P3_<session>_D_q17
```

The option should also be visible in `source`, for example:

```text
Physics HL P3 · 2024 May TZ1 · Option C Imaging
```

This avoids collisions and makes it clear that the question came from a selectable option.

---

## 5. Text ↔ image relationship and matching rule

### Question images

Paper 3 QP pages contain inline vector diagrams, graphs, tables, spacetime diagrams, optical
layouts, and experimental apparatus. These are often the main answer target, especially in
Section A. The text layer does not preserve layout reliably.

For each `(section/option, qnum)`:

- start at the detected top-level qnum header;
- end before the next top-level qnum in the same block;
- for the final question in a block, end at `End of Option X`, the next section marker, or
  the last relevant page;
- render the full-width vertical band for every page in that span;
- omit only truly blank `Please do not write on this page` spacer pages;
- retain all graph pages even when text is sparse.

### Answer images

Mark-scheme pages frequently contain graph/diagram marking instructions and are not safely
represented by text alone. For each `(section/option, qnum)`:

- start at that qnum's first answer-table row in the corresponding block;
- end before the next top-level qnum in that same block;
- include all continuation pages and all repeated `Question Answers Notes Total` headers;
- retain answer graphs/diagrams and graph-drawing examples;
- omit only an actually blank page with no answer content.

No separate figure-caption heuristic is needed. The option/qnum page-span key is the reliable
matching rule.

---

## 6. Extraction decision and verification plan

### Recommended extraction model

Extract **all four options** from every available English Paper 3 PDF, not only one option. This
creates a complete searchable question bank. Each record remains labeled with its option, so a
future UI can filter Relativity, Engineering physics, Imaging, or Astrophysics.

Expected result if approved: **386 top-level records** from 19 pairs.

### Verification after approval

- Inventory assertion: 19 QP/MS pairs, all paired.
- Section/option range assertion: every QP matches its declared Section A + A/B/C/D ranges.
- Record count assertion: 386 all-option records.
- Answer alignment assertion: every `(option, qnum)` answer starts at its own declared qnum;
  no answer span crosses an option boundary.
- Every record has nonempty question and answer text.
- Every record has both image fields; every referenced JPG exists.
- Normalize Physics PUA glyphs and report any unmapped codepoints.
- Every row uses `category='past'`, `review_status='new'`, `paper_type='Paper 3'`.
- Keep all existing Math and Physics Paper 1/Paper 2 rows untouched.

---

## 7. Decision gate

This completes Phase A research. **No Physics Paper 3 extraction has started.**

The main implementation choice is recorded: import all available options as separate stable
records, because the PDFs contain four complete option blocks and the question bank benefits
from searchable coverage of every option. If you prefer only one option per paper, specify the
option policy before approving extraction.

Reply `start` / `scan` / `detect` to begin Phase B, or tell me to change the all-options policy.
