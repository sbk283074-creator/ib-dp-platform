# SESSION 10 RESEARCH — Math AA HL Topic Questions

**Status:** RESEARCH ONLY — not started. Awaiting `start` / `scan` / `detect` before building extractor.

## Source location
`/Users/lucas.ma/Downloads/dp learning/IB数学AA  HL 分章练习/IB数学AA-Mathmatics HL IB Question Bank/`
(Note: double space in `IB数学AA  HL`.)

Mirror of the Physics topic layout — per-topic booklets, each with questions + a separate markscheme PDF.

## Scope (verified)
- **10 topics** (Topic 1–10).
- Most topics: `HL-paper1.pdf`, `HL-paper2.pdf`, `HL-paper3.pdf` + `markscheme-HL-paperN.pdf` (×3).
- Topic 3 & Topic 4: only paper1 + paper2 (no paper3).
- **Total: 28 question PDFs + 28 markscheme PDFs.**

## Question structure (verified via text-layer probe)
- Header `HL Paper 1` per booklet.
- Questions are **lettered sub-parts** (`a.`, `b.`, `c.i.`, `c.ii.`) with marks in `[N]`.
- **No explicit top-level `N.` question number** at line start (confirmed: regex `^\s*(\d+)\.\s` found 0 matches in first 3 pages). A new question often begins with a bare statement (e.g. "Find integer values of x and y for which") followed by its parts — so question boundaries are NOT reliably detectable from numbering alone.
- **Visual delimiter = a light horizontal line between questions** (user-confirmed; this is the reliable boundary signal, same across all subjects' topic questions).

## Answer ↔ Question relationship (the focus)
- The **markscheme PDF repeats each question's prompt text**, then gives:
  1. the worked solution (`(A1) M1 A1 N1 [3 marks]` …), then
  2. an `Examiners report` commentary block.
- Therefore answers align to questions **by order / matching prompt text** — identical pattern to past papers (separate markscheme, paired by question).
- `Examiners report` is commentary, not the answer; the answer = the markscheme-solution region (between the prompt and the next prompt / `Examiners report`).

## Proposed extraction approach (to validate in `detect`)
1. **Questions:** render each booklet page to image; detect the **light separator line** between questions; group text + crop a `question_image` per question. Keep normalized text (Rule #5).
2. **Answers:** in the matching `markscheme-HL-paperN.pdf`, locate each question prompt (same text), crop the solution region up to the next prompt / `Examiners report` → `answer_image` + answer text. Pair by prompt/text match.
3. Reuse the past-paper extractor machinery (`pypdfium2` render + `crop_box` band math, idempotent manifest → Node importer). Adjust question-boundary detection from "consecutive number walk" to "light-line + prompt match".
4. Subject = `Mathematics`, category = `topic`, topic = `Topic N`, level = `HL`.
- pypdfium2 is now installed in the canonical venv: `/Users/lucas.ma/.workbuddy/binaries/python/envs/default/bin/python`.

## Open items (resolve at `detect`)
- Confirm light-line detection works on a sample page (rule thickness/color) before full run.
- Decide whether `answer_image` should include the `Examiners report` or trim to solution only (recommend: trim to solution).
- Physics topic questions (Session 11) will follow the SAME structure/source pattern (`Physics-HL-Topic questions/Topic N/`).
