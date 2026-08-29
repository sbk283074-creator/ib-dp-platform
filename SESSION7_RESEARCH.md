# SESSION 7 RESEARCH — Computer Science Paper 1 (HL) — past 10 yrs

> **Phase:** A (Research only — NO extraction). Per FINAL_PLAN §2 / operating contract.
> **Source root:** `../Computer Science-HL-Past Papers&Mark Schemes(1999.05~2025.05)/`
> **Status:** Research complete. Awaiting user command (`start` / `scan` / `detect`) before any extraction.

---

## 1. Source inventory

**Folder layout:** one subfolder per examination session, two naming styles:
- Word style: `2016 May Examination Session`, `2016 November Examination Session`
- Dot style (newer): `2022.05`, `2023.11`, `2024.11`, `2025.05`

**Filename pattern:** `Computer_science_paper_1[_<TZ>]_HL[_<lang>][_markscheme].pdf`
- `paper_1` → Paper 1. `_HL` → Higher Level.
- `<TZ>` token (new guide only, see §2): `TZ1` / `TZ2` / `TZ3`.
- `<lang>`: `Spanish` / `French` (language variants — **skip**, we want English).
- `_markscheme` → answer key (separate file).
- `_case_study` → only on Paper 3, not relevant here.

**Totals (whole folder):** 330 PDFs, of which **113 are P1** (100% HL — see §6 note on SL).

**P1 in the "past 10 years" window (May 2016 → Nov 2025):**
- **21 English question papers** + **21 markschemes** = 42 files to import.
- **13 language-variant files** (Spanish/French) → **skip**.
- 2020-05 is absent (COVID cancellation), as expected.

**Per-session English P1 (question / markscheme):**

| Session | Q | MS | TZ? |
|---|---|---|---|
| 2016-05 / 2016-11 | 1 | 1 | — |
| 2017-05 / 2017-11 | 1 | 1 | — |
| 2018-05 / 2018-11 | 1 | 1 | — |
| 2019-05 / 2019-11 | 1 | 1 | — |
| 2020-11 | 1 | 1 | — |
| 2021-05 / 2021-11 | 1 | 1 | — |
| 2022-05 / 2022-11 | 1 | 1 | — |
| 2023-05 | 2 | 2 | TZ1+TZ2 |
| 2023-11 | 1 | 1 | — |
| 2024-05 | 2 | 2 | TZ1+TZ2 |
| 2024-11 | 1 | 1 | — |
| 2025-05 | 2 | 2 | TZ2+TZ3 |

→ **19 sessions** contain P1; 3 of them (2023-05, 2024-05, 2025-05) ship **two TZ variants each**.

---

## 2. Text-layer verdict → extraction method

**Born-digital TEXT** (confirmed by pypdfium2 probe on 5 papers across the span):

| Sample | Pages | Text pages | Raster imgs | Verdict |
|---|---|---|---|---|
| 2012-05 P1 | 7 | 7/7 | 0 | TEXT |
| 2016-05 P1 | 8 | 8/8 | 0 | TEXT |
| 2018-11 P1 | 9 | 9/9 | 0 | TEXT |
| 2023-05 TZ1 P1 | 8 | 8/8 | 0 | TEXT |
| 2025-05 TZ2 P1 | 10 | 10/10 | 0 | TEXT |

→ **Use the TEXT-LAYER path** (FINAL_PLAN §3). No OCR needed. This is a different source from the
old scanned `IB 计算机分类真题.pdf` (that was the classified book, NOT these past papers).

**Diagrams = vector graphics, not raster.** Per-page object counts show `vector_paths` present
(e.g. 2023 TZ1 P1: page1=716, p2=141, p4=17, p7=32, p8=53 paths; raster_images = 0 everywhere).
Consequence (Rule #5): diagrams live only in the rendered image, never in the text layer → we
**must keep BOTH** `question_image`/`answer_image` (JPG render) **and** the normalized text.

---

## 3. Question-paper structure (mapped from 2023-05 TZ1 P1)

- **Cover page:** 3-language copyright + exam metadata ("7 pages", date, "Computer science / Higher
  level / Paper 1", duration "2 hours 10 minutes", zones).
- **Instructions page:** "Section A: answer all questions. Section B: answer all questions. The
  maximum mark for this examination paper is [100 marks]."
- **Two sections, continuous numbering:**
  - **Section A** — short questions, "Total 25 marks". (e.g. Q1–Q9)
  - **Section B** — longer weighted questions, "Total 75 marks". (e.g. Q10–Q14)
  - Numbering is **continuous** (Q9 → Q10 across the A/B break); it does **not** reset in B.
- **Question format:** `N. <command term> … [M]` where `[M]` is the mark value.
  - Example: `1. Outline the function of a web browser. [2]`
  - Subparts: `(a)`, `(b)`, `(c)`, … each may carry its own `[M]`; question total = sum of subparts.
  - Example: `4. (a) Define the term interrupt. [1] (b) Describe how polling could be used… [3]`
- **Command terms observed:** Outline, Identify, Define, Describe, Construct, Distinguish, State,
  Sketch, Explain, Evaluate.
- Whole-paper cap stated as `[100 marks]` (note: per-question marks are bare `[N]`, not `[N marks]`).

---

## 4. Markscheme structure (mapped from 2023-05 TZ1 P1 markscheme)

- **Header:** `– 3 – M23/4/COMSC/HP1/ENG/TZ1/XX/M` + "Subject details: Computer science HL paper 1
  markscheme".
- **Mark allocation block:** "Section A: … Total 25 marks. Section B: … Total 75 marks. Maximum
  total = 100 marks."
- **"General" marking guidance:** points separated by `;`, `/` = alternative wording, `( … )` =
  optional, `FT` = follow-through, mark-positively, etc.
- **Answer body:** keyed by **question number**, NOT by repeating the question text.
  - `1. Award [2 max]` → bullet answer points.
  - Subpart answers appear under the parent number with their letter (e.g. `4. (a) … (b) …`).
- **Anchoring rule:** match question `N` ↔ markscheme `N` **by number**. The markscheme does not
  re-print the prompt, so we keep the question prompt from the question paper and append the
  markscheme points as `answer`.

---

## 5. Text ↔ image (figure) relationship & matching rule

- **Figures are inline vector diagrams** within the question's page region (flowcharts, logic
  gates, binary trees, network sketches, truth tables). No standalone figure files, no captions to
  anchor — the diagram simply sits in the question band.
- **Matching rule (proposed):**
  - Segment the question paper by top-level question number (`N.`) → render that question's page
    span to `question_image` (JPG). This captures any inline vector diagram.
  - Segment the markscheme by the same question number → render to `answer_image` (JPG). This
    captures answer diagrams (e.g. completed truth tables, sketches).
  - `question` = normalized text of the prompt + subparts; `answer` = markscheme points for that
    number.
  - Per Rule #5, both JPG + text are stored for every record.

---

## 6. DB schema to mirror (from existing MATH_AAHL_P1, verified live)

Storage is **one row per top-level question** (subparts embedded in `question`/`answer` text) — CS
P1 must match this.

| Field | Value for CS P1 |
|---|---|
| `id` | `CS_HL_P1_<Session>_qNN` (e.g. `CS_HL_P1_2023May_TZ1_q01`) |
| `subject` | `Computer Science` |
| `level` | `HL` |
| `topic` | `CS HL` (or tag Section A/B via `tags`) |
| `paper_type` | `Paper 1` |
| `marks` | sum of subpart `[M]` for the question |
| `question` | prompt + subparts (text) |
| `answer` | markscheme points for that number (text) |
| `question_image` | `cs_hl_p1/<session>/qNN_pX.jpg` (rendered band) |
| `answer_image` | `cs_hl_p1/<session>/aNN_pY.jpg` (rendered band) |
| `source` | `CS HL P1 · 2023 May TZ1` |
| `source_type` | `paper` |
| `category` | `past` |
| `authored_by` | `ib` |
| `review_status` | `new` (lands in "New coming" queue) |

Image root = `backend/public/figures/cs_hl_p1/<session>/` (mirrors `paper_aa_hl_p1/…`).

---

## 7. Open decisions for the user (research gate — answer before extraction)

1. **TZ variants (2023+):** sessions 2023-05 / 2024-05 / 2025-05 each have **2 P1 papers**
   (TZ1+TZ2; 2025 uses TZ2+TZ3). Import **all** as separate sets (→ 21 papers), or **one per
   session** (→ 15 papers, picking e.g. TZ1)? Recommended: import ALL (maximal coverage).
2. **Section A/B tagging:** flatten questions but tag section via `tags`/`topic` (e.g.
   `CS HL · Section B`)? Recommended: yes, tag it.
3. **SL absence:** this folder is HL-only (all 113 P1 are HL). If CS P1 **SL** is wanted, a
   different source is required — note for the record.
4. **Granularity:** confirm per-top-level-question (matches Math P1). Subparts stay embedded.
5. **Marks field:** per-question total = sum of subpart `[M]`.

---

## 8. Feasibility verdict

✅ Fully feasible via the text-layer path. ✅ Diagrams captured by rendering (vector). ✅ Clean 1:1
question↔markscheme keying by number. ✅ Schema/mirror already proven by Math P1 import.
Only open item is the TZ-variant scope decision (#1 above) — everything else can proceed once
approved.
