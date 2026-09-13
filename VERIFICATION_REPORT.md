# Verification Report — audit claims & book extractions

**Date:** 2026-09-12
**Method:** every claim below was re-tested independently against the live SQLite DB
(`backend/data/app.db`) and the source PDFs on disk. Nothing was taken on trust from
`QUESTION_BANK_AUDIT.md` or from my own scripts. Where my earlier audit was wrong, it is
marked **REFUTED**.

---

## 0. Process finding that invalidates earlier measurements

A **full extraction pass was still running** while I first inspected the output. The
`book_json2/` folder contained a *mix* of files from several partial runs, so early
readings were meaningless.

Concrete proof:

| file | size / mtime at first read | size / mtime 90 s later |
|---|---|---|
| `MA-CAMBRIDGE-2012.json` | 92,238 B @ 11:49 (**120 questions**) | 832,736 B @ 12:05 |
| `MA-OXFORD-2019.json` | 443,982 B @ 11:29 | 469,820 B @ 12:02 |

I initially concluded "Cambridge is broken — only 120 questions". **That was a stale-file
artifact, not a real defect.** A settle-detector waiter (`/tmp/wait_and_import.sh`) now
watches file mtimes and only re-imports after the pass has been quiet for 4 minutes.

Two further consequences:

* The DB import at 11:45 ran against a partial set → **the DB is currently stale for all
  19 books** (JSON count ≠ DB count for 19/19 books).
* Crop images are **never cleaned between runs**, so `MA-CAMBRIDGE-2012/` held **981 images**
  while its JSON listed 120. Any consumer keying off filenames rather than the JSON would
  see hundreds of phantom questions.

---

## 1. Claims that are CONFIRMED

### 1.1 CS HL — exactly 10 sessions on disk missing from the bank ✅
Compared the 48 session folders in
`Computer Science-HL-Past Papers&Mark Schemes(1999.05~2025.05)/` against the DB:

```
2001 May      2001 November   2003 November   2004 May        2004 November
2006 November 2007 November   2008 May        2009 May        2009 November
```
48 folders on disk · 96 distinct DB labels · **10 sessions with no DB rows**. Matches the
audit exactly.

### 1.2 Math HL — 1995–2007 entirely missing ✅
* On disk: `IB 数学 AA  HL 历年真题/IB 数学 HL 真题（2006-23）/` contains **57 year-session
  folders**, running `1995 May` → `2023 Nov` (folder name understates the range).
* In DB: old-syllabus `HL P1 · …` starts at **2008 May**; `AA HL P1/P2/P3 · …` covers
  **2021–2024** only.
* ⇒ **1995–2007 (26 sessions) absent.** Confirmed.

### 1.3 Page-footer contamination ✅
With corrected patterns (my first audit used patterns that matched nothing):

| pattern | rows |
|---|---|
| `continued` | 1,524 |
| `Turn over` | 1,128 |
| `Do not write` | 296 |
| `blank page` | 84 |
| `©` | 56 |

Union ≈ 1,531 — consistent with the original claim. Example:
`MATH_AAHL_P1_2021May_TZ2_q09` ends with `… 2221–7111 Do not write solutions on this page.`

### 1.4 CS label fragmentation ✅
`CS HL Paper 1` (old label) and `CS HL P1` (new label) coexist, likewise `Paper 2` / `P2`.
Date formats are also inconsistent: `2012 November` vs `2024 Nov` vs `2025 May TZ3`.

### 1.5 Zero explanations on past papers ✅
6,977 of 6,977 `category='past'` rows have NULL/empty `explanation`.

### 1.6 Math topic questions have unusable text ✅ (with an important caveat)
Examples pulled from the DB:

```
MA_HL_topic_Topic1_HL-paper1_q41  →  "Express ."
MA_HL_topic_Topic1_HL-paper1_q66  →  "Slov e\r\n."
MA_HL_topic_Topic2_HL-paper1_q55  →  "Solve."
MA_HL_topic_Topic9_HL-paper3_q09  →  "Find ."
```
9 questions are under 15 characters; 87 under 50. The maths itself lives in equation
objects the text layer can't recover.

**Caveat that changes the severity: all 2,205 topic questions DO have a `question_image`.**
So this is a *search/indexing* problem, not a *display* problem — the student still sees the
real question. The original audit implied the questions were broken; they are not.

---

## 2. Claims that are REFUTED / corrected

### 2.1 "24.1 % of questions missing marks" — REFUTED
Marks completeness by category:

| category | total | missing marks |
|---|---|---|
| past | 6,977 | **12 (0.2 %)** |
| questionbank | 787 | 1 (0.1 %) |
| book | 6,884 | 6,884 (100 %) |
| topic | 2,205 | 2,205 (100 %) |

Past papers are **99.8 % complete**. The 24.1 % figure came from lumping in `book` and
`topic`, which carry no marks *by design*. As a defect for past papers this claim is void.

### 2.2 "`paper_type` inconsistent — `Paper 1` 4,001 vs `HL-paper1` 887" — REFUTED
Current distribution of `paper_type` over past papers:

```
"Paper 1" 4,001   "Paper 2" 1,588   "Paper 3" 1,388      (sum = 6,977 = all past rows)
```
No `HL-paper1` value exists. Either it was fixed already or the original reading was wrong.

### 2.3 "3 orphan sub-label questions" — REFUTED
* IDs with a trailing letter in `category='past'`: **0**
* Past questions whose text begins with `(a)` / `(b)` / `(i)`: **0**

I could not reproduce this finding in any form.

### 2.4 My own audit script was buggy
`WHERE source LIKE '%CS HL%'` also matched **"Physi·cs HL"** (case-insensitive `LIKE`),
silently mixing Physics rows into the CS label analysis. Fixed with `LIKE 'CS HL%'`.

---

## 3. NEW defects found during verification (not in the original audit)

### 3.1 Index / glossary pages become bogus questions
`MA-OXFORD-2019-S137-Q12`, section **"Exercise 0"**, page 854 → I opened the crop: it is the
book's **index**, not a question. 22 such rows in that book alone (3.6 % of its 617).
The section name `Exercise 0` is itself invalid.

### 3.2 Section names can be body text
`MA-HODDER-2019` contains section names like
`2The last eq bu ation sho w s Thi s means th a t q i s an even num er`, and
`MA-HAESE-AA2` contains `Exercise 22` / `Exercise 51` / `Exercise 16` where the real headings
are `1B` / `1G` etc. Heading detection is firing on ordinary prose.

### 3.3 Two-column bleed (verified visually)
I opened `MA-OXFORD-2019_q_26_1.jpg` (Exercise 1B Q1). The question itself is **correct and
clean** — "Find the *n*th term of each of these sequences: a…d". But the crop is full-width,
so it also contains **questions 5, 6 and 7 from the adjacent column**. Every two-column crop
therefore carries neighbour content. This is the known trade-off from reverting
column-aware cropping (which had cut recall from 297 → 58/94).

### 3.4 Cambridge 2012's text layer is not trustworthy
`KKEEYY PPOOIINNTT 11 55` (doubled letters), `W 7or k e d examp l e 1` (should be "Worked
example 1"), `E Dxerc i se 1` (should be "Exercise 1"), and glyph sizes swing from 0.6 to 14.0
on one page while `estimate_body()` returns 7.3. The size-based heading test is therefore
near-meaningless for this book — headings cannot be distinguished from maths by font size.

---

## 4. Verified GOOD

* `MA-OXFORD-2019_q_26_1.jpg` — Exercise 1B Q1 crop is correct, legible, correctly numbered.
* Question numbering survives garbled text layers: the structural detector found the right
  numbers even where the text read `E Dxerc i se 1`.
* `Physics` past-paper coverage is strong: 74 distinct `Physics HL P1 · …` sessions,
  2000 May → 2025, including the new-syllabus `2025 … 1A TZ1/2/3` and `P1B` papers.

---

## 5. "Mock papers" — resolved (they are the official specimen papers)

The audit said mock papers were missing. They are the official IB **specimen** papers
(样卷), and there are exactly two in the whole Downloads tree:

| paper | pages | in `dp learning`? | in bank before? |
|---|---|---|---|
| `Physics-HLSL-Specimen Papers(First exam 2025)/Specimen Papers 2025 - English.pdf` | 158 | yes | **no** (a stale JSON existed, never imported) |
| `IB DP Preparation/Computer Science 计算机/…/Specimen Papers 2014 - English.pdf` | 141 | **no** | no |

The DB's `Physics HL P1 · 2025 May 1A TZ1/2/3` rows come from the *past-paper* folders, not
the specimen, so the specimen was genuinely absent. Note `Downloads/IB DP Preparation/` is a
much richer parallel tree (3 subjects, many more folders) than `dp learning`.

**Done:** `ocr/extract_specimen.py` + `scripts/import_specimen.mjs` now extract and import
both specimens as `category='mock'` — 93 questions, all with marks, plus 153 crop images:

| paper | questions | marks |
|---|---|---|
| CS HL Specimen Paper 1 (2014) | 15 | 100 (= official total) |
| CS HL Specimen Paper 2 (2014) | 16 | 260 |
| CS HL Specimen Paper 3 (2014) | 8 | 60 |
| Physics HL Specimen Paper 1A (2025) | 40 | 40 (= official total) |
| Physics HL Specimen Paper 1B (2025) | 4 | 20 |
| Physics HL Specimen Paper 2 (2025) | 10 | 87 |

A **"Mock papers"** filter button was added to PracticePage, SearchPage and ExportPage.

---

## 6. Current state / what still needs doing

| item | state |
|---|---|
| Full book extraction pass | **finished** (19/20 books) |
| Book re-import | **done** — 7,538 inserted |
| Duplicate book ids | **still loses rows** (6,976 in DB) — not yet fixed |
| Stale book crop images | still present (Cambridge 981 images vs 120-question JSON case) |
| Specimen / mock papers | **DONE** — 93 rows, `category='mock'` |
| Index-page false positives | need a page/section filter |
| Section-name garbage (Hodder/Haese) | needs heading-quality gate |
| CS 10 missing sessions | deferred by user |
| Math 1995–2007 | deferred by user |
| `PH-TSOKOS-WB`, `MA-PEARSON-2019` | image-only → need OCR |
