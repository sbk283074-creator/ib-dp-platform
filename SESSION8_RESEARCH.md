# SESSION 8 RESEARCH — Computer Science Paper 2 (HL) — past 10 yrs

> **Phase:** A (Research only — NO extraction). Per FINAL_PLAN §2 / operating contract.
> **Source root:** `../Computer Science-HL-Past Papers&Mark Schemes(1999.05~2025.05)/`
> **Status:** Research complete. Awaiting user command (`start` / `scan` / `detect`) before any extraction.

---

## 1. Source inventory

**Folder layout & filename pattern:** identical to P1 (see SESSION7_RESEARCH §1).
- `Computer_science_paper_2__HL.pdf` (note **double underscore** `paper_2__HL` — the single-underscore
  guess fails; the scanner must match `paper_2` + `HL` loosely, not a fixed literal).
- `_markscheme`, `_Spanish`, `_French`, `_case_study` suffixes as before. **Skip language variants; skip `_case_study`** (that is Paper 3, not P2).

**⚠️ Coverage gap — 2021 & 2022 have NO Paper 2.** Those sessions contain only P1 + P3
(`*paper_3__case_study_HL*`). Empirically P2 is absent from the source for 2021-05/11 and 2022-05/11.
So the import set is **not** a clean 2016→2025 span.

**P2 in the window (May 2016 → Nov 2025), English, with markscheme:**

| Session | Q | MS | TZ? |
|---|---|---|---|
| 2016-05 / 2016-11 | 1 | 1 | — |
| 2017-05 / 2017-11 | 1 | 1 | — |
| 2018-05 / 2018-11 | 1 | 1 | — |
| 2019-05 / 2019-11 | 1 | 1 | — |
| 2020-11 | 1 | 1 | — |
| 2021-05 / 2021-11 | — | — | **GAP (no P2)** |
| 2022-05 / 2022-11 | — | — | **GAP (no P2)** |
| 2023-05 / 2023-11 | 1 | 1 | — |
| 2024-05 / 2024-11 | 1 | 1 | — |
| 2025-05 | 2 | 2 | TZ2+TZ3 |

→ **15 English P2 papers** (9 from 2016–2020 + 4 from 2023–2024 + 2 from 2025). Only **2025-05** ships
TZ variants (TZ2+TZ3); 2023/2024 are single (unlike P1, which had TZ1+TZ2 in 2023/2024 too).
Total expected questions ≈ 15 × ~16 ≈ **240** (per-paper top-level count ranges 16–17).

---

## 2. Text-layer verdict → extraction method

**Born-digital TEXT** (same as P1 — confirmed by the probes reading clean text from 2019/2023/2025).
No OCR needed. Diagrams (ER diagrams, tables, sketches) are **vector graphics**, not raster →
**Rule #5 applies**: keep BOTH normalized text AND a rendered JPG band for every question/answer.

Reuse the exact P1 machinery: `pypdfium2` text + `get_charbox` for tight per-question vertical crops,
consecutive `N.` walker for segmentation.

---

## 3. Question-paper structure — DIFFERENT FROM P1 (options, not Section A/B)

This is the key difference from P1. P2 is **option-based**, not "Section A / Section B".

- **Instructions:** *"Answer all of the questions from **one of the options**."* Whole-paper cap is
  **[65 marks]** (not 100 like P1).
- **Four options**, each a self-contained block of questions, with **continuous numbering 1..N across
  all options**:

  | Guide | Option A | Option B | Option C | Option D |
  |---|---|---|---|---|
  | 2019 (old) | Databases 1–4 | Modelling 5–8 | Web science 9–13 | OOP 14–17 |
  | 2023 (new) | Databases 1–4 | Modelling 5–8 | Web science 9–12 | OOP 13–16 |
  | 2025 (new) | Databases 1–4 | Modelling 5–8 | Web science 9–13 | OOP 14–17 |

  The "Option Questions" list at the top of the paper maps **question-number ranges → option name**.
  This list is the authoritative way to tag each question with its option.
- **Within an option**, questions use the same format as P1: `N. <context> … (a)(i) … [1]` — top-level
  `N.`, lettered subparts `(a)(b)(c)`, and bracketed marks `[M]` per subpart. Numbering does **not**
  reset between options (it runs 1..17 continuously).
- **Command terms:** same vocabulary as P1 (State, Define, Describe, Explain, Construct, Outline…).
- The option block is also announced by a body header `Option A — Databases` before its first question
  (mirrors the markscheme grouping), useful as a secondary anchor.

---

## 4. Markscheme structure

- **Header per option:** `Option A — Databases`, then answers keyed by question number.
- **Answer body:** `1. (a) (i) Award [1 max] … (ii) Award [1 max] … (b) Award [1 max] …` — i.e.
  keyed by number, does **not** reprint the prompt (same as P1). We keep the QP prompt + append MS points.
- **Marking-instructions preamble:** the MS opens with general guidance prose (e.g. *"…two reasons…,
  mark the first two correct answers…"*) BEFORE the first real `1.` — same anchoring trap as P1.
  Anchor the MS walk at the first `1.` that follows the option-grouping / past the preamble.
- **Marks source decision (carried from P1):** use the **QP printed `[M]`** summed over the question
  span (ignoring array/matrix/index notation via the proven `qp_marks` filter). The MS `Award [N max]`
  is per-subpart and summing is fragile; QP totals are uniform and reliable. Whole-paper `[65 marks]`
  appears only once in the instructions, outside any question span, so it is never double-counted.

---

## 5. Text ↔ image (figure) relationship & matching rule

Identical to P1 (§5 of SESSION7): inline vector diagrams sit inside each question's page band. Segment
by top-level `N.` → render `question_image`; segment MS by same `N.` → render `answer_image`. Both JPG
+ text stored per record (Rule #5).

---

## 6. DB schema to mirror (reuse CS P1 layout)

| Field | Value for CS P2 |
|---|---|
| `id` | `CS_HL_P2_<Session>_qNN` (e.g. `CS_HL_P2_2023May_q01`); 2025 → `CS_HL_P2_2025May_TZ2_q01` |
| `subject` | `Computer Science` |
| `level` | `HL` |
| `topic` | `CS HL` |
| `paper_type` | `Paper 2` |
| `tags` | `["Option A — Databases"]` (the option this question belongs to — P2's analog of P1's Section A/B) |
| `marks` | sum of subpart `[M]` for the question (QP source) |
| `question` | prompt + subparts (text) |
| `answer` | markscheme points for that number (text) |
| `question_image` | `cs_hl_p2/<session>/qNN_pX.jpg` |
| `answer_image` | `cs_hl_p2/<session>/aNN_pY.jpg` |
| `source` | `CS HL P2 · 2023 May` (2025 → `CS HL P2 · 2025 May TZ2`) |
| `source_type` | `paper` |
| `category` | `past` |
| `authored_by` | `ib` |
| `review_status` | `new` (lands in "New coming" queue) |

Image root = `backend/public/figures/cs_hl_p2/<session>/` (mirrors `cs_hl_p1/…`).

---

## 7. Open decisions for the user (research gate — answer before extraction)

1. **TZ variants (2025 only):** import **both** TZ2 + TZ3 (→ 15 papers total). Recommended: yes (max coverage).
2. **Option tagging:** flatten all 4 options into one question set, tag each by option via `tags`
   (e.g. `Option A — Databases`). Recommended: yes. (In the real exam a candidate answers ONE option,
   but a question bank should hold all four — same logic as importing all TZ variants in P1.)
3. **2021/2022 gap:** P2 is absent from the source for those two years; they will simply be skipped.
   Note for the record (if those papers are later obtained, they can be added).
4. **Granularity:** one row per top-level question (subparts embedded) — matches P1 and Math P1.
5. **Marks field:** per-question total = sum of subpart `[M]` from the QP (reuse `qp_marks`).
6. **SL absence:** folder is HL-only (same as P1).

---

## 8. Feasibility verdict

✅ Fully feasible — it is essentially the **P1 pipeline with two twists**: (a) tag by **option** instead
of Section A/B (parse the "Option Questions" range list, or use the body `Option A — Databases` headers);
(b) mind the **double-underscore filename** (`paper_2__HL`) and the **2021/2022 gap**. Text-layer path,
vector-diagram rendering (Rule #5), clean 1:1 question↔markscheme keying, and the proven schema mirror
all carry over unchanged. Only open item is the TZ/option scope (#1/#2) — everything else can proceed
once approved.
