# SESSION 2 RESEARCH — Math AA HL Paper 2 (past papers)

> **Status:** RESEARCH PHASE ONLY. Nothing has been extracted. Per Final Plan Rule #3
> (research-first gate) this document is presented for approval; extraction does NOT start
> until you say `start` / `scan` / `detect`.
>
> Companion to `SESSION1_RESEARCH.md` (Paper 1, done). Reuses the same text-layer engine
> and the same `numre` detector — with **one P2-specific addition** (see §3).

---

## 1. Source inventory (13 in-scope English papers)

All post-2019 AA HL Paper 2 English-language papers. French/Spanish/German translation
duplicates (present in 2022 May/Nov) are **excluded** — they are the same content.

| # | slug | source folder | QP pages | N (questions) | markscheme pages |
|---|------|---------------|---------:|----:|---:|
| 1 | `2024_5_TZ1`  | `2024.5HL/…_paper_2__TZ1_HL.pdf` | 17 | 12 | 29 |
| 2 | `2024_5_TZ2`  | `2024.5HL/…_paper_2__TZ2_HL.pdf` | 17 | 12 | 29 |
| 3 | `2024_11`     | `2024.11HL/…_paper_2__HL.pdf`     | 21 | 12 | 30 |
| 4 | `2021May_TZ1` | `…/2021 May/IB 数学 AA HL 2021.05/…_TZ1_HL.pdf` | 17 | 12 | 22 |
| 5 | `2021May_TZ2` | `…/2021 May/IB 数学 AA HL 2021.05/…_TZ2_HL.pdf` | 17 | 12 | 28 |
| 6 | `2021Nov`     | `…/2021 Nov/…_paper_2__HL.pdf`    | 17 | **11** | 32 |
| 7 | `2022May_TZ1` | `…/2022 May/…_TZ1_HL.pdf`         | 17 | 12 | 32 |
| 8 | `2022May_TZ2` | `…/2022 May/…_TZ2_HL.pdf`         | 17 | 12 | 35 |
| 9 | `2022Nov`     | `…/2022 Nov/…_paper_2__HL.pdf`    | 13 | 12 | 32 |
| 10| `2023May_TZ1` | `…/2023 May/…_TZ1_HL.pdf`         | 17 | 12 | 31 |
| 11| `2023May_TZ2` | `…/2023 May/…_TZ2_HL.pdf`         | 17 | 12 | 29 |
| 12| `2023Nov_TZ1` | `…/2023 Nov/…_TZ1_HL.pdf`         | 17 | 12 | 32 |
| 13| `2023Nov_TZ2` | `…/2023 Nov/…_TZ2_HL.pdf`         | 17 | 12 | 32 |

Expected total questions if all resolve: 12×12 + 11 = **155**.

---

## 2. Text-layer viability

| signal | finding |
|--------|---------|
| QP text layer | Born-digital TEXT in all 13. QP PUA (Symbol/MT-Extra) density **low** (1–76 glyphs/paper) → question text is highly readable as-is. |
| MS text layer | Born-digital TEXT in all 13. MS PUA density **high** (278–1137 glyphs/paper) → answers need `normalize_math()` (same PUA_MAP as P1). |
| MS raster/figure pages | **0** pages with ≤40 chars of text in every MS → the mark schemes are fully text-based; no scanned figure pages to special-case. (P2 diagrams live inline in the QP, exactly like P1.) |
| QP question header | `N. [Maximum mark: X]` — identical to P1. `qhead_re` detects all 13 correctly (N = 12, except 2021Nov = 11). |

**Conclusion:** P2 is text-extractable with the same engine as P1. Per Rule #5 every record keeps BOTH the rendered `question_image`/`answer_image` JPGs AND the normalized text.

---

## 3. Mark-scheme question structure — the P2-specific finding

P1's `numre` (3 alternatives) resolves **12/13** P2 papers, but **`2021May_TZ1` only 5/12**.
Root cause: a 4th MS header format unique to P2:

```
6 (a) attempt to find a vector perpendicular to and      ← 2021May_TZ1, Q6  (NO DOT)
```

The 3 P1 formats (`Question N` / `N.` / `N METHOD`) all miss a bare `N (a)` with no dot.
Adding a 4th alternative `(\d+)\s+\([a-z]\)` fixes it. The full detector:

```python
numre = re.compile(
    r'(?m)^\s*(?:Question\s+(\d+)      # g1  "Question 10" / "Question 10 continued"
              |(\d+)\.(?!\d)\s          # g2  "10."  (dot, not a decimal)
              |(\d+)\s+METHOD\b         # g3  "2 METHOD 1"
              |(\d+)\s+\([a-z]\))        # g4  "6 (a)"  ← NEW for P2
              )'
)
```

All 4 formats seen in the corpus (verified by header dumps):

| format | example | papers |
|--------|---------|--------|
| `N. (a)` (dot) | `1. (a) recognition that …` | most papers |
| `N (a)` (no dot) | `6 (a) attempt to find a vector …` | **2021May_TZ1 only** |
| `Question N continued` | `Question 7 continued` | continuation bands |
| `N. METHOD 1` | `9. (a) METHOD 1` | alt-solution markers |
| `N. EITHER` / `OR` | `2. EITHER` | alternative mark paths (2021Nov) |

The strict `num == expected` walker (1→N, monotonic) is the safety net: even within a
question, stray `N (a)` subpart lines can only be accepted if they are exactly the next
expected question number, so a mid-question `6 (a)` cannot steal a span.

**Verified result (research probe, `research_p2.py`):**

```
ALL 13 P2 PAPERS RESOLVE 12/12 (or 11/11 for 2021Nov) WITH 4-ALT DETECTOR.
2021May_TZ1:  3alt = 5/12  ->  4alt = 12/12   (the fix)
every other paper: 12/12 (2021Nov 11/11) with both detectors
```

---

## 4. Text ↔ image matching rule (identical to P1)

- **Question band:** from the QP page of question `n`'s `qhead_re` match, up to the page
  *before* question `n+1`'s header (last question → actual last QP page). Rendered to
  `question_image` JPGs. P2 diagrams/graphs are inline in this band, so they are captured.
- **Answer band:** MS text anchored after the last `Presentation of candidate work`, from
  question `n`'s MS header to question `n+1`'s MS header (strict walker). Rendered to
  `answer_image` JPGs. METHOD-1/METHOD-2 and EITHER/OR alternatives fall inside one band.
- **Matching key:** stable id `MATH_AAHL_P2_<slug>_qNN` (zero-padded). Idempotent
  DELETE+INSERT on re-run (per paper). Same stable-id scheme as P1.
- **Figure columns:** `figure` / `figure_image` / `answer_figure` left `null` for past
  papers (figures are inline in the rendered bands, not separate files) — same convention as P1.

---

## 5. Normalization & verification plan (for the extraction phase, after approval)

- Reuse P1's `normalize_math()` + `PUA_MAP` (92 entries) for both question and answer text.
- **Invariant check** (mirrors the P1 fix that resolved the "blank/wrong answer" bug):
  the first question-number header inside each `answer` text MUST equal its own `qnum`.
  Assert 0 mismatches across all 155 records after extraction.
- DB writes via the same idempotent importer; every row `review_status='new'`,
  `category='past'`, `source = "AA HL P2 · <pretty>"`, `paper_type = "Paper 2"`,
  `level = "HL"`, `topic = "AA HL"`.
- `question_image`/`answer_image` go under `backend/public/figures/paper_aa_hl_p2/<slug>/`.

---

## 6. Open items / risks

- **2021Nov has 11 questions** (not 12) — the walker correctly caps at N=11; no special case.
- **PUA density is higher in P2 MS** (up to 1137 vs P1's ~276–1137) — normalization is
  essential; a few rare structural glyphs (tall brackets, large operators) remain
  best-effort linearized, with the rendered image as source of truth (Rule #5).
- No AI/SL, no P3 in this session — those are later sessions (3, 4+).

---

## 7. Decision gate

This is the end of the research phase. **I have NOT started extraction.**

If you approve, the next step is: create `extract_paper_aa_p2.py` (fork of the P1 extractor,
4-alt detector, new `paper_aa_hl_p2` figure folder + `paper_aa_p2_manifest.json`), run it,
import, and verify (155 rows, invariant 0 mismatches). Then STOP-AND-WAIT.

Reply `start` / `scan` / `detect` to proceed, or tell me any adjustment.
