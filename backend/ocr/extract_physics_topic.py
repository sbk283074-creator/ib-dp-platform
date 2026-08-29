#!/usr/bin/env python3
"""Extract IB Physics HL topic questions + markscheme answers (Session 11).

Source: ../Physics-HL-Topic questions/
  - 12 core topics: Topic 1 .. Topic 12  (each: HL-paper1/2[/3].pdf + markscheme-*.pdf)
  - 4 options:      Option A .. Option D (Option B names files HL-Paper-N / Markscheme-HL-Paper-N)

DIFFERENCE FROM MATH: Physics markschemes have NO "[N marks]" anchors (most have 0).
Answers are bounded by locating this question's prompt, then cutting at the NEXT
question's prompt (or first "Examiners report" / "Markscheme" header), and stripping
stray header noise + "[N/A]" tokens. Both question and markscheme layers are clean
born-digital text, so prompt matching is reliable (unlike Math's OCR-garbled prompts).

Output:
  backend/public/figures/<FolderSlug>/<paper_slug>/q{i}_p{k}.jpg
  backend/public/figures/<FolderSlug>/<paper_slug>/a{i}_p{k}.jpg
  backend/data/physics_topic_manifest.json

Image paths stored RELATIVE to public/figures/ (e.g. "Topic_1/hl_paper1/q02_p1.jpg").
"""
import os, re, json, glob
import numpy as np
import pypdfium2 as pdfium
from PIL import Image

SRC_ROOT = "/Users/lucas.ma/Downloads/dp learning/Physics-HL-Topic questions"
FIG_ROOT  = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/public/figures"
MANIFEST = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/data/physics_topic_manifest.json"
# Optional override so test runs never clobber the production manifest.
MANIFEST = os.environ.get("PT_OUT", MANIFEST)

SUBJECT = "Physics"
LEVEL = "HL"
CATEGORY = "topic"
SCALE = 2.0
SEP_STD_MAX = 10
SEP_BR_RANGE = (90, 250)
INK_FRAC_MAX = 0.01
HEADER_MAX_PX = 160
SPAN_BOT_FRAC = 0.85


def render_page(page, scale=SCALE):
    return page.render(scale=scale).to_pil().convert("L")


def detect_separator_runs(img_gray):
    arr = np.asarray(img_gray)
    means = arr.mean(axis=1); stds = arr.std(axis=1); ink = (arr < 128).mean(axis=1)
    cand = (stds < SEP_STD_MAX) & (ink < INK_FRAC_MAX) & (means > SEP_BR_RANGE[0]) & (means < SEP_BR_RANGE[1])
    H = arr.shape[0]; runs = []; y = 0
    while y < H:
        if cand[y]:
            y0 = y
            while y < H and cand[y]: y += 1
            runs.append((y0, y - 1))
        else:
            y += 1
    return runs


def page_bands(runs, H):
    if not runs:
        return [(0, H, 'content')]
    bands = [(0, runs[0][0], 'header')]
    prev_end = runs[0][1]
    for i in range(1, len(runs)):
        bands.append((prev_end + 1, runs[i][0], 'content'))
        prev_end = runs[i][1]
    if prev_end < H - 1:
        bands.append((prev_end + 1, H, 'content'))
    return bands


def band_text(page, y_top, y_bot):
    """Extract text within a band using the PDF's natural reading order.

    Filter characters by their charbox y-range (so each visual band maps to the
    right text) but emit them in the PDF's built-in character INDEX order, which
    is the reading order. Sorting by (y, x) was found to scramble multi-line
    Physics text (charbox y is unreliable for ordering here), whereas the raw
    index order is clean and correct for these single-column topic PDFs.
    """
    tp = page.get_textpage()
    n = tp.count_chars()
    if n == 0:
        return ""
    H_pt = page.get_size()[1]
    y_low_pt = H_pt - y_bot / SCALE
    y_high_pt = H_pt - y_top / SCALE
    text = tp.get_text_range()
    sel = []
    for i in range(n):
        cb = tp.get_charbox(i)
        if cb is None:
            continue
        y0, y1 = cb[1], cb[3]
        if y0 <= y_high_pt and y1 >= y_low_pt and i < len(text):
            sel.append((i, text[i]))
    sel.sort(key=lambda c: c[0])  # index order == reading order
    return "".join(c[1] for c in sel).strip()


def render_crop(page, y_top, y_bot, out_path):
    img = page.render(scale=SCALE).to_pil().convert("RGB")
    W = img.width
    pad = 8
    y0 = max(0, int(y_top) - pad)
    y1 = min(img.height, int(y_bot) + pad)
    crop = img.crop((0, y0, W, y1))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    crop.save(out_path, "JPEG", quality=85)
    return out_path


def _is_continuation_signal(text):
    s = (text or "").strip()
    if not s:
        return False
    if re.match(r"^\s*\(([a-z]|ii|iii|iv|vi?|vii)\b", s, re.IGNORECASE):
        return True
    first_alpha = next((c for c in s if c.isalpha()), None)
    if first_alpha and first_alpha.islower():
        return True
    first_word = re.split(r"[\s(]", s, 1)[0].lower().rstrip(",.;:")
    if first_word in {"hence", "therefore", "thus", "so", "also"} and len(s) < 200:
        return True
    return False


def extract_questions(doc):
    pages = []
    for pi in range(len(doc)):
        img = render_page(doc[pi])
        runs = detect_separator_runs(img)
        bands = page_bands(runs, img.height)
        if bands:
            (yt0, yb0, k0) = bands[0]
            first_text = band_text(doc[pi], yt0, yb0)
            is_real_title = (bool(first_text) and TITLE_LEAD.match(first_text) is not None and len(first_text) < 100)
            # Keep band0 as 'header' (so it is skipped) when it is either empty
            # or a real "HL Paper N" title. Only reclassify to 'content' when it
            # actually holds question text (e.g. a continuation/page-top
            # question). This avoids turning an empty top-margin band into a
            # phantom q01 that shifts every later question's number.
            if first_text and not is_real_title:
                bands[0] = (yt0, yb0, 'content')
        has_header = bool(bands) and bands[0][2] == 'header'
        first_content_text = ""
        for (yt, yb, kind) in bands:
            if kind == 'content':
                first_content_text = band_text(doc[pi], yt, yb)
                break
        pages.append({'pi': pi, 'bands': bands, 'has_header': has_header,
                      'H': img.height, 'first_content_text': first_content_text})

    questions = []
    for idx, p in enumerate(pages):
        prev_last_reached_bottom = False
        if idx > 0:
            prev = pages[idx - 1]
            prev_content = [b for b in prev['bands'] if b[2] == 'content']
            if prev_content:
                _, yb, _ = prev_content[-1]
                prev_last_reached_bottom = yb >= SPAN_BOT_FRAC * prev['H']
        first_content_on_page = True
        for (yt, yb, kind) in p['bands']:
            if kind == 'header':
                continue
            is_continuation = (first_content_on_page and not p['has_header']
                               and prev_last_reached_bottom and bool(questions)
                               and _is_continuation_signal(p['first_content_text']))
            first_content_on_page = False
            if is_continuation:
                questions[-1]['bands'].append((p['pi'], yt, yb))
            else:
                questions.append({'bands': [(p['pi'], yt, yb)]})
    out = []
    for qi, q in enumerate(questions, start=1):
        pages_set = sorted(set(b[0] for b in q['bands']))
        out.append({'q_index': qi, 'bands': q['bands'], 'pages': pages_set})
    return out


def normalize(s):
    return re.sub(r"\s+", " ", s or "").strip()


# Cut the prompt at the first option / sub-part label so the matching needle is
# the STABLE question STEM. The options themselves often differ between the
# question PDF and the markscheme (e.g. question "10 μC" vs markscheme "10−12 μC"),
# so including them in the needle breaks the match.
OPTION_CUT = re.compile(r"(?im)\n\s*(?:[a-d]|\([a-d]\)|\(i+\)|[A-D])\s*[\.\)]|\[?\d+\]?\s*marks?")
def stem_needle(text, maxlen=90):
    m = OPTION_CUT.search(text or "")
    cand = text[:m.start()] if m else text
    return normalize(cand).lower().strip()[:maxlen]

# Matches the OCR'd / stylized page-header title that leaks into q01 text.
TITLE_LEAD = re.compile(r"^\s*hl\.?\s*p\w*r\s*\d+\s*p?\s*[\r\n]*", re.I)

def strip_title(text):
    if not text:
        return text
    return TITLE_LEAD.sub("", text).strip()

def is_cover(text):
    raw = (text or "").strip()
    if not raw or not re.search(r"\d", raw):
        return False
    rest = strip_title(raw)
    alnum = re.sub(r"[^a-z0-9]", "", rest.lower())
    return len(alnum) < 3


def build_markscheme_index(ms_doc):
    page_texts = []
    page_char_starts = []
    cursor = 0
    for i in range(len(ms_doc)):
        tp = ms_doc[i].get_textpage()
        t = tp.get_text_range()
        page_texts.append(t)
        page_char_starts.append(cursor)
        cursor += len(t) + 1
    full = "\n".join(page_texts)

    def pos_to_page(p):
        pi = 0
        for i, st in enumerate(page_char_starts):
            if st > p:
                break
            pi = i
        return pi

    page_char_ys = {}
    def get_page_char_ys(pi):
        if pi in page_char_ys:
            return page_char_ys[pi]
        tp = ms_doc[pi].get_textpage()
        n = tp.count_chars()
        ys = []
        for j in range(n):
            cb = tp.get_charbox(j)
            ys.append(((cb[1] + cb[3]) / 2) if cb else 0)
        page_char_ys[pi] = ys
        return ys

    norm_chars = []
    norm_to_raw = []
    i = 0
    while i < len(full):
        ch = full[i]
        if ch.isspace():
            norm_chars.append(' ')
            norm_to_raw.append(i)
            while i < len(full) and full[i].isspace():
                i += 1
        else:
            norm_chars.append(ch.lower())
            norm_to_raw.append(i)
            i += 1
    norm_full = "".join(norm_chars)

    return {'full': full, 'norm_full': norm_full, 'norm_to_raw': norm_to_raw,
            'page_texts': page_texts, 'page_char_starts': page_char_starts,
            'get_page_char_ys': get_page_char_ys, 'pos_to_page': pos_to_page}


# Matches a standalone noise header line we strip from answer text.
HEADER_LINE = re.compile(r"(?im)^\s*(markscheme|examiners report)\s*$")
# Trailing-only trim of "This question is about ..." / "These questions are about
# ..." section dividers that bleed into the END of an answer when it is bounded
# at the next prompt. We deliberately do NOT strip these from the START of an
# answer: there the line is the prompt echo (proof of correct pairing) and
# stripping it would empty answers whose prompt itself begins with that phrase.
DIVIDER_TRAIL = re.compile(r"\s*(?:this question is about|these questions are about)[^\n]*\s*$", re.I)
NA_TOKEN = re.compile(r"\[N/?A\]", re.I)


def _find_stem(stem, prev_end_norm, norm_full):
    """Return the position of the LONGEST prefix of `stem` that occurs at/after
    prev_end_norm, or -1 if even an 8-char prefix is absent.

    Physics question PDFs are partly garbled (diagram-only options drop their text,
    and symbols such as angles render as stray letters). The leading words of the
    stem are intact, though, so matching the longest common prefix recovers the
    prompt location in the (clean) markscheme even when the tail diverged.
    """
    if len(stem) < 8:
        return -1
    for L in range(len(stem), 7, -1):
        pos = norm_full.find(stem[:L], prev_end_norm)
        if pos >= 0:
            return pos
    return -1


def _local_boundary(norm_full, ni, all_stems):
    """Local answer boundary when the IMMEDIATE next question's stem is unfindable.

    We must NOT fall back to end-of-document (that would swallow every later
    question and cascade the failure). Instead bound at the nearest structural
    marker (next '[N/A]' / 'Examiners report'), or — failing that — at the next
    OCCURRENCE OF ANY question stem (the next real prompt). This keeps the cursor
    local so later findable questions are still recovered.
    """
    cands = []
    for tok in ("examiners report", "[n/a]"):
        p = norm_full.find(tok, ni + 1)
        if p > ni:
            cands.append(p)
    if cands:
        return min(cands)
    best = None
    for s in all_stems:
        if len(s) < 8:
            continue
        p = _find_stem(s, ni + 1, norm_full)
        if p > ni and (best is None or p < best):
            best = p
    if best is not None:
        return best
    return min(len(norm_full), ni + 1500)


def extract_answer_for_question(ms_index, q_text, next_q_text, prev_end_norm, all_stems):
    """Return (answer_text, answer_image_paths, end_norm).

    Locate this question's prompt (forward from prev_end_norm), bound the answer
    region at the NEXT question's prompt (or a local structural marker / the next
    real prompt when that prompt is itself unfindable), then strip stray header
    lines + '[N/A]' tokens from the answer text.

    end_norm is the cursor for the NEXT question. On an unfindable prompt we return
    prev_end_norm unchanged so a single bad question can never cascade into its
    neighbours.
    """
    norm_full = ms_index['norm_full']
    norm_to_raw = ms_index['norm_to_raw']
    full = ms_index['full']

    # Match on the STABLE STEM (truncated at the first option/sub-part label).
    # Use the longest-matching prefix: the question PDF is sometimes garbled in
    # its tail/options, but the markscheme prompt is clean, so a prefix match
    # still lands on the correct prompt.
    needle = stem_needle(q_text)
    ni = _find_stem(needle, prev_end_norm, norm_full)
    if ni < 0:
        # Unfindable prompt (garbled/too-short question text). Do NOT advance the
        # cursor; leave a blank answer so later questions are unaffected.
        return "", [], prev_end_norm

    raw_i = norm_to_raw[ni]

    # Boundary = the NEXT question's prompt, or (when that prompt is itself
    # unfindable) a local structural marker / the next real prompt. Never the
    # end of the document.
    if next_q_text:
        nneedle = stem_needle(next_q_text)
        npos = _find_stem(nneedle, ni + 1, norm_full)
        # Guard against a FALSE early match: the next question's stem can
        # coincidentally appear INSIDE this question's echoed prompt (right
        # after `ni`), which would bound the answer to just the prompt echo and
        # make answer == question. The real next-prompt boundary always sits
        # AFTER this question's answer content, so the captured region must be
        # longer than the prompt echo and contain answer markers. If the region
        # is prompt-only (no answer content, length ≈ the question), the match
        # is false — skip to the next occurrence of the same stem.
        q_norm_len = len(re.sub(r"\s+", " ", (q_text or "").lower()))
        while npos > 0:
            region = norm_full[ni:npos]
            prompt_only = (npos - ni) <= q_norm_len + 30 and not _region_has_answer(region)
            if not prompt_only:
                break
            npos2 = _find_stem(nneedle, npos + 1, norm_full)
            if npos2 <= npos:
                break
            npos = npos2
        if npos > ni:
            bound_norm = npos
        else:
            bound_norm = _local_boundary(norm_full, ni, all_stems)
    else:
        # Last question. Normally the answer precedes the trailing "Examiners
        # report" commentary, so we bound at it. But some markschemes append the
        # final answer letter at the START of the examiners-report block (right
        # after "Examiners report"); for those the ni..er region is prompt-only
        # (no answer content) and the real answer would be lost. Detect that and
        # capture only up to the short answer token, stopping before the examiner
        # commentary (first long prose line).
        er = norm_full.find("examiners report", ni + 1)
        if er != -1:
            region_to_er = norm_full[ni:er]
            if _region_has_answer(region_to_er):
                bound_norm = er
            else:
                # Answer sits right after the "Examiners report" header, possibly
                # concatenated with the examiner commentary (no clean line break).
                # Capture only the leading answer token — for these final MCQs the
                # answer is a single letter — stopping before the commentary prose.
                p = er + len("examiners report")
                while p < len(norm_full) and norm_full[p] in "\r\n ":
                    p += 1
                rest = norm_full[p:]
                m = re.match(r"\s*(\S+)", rest)
                if m:
                    end = p + m.end()
                else:
                    end = p
                bound_norm = end
        else:
            bound_norm = len(norm_full)

    cut = bound_norm
    raw_end = norm_to_raw[cut] if cut < len(norm_to_raw) else len(full)
    answer_text = full[raw_i:raw_end]
    # strip noise: standalone Markscheme/Examiners-report header lines + [N/A] tokens
    answer_text = HEADER_LINE.sub("", answer_text)
    answer_text = DIVIDER_TRAIL.sub("", answer_text)
    answer_text = NA_TOKEN.sub("", answer_text)
    answer_text = strip_title(answer_text).strip()
    paths = _render_answer_image(ms_index, raw_i, raw_end)
    # The cursor for the NEXT question is the position of THIS question's prompt
    # (ni), NOT the answer boundary. Decoupling them means a wrong/loose boundary
    # can only corrupt this one answer's length, never the alignment of later
    # questions (which would otherwise cascade into a wall of empty answers).
    end_norm = ni
    return answer_text, paths, end_norm


def _render_answer_image(ms_index, start_char, end_char):
    paths = []
    page_char_starts = ms_index['page_char_starts']
    page_texts = ms_index['page_texts']
    pos_to_page = ms_index['pos_to_page']
    get_page_char_ys = ms_index['get_page_char_ys']
    ms_doc = _MS_DOC
    pi_start = pos_to_page(start_char)
    pi_end = pos_to_page(max(start_char, end_char - 1))
    for pi in range(pi_start, pi_end + 1):
        local_start = max(0, start_char - page_char_starts[pi])
        local_end = min(len(page_texts[pi]), end_char - page_char_starts[pi])
        if local_end <= local_start:
            continue
        ys = get_page_char_ys(pi)
        if local_start >= len(ys) or local_end > len(ys):
            continue
        sub_ys = ys[local_start:local_end]
        y_top = min(sub_ys) - 12
        y_bot = max(sub_ys) + 12
        img = ms_doc[pi].render(scale=SCALE).to_pil()
        H_px = img.height
        py_top = H_px - int(y_bot * SCALE) - 6
        py_bot = H_px - int(y_top * SCALE) + 6
        py_top = max(0, py_top)
        py_bot = min(H_px, py_bot)
        crop = img.crop((0, py_top, img.width, py_bot)).convert("RGB")
        rel = _ANSWER_IMG_PATH(pi)
        out = os.path.join(FIG_ROOT, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        crop.save(out, "JPEG", quality=85)
        paths.append(rel)
    return paths


_MS_DOC = None
_ANSWER_IMG_PATH = None


# --- Page-break split repair -------------------------------------------------
# The question paper (and the markscheme, which mirrors it) sometimes split a
# single question across a page boundary. The question PDF then yields TWO
# extracted questions: the first half (whose markscheme answer degenerates to
# just the prompt echo) and the second half (which absorbs the real markscheme).
#
# Robust, layout-independent fix: two consecutive extracted questions are the
# SAME question (page-break continuation) iff the markscheme region between
# their prompt positions contains NO answer content (only prompt echo + header
# noise). A genuine new question always has its answers between its prompt and
# the next prompt, so that region contains answer markers.
#
# MCQ papers have no "[N marks]"/«»/award markers, so we use a dedicated rule:
# merge when the previous question has no options (a bare stem) and the current
# one STARTS with option lines (the options were pushed to the next page).

def _region_has_answer(region):
    if re.search(r"\[\d+\s*marks?\]", region, re.I):
        return True
    if "«" in region:
        return True
    if re.search(r"\baward\b", region, re.I):
        return True
    if re.search(r"\[N/?A\]", region, re.I):
        return True
    return False


def _has_options(text):
    return len(re.findall(r"^\s*[A-D]\.\s", text or "", re.M)) >= 3


def _starts_with_options(text):
    return bool(re.match(r"^\s*[A-D]\.\s", text or ""))


def _last_option_letter(text):
    """Last MCQ option letter (A-D) appearing as a line-start in `text`, or None."""
    letters = [m.group(0)[0] for m in re.finditer(r"^[A-D]\.\s*", text or "", re.M)]
    return letters[-1] if letters else None


def _first_option_letter(text):
    m = re.match(r"^\s*[A-D]\.\s*", text or "")
    return m.group(0)[0] if m else None


def _join_questions(a, b):
    return (a or "") + "\n\n" + (b or "")


def repair_mcq_option_spill(questions, qtexts):
    """Merge question-paper MCQ option-spill fragments.

    Sometimes an MCQ's later option(s) are pushed onto the next page/band, so the
    extractor yields fragment i = "...A. … B. … C." and fragment j =
    "D. <option text>" (possibly followed by the next real question on the same
    page). The markscheme keeps all options together, so the markscheme-based
    merge cannot see this split and would instead wrongly cascade (j's stray
    option line matches inside i's echoed prompt, dragging the real next question
    into j). We repair it at the question-paper level: if fragment j STARTS with
    the option letter immediately after fragment i's last option letter, j is a
    continuation of i's options and is merged into i (bands + text), then
    consumed. Two genuinely separate questions never satisfy this (a new question
    starts with prose, not the next option letter).
    """
    out_q = []
    out_t = []
    for idx in range(len(qtexts)):
        t = qtexts[idx]
        q = questions[idx]
        if t is None:
            out_q.append(q)
            out_t.append(None)
            continue
        fj = _first_option_letter(t)
        if fj and out_t:
            li = _last_option_letter(out_t[-1])
            if li is not None and ord(fj) - ord(li) == 1:
                prev_q = dict(out_q[-1])
                prev_q['bands'] = list(prev_q['bands']) + list(q['bands'])
                prev_q['pages'] = sorted(set(prev_q.get('pages', [])) | set(q.get('pages', [])))
                out_t[-1] = (out_t[-1] or "") + "\n\n" + t
                # consume j: prepend its bands/text to i, do not emit separately
                continue
        out_q.append(q)
        out_t.append(t)
    return out_q, out_t


# Topic-divider lines that open a NEW real question in the markscheme. A
# page-break *continuation* fragment NEVER starts with one of these (it is a
# mid-prompt phrase), so the next divider strictly after a question's prompt is
# a hard upper bound on that question's prompt-echo region: any fragment whose
# prompt starts at (or after) that divider is a genuine new question and must
# not be merged into the previous one. This is what stops the merge from
# swallowing a real next question when the current question's answer region
# happens to lack [N marks]/«/award/[N/A] markers (which would otherwise let
# the 1800-char fallback window reach into the next question's prompt).
DIVIDER_RE = re.compile(r"this question is about|these questions are about", re.I)

def _next_divider(norm_full, after):
    m = DIVIDER_RE.search(norm_full, after + 1)
    return m.start() if m else None

def _answers_start(norm_full, p):
    """Upper bound of the prompt-echo region for the question whose prompt starts
    at `p`: the first answer marker strictly after `p`, but NEVER past the next
    "This question is about" divider (a genuine new question) and never past a
    sane maximum prompt length (page-break continuations are never that long)."""
    MAX_ECHO = 1800
    end = min(p + MAX_ECHO, len(norm_full))
    m = re.search(r"\[\d+\s*marks?\]|«|\baward\b|\[N/?A\]", norm_full[p:end])
    if m:
        end = min(end, p + m.start())
    nd = _next_divider(norm_full, p)
    if nd is not None:
        end = min(end, nd)
    return end


def merge_questions_with_ms(questions, qtexts, ms_index, debug=False):
    """Collapse page-break split fragments using the markscheme as ground truth.

    The markscheme echoes each question's prompt EXACTLY as laid out in the
    question paper (including page breaks), then lists the answers. So a question
    split across a page break yields several extracted "questions" whose prompts
    all sit inside ONE markscheme prompt-echo region — i.e. before that question's
    first answer marker.

    Decision per consecutive pair (current i, candidate j):
      * MCQ split: i has no options (bare stem) and j STARTS with options
        (the options were pushed to the next page) -> merge.
      * Extended split: neither has options, and j's prompt position lies strictly
        between i's prompt position and i's first answer marker -> j's prompt is
        just more of i's echoed prompt (page-break continuation) -> merge.
      * Otherwise -> keep separate (j is a genuine new question).
    Prompt positions are found with an ADVANCING cursor so a question never
    re-matches its own echo. Returns a list of {'bands': [...], 'text': str}.
    """
    norm_full = ms_index['norm_full']
    n = len(qtexts)
    nis = [None] * n
    cursor = 0
    for idx in range(n):
        qt = qtexts[idx]
        if qt is None:
            continue
        needle = stem_needle(qt)
        ni = _find_stem(needle, cursor, norm_full)
        nis[idx] = ni
        if ni >= 0:
            cursor = ni + 1
    merged = []
    report = []
    k = 0
    while k < n:
        qt_k = qtexts[k]
        if qt_k is None or nis[k] is None:
            if qt_k is not None:
                merged.append({'bands': list(questions[k]['bands']), 'text': qt_k})
            k += 1
            continue
        cur_bands = list(questions[k]['bands'])
        cur_text = qt_k
        cur_ni = nis[k]
        j = k + 1
        while j < n:
            qt_j = qtexts[j]
            if qt_j is None or nis[j] is None:
                # Unfindable/cover fragment between two real fragments. DO NOT
                # break here — that would block a legitimate page-break merge when
                # the continuation fragment sits just past the gap (e.g. a
                # preamble fragment, then a None cover, then the question body).
                # The actual merge is still gated on nis[j]'s position later, so
                # skipping a None can never wrongly join two genuine questions.
                j += 1
                continue
            prev_opt = _has_options(cur_text)
            curj_opt = _has_options(qt_j)
            curj_starts_opt = _starts_with_options(qt_j)
            do_merge = False
            if (not prev_opt) and curj_starts_opt:
                do_merge = True                       # MCQ stem + options fragment
            elif (not prev_opt) and cur_ni is not None and nis[j] is not None:
                echo_end = _answers_start(norm_full, cur_ni)
                if cur_ni <= nis[j] < echo_end:
                    do_merge = True
            if debug:
                report.append((k, j, prev_opt, curj_starts_opt, curj_opt,
                               cur_ni, nis[j], _answers_start(norm_full, cur_ni), do_merge))
            if not do_merge:
                break
            cur_bands.extend(questions[j]['bands'])
            cur_text = _join_questions(cur_text, qt_j)
            j += 1
        merged.append({'bands': cur_bands, 'text': cur_text})
        k = j
    if debug:
        return nis, merged, report
    return merged


def find_markscheme(fdir, paper_raw):
    target = "markscheme-" + paper_raw.lower() + ".pdf"
    for f in os.listdir(fdir):
        if f.lower() == target:
            return os.path.join(fdir, f)
    return None


def main():
    global _MS_DOC, _ANSWER_IMG_PATH
    records = []
    only = os.environ.get('PT_TOPIC')  # optional: restrict to one folder, e.g. "Topic 1"

    for folder in sorted(os.listdir(SRC_ROOT)):
        fdir = os.path.join(SRC_ROOT, folder)
        if not os.path.isdir(fdir):
            continue
        if only and folder != only:
            continue
        folder_slug = folder.replace(" ", "_")   # Topic 1 -> Topic_1, Option A -> Option_A
        qfiles = [f for f in os.listdir(fdir)
                  if f.lower().endswith('.pdf') and 'markscheme' not in f.lower()]
        for qf in sorted(qfiles):
            paper_raw = qf[:-4]
            m = re.search(r"(\d+)", paper_raw)
            num = m.group(1) if m else ""
            paper_type = f"HL-paper{num}"      # DB label (uniform)
            paper_slug = f"hl_paper{num}"      # figure-path component
            qpath = os.path.join(fdir, qf)
            mspath = find_markscheme(fdir, paper_raw)
            if not mspath:
                print(f"  SKIP (no markscheme): {folder}/{paper_raw}")
                continue

            topic_dir = os.path.join(FIG_ROOT, folder_slug, paper_slug)
            os.makedirs(topic_dir, exist_ok=True)

            q_doc = pdfium.PdfDocument(qpath)
            ms_doc = pdfium.PdfDocument(mspath)
            _MS_DOC = ms_doc

            questions = extract_questions(q_doc)
            ms_index = build_markscheme_index(ms_doc)

            # Pass 1: question texts (+ cover/blank detection)
            qtexts = []
            for qi, q in enumerate(questions, start=1):
                parts = []
                for (pi, yt, yb) in q['bands']:
                    t = band_text(q_doc[pi], yt, yb)
                    if t:
                        parts.append(t)
                raw = "\n\n".join(parts)
                if is_cover(raw) or len(raw.strip()) < 5:
                    qtexts.append(None)
                    print(f"  SKIP cover/blank: {folder} {paper_raw} q{qi:02d}")
                else:
                    qtexts.append(strip_title(raw))

            # Pass 1.25: repair MCQ option-spill at the question-paper level
            # (later option(s) pushed onto the next page/band). Must run before
            # the markscheme merge, which cannot see this split.
            questions, qtexts = repair_mcq_option_spill(questions, qtexts)

            # Pass 1.5: collapse page-break split fragments using the markscheme.
            merged = merge_questions_with_ms(questions, qtexts, ms_index)
            n_before = sum(1 for t in qtexts if t is not None)
            n_after = len(merged)
            if n_after != n_before:
                print(f"  MERGED splits: {folder} {paper_raw}: {n_before} -> {n_after} "
                      f"(-{n_before - n_after})")
            questions = [{'bands': m['bands'], 'q_index': i + 1,
                          'pages': sorted(set(b[0] for b in m['bands']))}
                         for i, m in enumerate(merged)]
            qtexts = [m['text'] for m in merged]

            # Pass 2: answers (with lookahead to next real question)
            def next_real_text(from_idx):
                for j in range(from_idx, len(qtexts)):
                    if qtexts[j] is not None:
                        return qtexts[j]
                return None

            # Pre-compute every question's stem so that, when one question's prompt
            # is unfindable, the answer boundary can fall back to the NEXT real
            # prompt (any stem) instead of end-of-document (which would cascade).
            all_stems = [stem_needle(t) for t in qtexts if t]

            prev_end_norm = 0
            real_qi = 0
            for qi, q in enumerate(questions, start=1):
                qtext = qtexts[qi - 1]
                if qtext is None:
                    continue
                real_qi += 1
                q_imgs = []
                for bi, (pi, yt, yb) in enumerate(q['bands'], start=1):
                    outp = os.path.join(topic_dir, f"q{real_qi:02d}_p{bi}.jpg")
                    render_crop(q_doc[pi], yt, yb, outp)
                    q_imgs.append(os.path.relpath(outp, FIG_ROOT).replace(os.sep, "/"))

                nxt = next_real_text(qi)  # next non-skipped question text
                def _a_path(pi):
                    return os.path.relpath(os.path.join(topic_dir, f"a{real_qi:02d}_p{pi + 1}.jpg"),
                                           FIG_ROOT).replace(os.sep, "/")
                _ANSWER_IMG_PATH = _a_path
                answer_text, a_imgs, prev_end_norm = extract_answer_for_question(
                    ms_index, qtext, nxt, prev_end_norm, all_stems)
                answer_text = strip_title(answer_text)

                src = f"Physics_HL_{folder_slug}_{paper_type}_q{real_qi:02d}"
                rec = {
                    'id': src.replace('Physics_HL_', 'PH_HL_'),
                    'source': src,
                    'subject': SUBJECT,
                    'level': LEVEL,
                    'category': CATEGORY,
                    'topic': folder,
                    'paper_type': paper_type,
                    'question_text': qtext,
                    'answer_text': answer_text,
                    'question_image': ",".join(q_imgs),
                    'answer_image': ",".join(a_imgs),
                    'marks': None,
                    'review_status': 'new',
                    'command_term': None,
                }
                records.append(rec)
                print(f"  {folder} {paper_raw} Q{real_qi:02d}: q_imgs={len(q_imgs)} a_imgs={len(a_imgs)} "
                      f"text_q={len(qtext)}c text_a={len(answer_text)}c")

    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(records)} records to {MANIFEST}")


if __name__ == '__main__':
    main()
