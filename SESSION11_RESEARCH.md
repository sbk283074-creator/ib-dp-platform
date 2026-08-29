# Session 11 — Physics HL Topic Questions · RESEARCH (Phase A, read-only)

> Status: **RESEARCH COMPLETE. STOP-AND-WAIT** — awaiting your `start` / `scan` / `detect`
> before any extraction. Proposal below; nothing written to DB or figures yet.

## 1. Source inventory
- **Root:** `../Physics-HL-Topic questions/` (sibling of the other source PDFs, OUTSIDE `ib-dp-platform/`).
- **16 groups:** 12 core topics (`Topic 1`–`Topic 12`) + 4 options (`Option A`–`Option D`).
- **Papers present per group:**
  | Group | Papers |
  |---|---|
  | Core Topics 1–3,5,6,8,10,11 | `HL-paper1`, `HL-paper2` |
  | Core Topics 4,7,9,12 | `HL-paper1`, `HL-paper2`, **`HL-paper3`** |
  | Option A / C / D | `HL-paper3` only |
  | Option B | `HL-Paper-1`, `HL-Paper-2`, `HL-Paper-3` |
- **Naming inconsistency (important):**
  - Core + Options A/C/D: `HL-paperN.pdf` / `markscheme-HL-paperN.pdf` (lowercase).
  - **Option B:** `HL-Paper-N.pdf` / `Markscheme-HL-Paper-N.pdf` (capital **P** in "Paper", capital **M** in "Markscheme").
- **Volume:** 537 question pages + 916 markscheme pages. **~1,057 estimated question records** (band-count upper bound; exact count set at extraction).

## 2. Text layer (feasibility) — all clean
- Every sampled + every scanned PDF is **born-digital TEXT** (370–39,517 chars; 0 scanned flags).
- ~450–1,100 chars/page → no OCR garble. **This is better than Math** (whose questions were OCR-mangled). Prompt→markscheme matching will be far more reliable here.
- **No cover-only pages** (`is_cover`=False on every page 1). The `is_cover()`/`strip_title()` guard from Math is still carried over as a safety net.

## 3. Question structure (maps directly to Math extractor)
- Questions are separated by **light horizontal rule lines** → the `extract_math_topic.py` separator-band detector ports as-is.
- **Two question styles in the source:**
  1. **Multiple-choice (MCQ):** Topic 1, all Options A–D, and many core papers. Each = stem + `A./B./C./D.` options. Answer = a single letter.
  2. **Structured/written:** Topic 12 (and likely others) — prompt with `a.`/`b.`/`c.` and `(i)`/`(ii)`; written solutions. Marks shown **inline** as `[3]`, `[1]` (NOT `[N marks]`).
- One record per question (sub-parts kept together in one text block), same as Math.

## 4. Markscheme / answer structure — THE KEY DIFFERENCE FROM MATH
- Markschemes **repeat the full question prompt**, then the solution. ✅ (prompt matching viable)
- **NO `[N marks]` anchors** in most markschemes (Topic 1 / 12 / Option B = 0; only Option A had 21). → **Math's answer-bounding-by-`[N marks]` will NOT work for Physics.**
- Markschemes **interleave `Examiners report` and `Markscheme` header noise** (Topic 1 top shows `Markscheme / Examiners report / Markscheme / Examiners report`; Option B has 34 such headers). MCQ answers also carry a trailing **`[N/A]`** token.
- Two observed markscheme formats:
  - **MCQ:** `prompt + options → correct letter (e.g. "D") → [N/A] → (next prompt)`, with occasional stray headers.
  - **Structured:** `prompt a.[3] b.[1] → solutions → "Examiners report" commentary`.

## 5. Proposed answer-extraction rule (replaces Math's `[N marks]` bound)
For each question `i` (processed in order; prompts are unique & clean):
1. **Locate** `prompt_i` in the markscheme text (forward search from `prev_end`; alpha-normalized first ~60–80-char needle — high reliability since both layers are clean text).
2. **Bound** the answer region = `markscheme[pos_i : pos_{i+1}]`, where `pos_{i+1}` = the **next question's prompt** (or end-of-doc for the last). → order-preserving, robust.
3. **Strip trailing `Examiners report`** (cut at the first "Examiners report" after the prompt) so commentary never leaks into the answer.
4. **Strip noise tokens** within the region: standalone `Markscheme` / `Examiners report` header lines and `[N/A]`.
5. **Render** the answer image from that exact char-span (reuse `_render_answer_image`, already saves to absolute path under `FIG_ROOT`).

> This is actually **more robust** than Math's `[N marks]` approach: it doesn't depend on marks anchors that don't exist, and it's immune to the OCR-garble that broke Math's pairing (Physics text is clean).

## 6. Text↔image (figure) relationship
- Same as Math (Rule #5): each question band → `qNN_pK.jpg`; answer → `aNN_pK.jpg` from the markscheme char-span.
- Figures (circuits, graphs, diagrams) are **inline** in the question page and captured by the band crop — no separate figure-keying needed. The band crop is the visual source of truth.
- **Path convention (carried GOTCHA):** stored **relative to `public/figures/`** (e.g. `Topic_1/hl_paper1/q01_p1.jpg`); `FIG_ROOT = .../public/figures`; answer saved to `os.path.join(FIG_ROOT, relpath)`.

## 7. Proposed config for `extract_physics_topic.py` (cp of `extract_math_topic.py`)
- `SRC_ROOT = .../Physics-HL-Topic questions`
- `SUBJECT = "Physics"`, `LEVEL = "HL"`, `CATEGORY = "topic"`
- **Paper slug canonicalized → `hl_paperN`** (so Option B `HL-Paper-1` and core `HL-paper1` both → `hl_paper1`; avoids divergent figure folders).
- **Folder slug:** `Topic 1`→`Topic_1`, `Option A`→`Option_A`.
- **Markscheme resolution: case-insensitive** (handles Option B's capital `Markscheme-`).
- **source/id:** `Physics_HL_Topic{tn}_{paper}_q{NN}` → id `PH_HL_topic_{tn}_{paper}_q{NN}` (Options: `PH_HL_option{A}_{paper}_q{NN}`).
- **Reuse:** separator detection, cover guard, cross-page merge, `_render_answer_image`, `is_cover`/`strip_title`.
- **Replace** `extract_answer_for_question` with the prompt→next-prompt + `Examiners report`-strip rule (§5).

## 8. Scope decision for you (please confirm)
- **(A) Include ALL 16 groups** (Topics 1–12 + Options A–D) in this one session (~1,057 est. records). *(Recommended — they are all topic-style questions in one folder.)*
- **(B) Core topics only (1–12)**, defer Options A–D to a separate session.

## 9. Open items / risks
- ~1,057 is a band-based **upper-bound estimate**; final count set at extraction.
- MCQ answers are a single letter — acceptable (prompt + options + letter retained in `answer_text`); some MCQ answer images will be thin.
- `marks` / `command_term` left `NULL` (like Math) unless we parse inline `[N]` (optional).
- Environment note: `pypdfium2` was **not** present in any discovered Python; installed into the managed venv (`/Users/lucas.ma/.workbuddy/binaries/python/envs/default/bin/python`). Run extractor with that interpreter going forward.
