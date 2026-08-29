# IB DP PLATFORM — MASTER PLAN (CLEAN REBUILD: questions + answers)

> Single source of truth for a **full wipe-and-rebuild** of the question
> database. Read this file + the STATUS block at the start of EVERY session.
> Last updated: 2026-08-24.
>
> Goal: delete everything, then re-import every book / past paper / topic file
> **with its answer attached in the same job** (never a separate end phase),
> verified per item, one target at a time, in a way that survives agent context
> resets (no error cycles).

---

## 0. Hard constraints + the decisive finding

1. **The agent CANNOT view images.** Screenshots cannot be verified by eye.
   This is why the old "screenshot" pipeline was blind and produced "errors
   everywhere" — we could never confirm a crop/segment was right.
2. **Two failed/weak approaches (do NOT reuse):**
   - Screenshots from solution PDFs → deterministic matching but unverifiable
     result. Keep only as a cosmetic `answer_image`, never as source of truth.
   - "AI detect text, copy the original picture" → unreliable (user-tested).
3. **Agent context can truncate on long sessions** → externalise all state to
   this file + STATUS; make every step idempotent; verify via the DB.

### 🔑 FEASIBILITY FINDING (answers the user's real question)

**Can past-paper questions be picked efficiently AND accurately?  YES — because
the paper PDFs are born-digital TEXT PDFs, not scans.**

I probed the actual source PDFs with `pypdfium2` (the same engine that cleanly
extracted the Math textbooks → 732 accurate questions):

| Source | Sample | Text-layer chars | Verdict |
|---|---|---|---|
| Math past 2024.11 P1 | `IB 数学 AA HL 历年真题/2024.11HL/...` | 10,092 | ✅ text |
| Math topic T1 HL-paper1 | `IB数学AA HL 分章练习/.../Topic 1/` | 24,265 | ✅ text |
| Physics past 2024.11 P1 | `Physics-HL-Past Papers.../2024.11/` | 15,714 | ✅ text |
| Physics past 2010 P1 | `.../2010 May.../` | 14,619 | ✅ text |
| Physics OLD 1999 P1 | `.../1999 May.../` | **0** | ❌ SCANNED |
| CS past 2024.11 P1 | `Computer Science-HL-Past.../2024.11/` | 10,319 | ✅ text |
| CS past 2010 P1 | `.../2010 May.../` | 7,389 | ✅ text |
| Markschemes (Math/Phys/CS 2024.11) | — | 26k / 3.6k / 27k | ✅ text |

- **~99% of papers (Physics ≥2000, CS ≥2002, all Math) have a clean text layer.**
- **Only the oldest (Physics 1999, and a few sparse early-CS years) are scanned**
  (0 chars). These are excluded by a minimum-year filter — no OCR needed.
- **Markschemes are ALSO text-based** → answers are extractable as TEXT, keyed by
  question number. This validates the text-anchored answer strategy.

**Conclusion:** the screenshot engine (`screenshot_questions.py`, driven by
`run_corpus.py`) is the WRONG tool for these sources and is the root cause of the
"errors everywhere." Replace it with a **text-layer paper extractor** built on
the proven `booklib.py` / `pypdfium` approach. Accuracy becomes high and
*verifiable* (we read the text + count rows), eliminating the blind spot.

---

## 1. DECISION — clean rebuild, text-layer extraction, combined Q+A

1. **Wipe first.** Drop all rows from `questions` (and reset `books` to the
   known textbook set). Rebuild from zero so no AI-generated / mis-split junk
   survives. Idempotent: any target can be re-run safely.
2. **Text-layer extraction for EVERYTHING** (books + papers + topics):
   - Questions: detect question numbers from the PDF text layer, segment into
     bands, render each band to a JPG (`question_image`) + keep the extracted
     text (for search/QA). This is exactly what `extract_books.py` does for
     textbooks and is proven accurate.
   - For papers, this replaces the screenshot engine entirely.
3. **Answers attached in the SAME job** (combined, not a final phase):
   - Pull answer TEXT from the matching mark-scheme / solution PDF's text layer,
     keyed by `(paper_code, question_number)`. Stored in `answer`.
   - P1 multiple-choice → answer = the mark-scheme letter (e.g. "1. A 16. C").
   - P2/P3 → answer = the mark-scheme solution text.
   - Where a solution renders cleanly, ALSO save `answer_image` (cosmetic).
   - Where no mark scheme / solution exists → AI-generate answer text from the
     question (pre-approved for no-solution sources).
4. **One target at a time, sequential, wait for go-ahead** (user directive).

---

## 2. Scope — what gets imported (with year boundary)

Textbooks (`source_type='book'`) — re-extract all 9 with the proven engine:

| Book ID | Engine | Answer source |
|---|---|---|
| CS-OX-2025 | `extract_books.py` | confirm solution PDF |
| MA-HAESE-AA2 | `extract_books.py` | Haese WORKED SOLUTIONS (or AI) |
| MA-HAESE-CORE1 | `extract_books.py` (visual splitter ✓) | Haese ✓ |
| MA-HODDER-2019 | `extract_books.py` | Hodder answers |
| MA-HODDER-WB | `extract_books.py` | Hodder ✓ |
| MA-OXFORD-2019 | `extract_books.py` | Oxford answers |
| PH-CAMB-WB | `extract_books.py` | Cambridge ✓ |
| PH-OX-2023 | `extract_books.py` (gating ✓) | Physics ANSWERS ✓ |
| PH-TSOKOS-WB | `extract_books.py` | Tsokos ✓ |

Past papers + topic files (`source_type='paper'`) — NEW text-layer engine:

| Set | Source folder | Min year | ~PDFs |
|---|---|---|---|
| Physics past | `Physics-HL-Past Papers&Mark Schemes(1999.05~2025.11)` | **2000** (excludes scanned 1999) | ~213 |
| CS past | `Computer Science-HL-Past Papers&Mark Schemes(1999.05~2025.05)` | **2002** (sparse earlier) | ~135 |
| Math past | `IB 数学 AA HL 历年真题` | all | small (recent + 2006–23 set) |
| Physics topic | `Physics-HL-Topic questions` | all | ~per-Topic papers |
| Math topic | `IB数学AA HL 分章练习` | all | 28 |

Exclude: French/Spanish/German language variants; the 1999 scanned Physics set;
any PDF with a near-empty text layer (auto-skip + log, do not OCR).

---

## 3. Per-target procedure (combined, sequential, idempotent)

For EACH target:
1. **Extract questions** (atomic DELETE+INSERT per target; safe to re-run):
   - Textbooks → `reimport_book.py --book <ID>` (already proven).
   - Papers/topics → the NEW `extract_papers_text.py` (text-layer engine; see §6).
2. **Attach answers for that SAME target** (in the same job):
   - Books with solution PDF → keyed text extractor (Haese / Oxford patterns).
   - Papers → mark-scheme text extractor keyed by `(paper_code, qnum)`.
   - No source → `generate_answers_ai.py` (LLM answer + explanation).
3. **Verify** with §7 SQL: row count sane, answer coverage %, and a text
   spot-check of a couple of questions to confirm no merge/leak.
4. **Checkpoint** → update STATUS (§8).
5. Next target. **Never parallel.**

---

## 4. Answer strategy by source

| Source | Answer source | Stored in |
|---|---|---|
| Haese textbooks | Haese WORKED SOLUTIONS (text) | `answer` (+`answer_image`) |
| Oxford Physics | Physics ANSWERS (text) | `answer` (+`answer_image`) |
| Other textbooks w/ solution PDF | that PDF (text) | `answer` |
| Textbooks w/o solution | — | AI-gen `answer` |
| Past papers P1 (MCQ) | mark scheme letter | `answer` (letter) |
| Past papers P2/P3 | mark scheme solution text | `answer` (+`answer_image`) |
| Topic files | mark scheme / AI | same as papers |

`answer` is authoritative. `answer_image` is cosmetic only.

---

## 5. Sequencing (user-specified: plan first, wait for go-ahead)

- **Phase 0** — build the text-layer paper engine `extract_papers_text.py`:
  segment paper PDFs by question number from the text layer, render bands to
  JPG, extract text; plus a mark-scheme answer extractor. Validate on 1 paper
  per subject (count questions, eyeball text) BEFORE any bulk run.
- **Phase 1** — wipe DB; re-import the 9 textbooks one at a time (combined Q+A).
- **Phase 2** — papers + topic files, one subject/batch at a time (combined Q+A).
- **Phase 3** — QA / UI (rebuild `frontend/dist`; restart `:3099`).

---

## 6. Paper engine design (`extract_papers_text.py`) — replaces screenshot

Reuses `backend/ocr/booklib.py` primitives (already imported by `extract_books.py`):

1. **Open** paper PDF with `pypdfium2`; for each content page get the textpage.
2. **Segment** by detecting question-number lines via regex on the text:
   - Numbered top-level questions: `^\s*(\d+)\.\s` , `^\s*(\d+)\s*\[Maximum mark`,
     and section headers (`Section A`, `Section B`, `Answer all questions`).
   - Keep multi-part questions (a, b, c / a.i, a.ii) under ONE row (matches the
     existing DB convention of "one paper question = one row").
   - Use the text-layer line `y` (from `pdfium_lines`) to compute band y0/y1.
3. **Render** each band to a JPG (`question_image`) — text defines WHERE,
   rendering gives exact pixels (incl. inline figures). No full-page visual
   question detection → removes the fragile step that caused errors.
4. **Store** `question_image` + extracted text + parsed `source`/`topic`/metadata.
5. **Answers:** open the matching `*-markscheme*.pdf`; locate each question's
   answer block by the same qnum regex; for P1 copy the letter, for P2/P3 copy
   the solution text; key by `(paper_code, qnum)` → join onto the question row.
6. **Idempotent + report:** DELETE+INSERT per paper; print counts per paper so
   the §7 check is trivial. Auto-skip near-empty-text PDFs (scanned) with a log.

The engine is fast (no OCR, no screenshots) and verifiable (we read text + counts).

---

## 7. Verification SQL (run after every target; trust the DB, not memory)

```sql
-- counts + answer coverage for one source/target
SELECT source,
       COUNT(*) AS questions,
       SUM(CASE WHEN answer_image IS NOT NULL AND answer_image<>'' THEN 1 ELSE 0 END) AS ans_img,
       SUM(CASE WHEN answer        IS NOT NULL AND answer<>''        THEN 1 ELSE 0 END) AS ans_text
FROM questions WHERE source LIKE '<PATTERN>' GROUP BY source;

-- confirm a paper page yields consecutive, non-merged questions
SELECT source, book_page, COUNT(*) FROM questions
WHERE source='<PAPER_CODE>' GROUP BY book_page ORDER BY book_page;

-- post-wipe sanity: total must be 0 before Phase 1 starts
SELECT COUNT(*) FROM questions;
```

Healthy sign: a paper page shows consecutive question numbers with no gaps and
no "Question N" merged into the previous row.

---

## 8. STATUS (checkpoint — update after every target)

Legend: ⬜ todo · 🟡 in progress · ✅ done

### Phase 0 — paper engine
- ⬜ Build `extract_papers_text.py` (text-layer segment + band render)
- ⬜ Build mark-scheme answer extractor
- ⬜ Validate on 1 paper per subject (Math/Phys/CS) → confirm counts + text

### Phase 1 — wipe + 9 textbooks (combined Q+A)
- ⬜ **WIPE** `questions` (count → 0), reset `books`
- ⬜ CS-OX-2025
- ⬜ MA-HAESE-AA2 (top gap: 0 answers)
- ✅ MA-HAESE-CORE1 (done)
- ⬜ MA-HODDER-2019
- ⬜ MA-HODDER-WB
- ⬜ MA-OXFORD-2019
- ⬜ PH-CAMB-WB
- ✅ PH-OX-2023 (done)
- ⬜ PH-TSOKOS-WB

### Phase 2 — papers + topic files (combined Q+A)
- ⬜ Physics past (≥2000)
- ⬜ CS past (≥2002)
- ⬜ Math past
- ⬜ Physics topic
- ⬜ Math topic

### Phase 3 — other
- ⬜ QA / UI / rebuild frontend dist / restart :3099

---

## 9. Memory-safe operating rules (anti error-cycle)

1. **Start every session by reading this file + STATUS.** Do not re-derive from
   conversation memory.
2. **One target at a time. Never parallel.** Slowness accepted; concurrent-run
   errors are not.
3. **Every script idempotent** (DELETE+INSERT per target; answers overwrite per
   id). Re-running is always safe.
4. **Checkpoint after each target** (update STATUS). Resume from next ⬜ item if
   the session resets — progress is on disk.
5. **Verify via the DB** (§7), not memory or assumptions.
6. **If ambiguous, stop and ask.** Do not guess a flag or a solution PDF.
7. **DB is the authority.** `books.total_questions` is unreliable; count from
   `questions`.

---

## 10. Open items (confirm in-session, not blocking the plan)

- Confirm `books` reset list (the 9 textbook IDs above) at wipe time.
- Decide P1 MCQ answer granularity (whole question letter vs per-option) — default
  whole-question letter.
- Confirm which textbooks have a real solution PDF (route the rest to AI-gen).
- Confirm the Math past folder's full paper count (it mixes recent + a 2006–23
  merged set; count it properly in Phase 0).
