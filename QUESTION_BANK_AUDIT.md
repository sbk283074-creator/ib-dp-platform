# Question Bank Audit — past papers, topic questions, mock papers

Date: 2026-09-12
Scope: the pre-existing 9,969-question bank (`past` 6,977 · `topic` 2,205 · `questionbank` 787)
Audited against the source PDFs in `/Users/lucas.ma/Downloads/dp learning`.

---

## 1. Missing content

### 1.1 Math HL past papers 1995–2007 are entirely absent  ⚠️ biggest gap
The bank's Math coverage starts at **2008**. On disk there are 13 further years of real papers at:

```
IB 数学 AA  HL 历年真题/IB 数学 HL 真题（2006-23）/<year> <May|Nov>/English Papers/
```

| Years | Paper booklets on disk | In bank |
|---|---|---|
| 1995–1996 | ~5 | **0** |
| 1997–2003 | ~4 per session | **0** |
| 2004–2006 | ~6 per session | **0** |
| 2007 | ~9 | **0** |
| 2008 onwards | ~18+ | present |

Roughly **55 paper booklets (~110 PDFs including markschemes)** are unprocessed. These are genuine
IB past papers (e.g. `1995 May/English Papers/Mathematics_paper_1_HL.pdf`), not duplicates.

### 1.2 CS HL — 10 sessions missing
`2001 May`, `2001 Nov`, `2003 Nov`, `2004 May`, `2004 Nov`, `2006 Nov`, `2007 Nov`,
`2008 May`, `2009 May`, `2009 Nov`.

### 1.3 Physics HL — 3 sessions missing
`1999 May`, `1999 Nov`, `2015 Nov`.

### 1.4 Mock papers
There is **no dedicated mock-paper folder**. The nearest equivalent is
`Physics-HLSL-Specimen Papers(First exam 2025)/Specimen Papers 2025 - English.pdf`, which *has*
been parsed — but its questions are stored under labels like `Physics HL P1 · 2025 May 1A TZ1`,
i.e. **presented as real 2025 sessions rather than as a specimen paper**. Worth relabelling.

---

## 2. Wrongly split / low-quality questions

### 2.1 Page footers baked into question text — 1,531 questions
Running footers (IB paper codes) were captured as part of the question, e.g.

```
… A. π 3/4  B. 1  C. 2  D. 8   M16/4/PHYSI/HPM/ENG/TZ0/XX
```

| Family | Affected |
|---|---|
| HL P2 | 306 |
| HL P1 | 295 |
| CS HL P2 | 151 |
| Physics HL P3 | 137 |
| AA HL P2 | 114 |
| Physics HL P1 | 104 |
| AA HL P1 | 99 |
| Physics HL P2 | 94 |

Fix is mechanical: strip `\b[MN]\d{2}\s*/\s*\d\s*/\s*[A-Z]+/…` and similar codes from the tail.

### 2.2 Garbled text — lost word spacing / stripped formulas — 1,126 questions
Concentrated in the **Math AA HL topic questions** (~848 of 2,205) and older **Physics HL P3** (~150):

```
(a)Showthat .(b)Henceprovebyinductionthat , , for all .Slhi(c) ove te equaton .
```

Spaces and many symbols are gone, so these are close to unusable as text. They are still fine as
*images* if re-rendered from the PDF — the same approach the new book extractor uses.

### 2.3 Sub-questions split into separate questions — **only 3 cases**  ✅
Your main worry turned out to be a non-issue in the current bank: just 3 rows start with a bare
sub-label (`b. …`, `(i) …`). No duplicate ids, and **no duplicate (source + text) pairs**.

---

## 3. Structural / metadata problems

| Issue | Detail |
|---|---|
| Duplicate family labels | `CS HL Paper 1` (316) **vs** `CS HL P1` (300); `CS HL Paper 2` (140) **vs** `CS HL P2` (263); `HL P1/P2/P3` **vs** `AA HL P1/P2/P3` — same papers, two naming schemes |
| `paper_type` inconsistent | `Paper 1` (4,001) **vs** `HL-paper1` (887), `HL-paper2` (690), `HL-paper3` (628) |
| Topic `source` unusable for grouping | one source string per question, e.g. `Math_AA_HL_Topic1_HL-paper1_q02` |
| No explanations | **all 9,969** old questions have an empty `explanation` |
| Missing marks | 2,217 of 9,182 past/topic rows (24.1%) have no marks |

---

## 4. Recommended fixes, in priority order

1. **Process the 1995–2007 Math papers** (+ the 10 CS and 3 Physics missing sessions) — biggest
   content win.
2. **Strip IB paper codes / footers** from question tails (1,531 rows, scripted).
3. **Re-extract the garbled Math topic questions** — keep them as rendered images rather than text.
4. **Normalise labels**: unify `CS HL Paper n` → `CS HL Pn`, and `HL Pn` / `AA HL Pn`; unify
   `paper_type` to `Paper n`.
5. **Relabel the specimen paper** so it isn't shown as a real 2025 session.
6. Backfill `marks` and `explanation` where derivable from markschemes.
