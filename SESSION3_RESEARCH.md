# SESSION 3 RESEARCH — Math AA HL Paper 3 (past papers)

> **Status:** RESEARCH PHASE ONLY. Nothing has been extracted. Per Final Plan Rule #3
> (research-first gate) this document is presented for approval; extraction does NOT start
> until you say `start` / `scan` / `detect`.
>
> Companion to `SESSION1_RESEARCH.md` (P1) and `SESSION2_RESEARCH.md` (P2). Reuses the same
> text-layer engine + the 4-alt `numre` MS detector, with **one P3-specific QP fix** (§3).

---

## 1. Source inventory (12 in-scope English papers)

AA HL Paper 3 is the HL calculator paper. Unlike P1/P2 (which had 13 papers), **P3 has only
12 English papers** — because **2023 Nov P3 is a single `HL` paper (no TZ1/TZ2 split)**,
whereas 2023 Nov P1/P2 had TZ1 + TZ2. French/Spanish/German translation duplicates (present
in 2022 May/Nov) are excluded.

| # | slug | source folder | QP pages | N | MS pages |
|---|------|---------------|---------:|---:|---:|
| 1 | `2024_5_TZ1`  | `2024.5HL/…_paper_3__TZ1_HL.pdf` | 6 | 2 | 16 |
| 2 | `2024_5_TZ2`  | `2024.5HL/…_paper_3__TZ2_HL.pdf` | 6 | 2 | 21 |
| 3 | `2024_11`     | `2024.11HL/…_paper_3__HL.pdf`     | 6 | 2 | 25 |
| 4 | `2021May_TZ1` | `…/2021 May/…_TZ1_HL.pdf`         | 6 | 2 | 24 |
| 5 | `2021May_TZ2` | `…/2021 May/…_TZ2_HL.pdf`         | 7 | 2 | 23 |
| 6 | `2021Nov`     | `…/2021 Nov/…_paper_3__HL.pdf`    | 4 | 2 | 16 |
| 7 | `2022May_TZ1` | `…/2022 May/…_TZ1_HL.pdf`         | 6 | 2 | 27 |
| 8 | `2022May_TZ2` | `…/2022 May/…_TZ2_HL.pdf`         | 6 | 2 | 20 |
| 9 | `2022Nov`     | `…/2022 Nov/…_paper_3__HL.pdf`    | 7 | 2 | 20 |
| 10| `2023May_TZ1` | `…/2023 May/…_TZ1_HL.pdf`         | 6 | 2 | 15 |
| 11| `2023May_TZ2` | `…/2023 May/…_TZ2_HL.pdf`         | 6 | 2 | 32 |
| 12| `2023Nov`     | `…/2023 Nov/…_paper_3__HL.pdf`    | 6 | 2 | 23 |

Expected total questions if all resolve: 12 × 2 = **24**.

**Note:** P3 has only **2 questions per paper** (vs 12 in P1/P2) — each is a long, multi-part,
multi-page question worth ~27–28 marks (total ~55). This is the defining P3 structural trait.

---

## 2. Text-layer viability

| signal | finding |
|--------|---------|
| QP text layer | Born-digital TEXT in all 12. QP PUA density **low** (1–38 glyphs/paper). |
| MS text layer | Born-digital TEXT in all 12. MS PUA density **moderate** (86–475 glyphs/paper; one paper, 2021May_TZ1, = 0). → reuse P1/P2 `normalize_math()` for answers. |
| MS raster/figure pages | **0** pages with ≤40 chars of text in every MS → fully text-based; diagrams inline in QP band (same as P1/P2). |
| MS anchor | `"Presentation of candidate work"` present in **all 12** MS → the P1/P2 anchor works unchanged. |

**Conclusion:** P3 is text-extractable with the same engine. Per Rule #5 every record keeps
BOTH the rendered `question_image`/`answer_image` JPGs AND the normalized text.

---

## 3. P3-specific finding — QP marks label is singular/plural

P1's `qhead_re` (`\[Maximum mark: (\d+)\]`) matched all P1/P2 papers (they use singular
"mark"). **P3 varies:**
- `2024_5_TZ1` QP: `1. [Maximum mark: 27]` (singular) ✅
- `2022May_TZ1` QP: `1. [Maximum marks: 27]` (**plural**) ❌ — original regex → N=0

Fix: make the QP detector accept both → `r'(?m)^\s*(\d+)\.\s*\[Maximum marks?: (\d+)\]'`.
Verified: with this fix, **all 12 P3 papers resolve 2/2** (was 11/12 with the singular-only regex).

The MS detector is unchanged from P2 (the 4-alt `numre`): `Question N` / `N.` / `N METHOD` /
`N (a)`. Confirmed by header dumps: P3 MS uses `1. (a) (i)` and `Question N continued` —
no new format. All 12 resolve 2/2 with the 4-alt detector.

---

## 4. Text ↔ image matching rule (identical to P1/P2)

- **Question band:** from the QP page of question `n`'s header (now detected by `\[Maximum marks?:]`)
  up to the page *before* question `n+1`'s header (last question → actual last QP page).
  Rendered to `question_image` JPGs. **Because P3 questions are long, a single question's
  `question_image` will span several pages** (e.g. 2–4 QP pages) — this is expected and correct.
- **Answer band:** MS text anchored after the last `Presentation of candidate work`, from
  question `n`'s MS header to `n+1`'s (strict walker). A single P3 answer may span **10+ MS
  pages** — again expected. Rendered to `answer_image` JPGs.
- **Matching key:** stable id `MATH_AAHL_P3_<slug>_qNN`. Idempotent DELETE+INSERT per paper.
- **Figure columns:** `figure` / `figure_image` / `answer_figure` left `null` (figures are
  inline in the rendered bands). Same convention as P1/P2.

---

## 5. Normalization & verification plan (after approval)

- Reuse P1/P2 `normalize_math()` + `PUA_MAP`. Strip page footers via `clean()` (page footers
  like "Please do not write on this page", session codes, "Turn over" remain cosmetic in text;
  images are correct).
- **Invariant check** (mirrors the P1 fix): first MS header inside each `answer` == own qnum →
  assert 0 mismatches across all 24.
- DB writes via the same idempotent importer; every row `review_status='new'`, `category='past'`,
  `source = "AA HL P3 · <pretty>"`, `paper_type = "Paper 3"`, `level = "HL"`, `topic = "AA HL"`.
- `question_image`/`answer_image` under `backend/public/figures/paper_aa_hl_p3/<slug>/`.

---

## 6. Decision gate

This is the end of the research phase. **Extraction has NOT started.**

If you approve, the next step is: fork `extract_paper_aa_p2.py` → `extract_paper_aa_p3.py`
(use `\[Maximum marks?:]` for QP detection, same 4-alt MS detector, `paper_aa_hl_p3` figure
folder + `paper_aa_p3_manifest.json`), run it, import, and verify (24 rows, invariant 0
mismatches). Then STOP-AND-WAIT.

Reply `start` / `scan` / `detect` to proceed, or tell me any adjustment.

---

## 7. Note on the OTHER task this turn (Paper 1 & 2 status)

Separately, you asked to move Paper 1 & 2 rows out of "New coming" into the finished-checking
status. That is `review_status = 'done'` (the frontend's "✓ Mark reviewed" value; the only
other valid value besides `'new'`/`null`). It is a direct DB status update on the 311
`AA HL P1%` / `AA HL P2%` rows and does NOT touch the `successful` tag. Handled in the same
session as the research (see chat) — extraction of P3 is still gated behind your approval.
