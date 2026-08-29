#!/usr/bin/env python3
"""Extract IB Math AA HL topic questions + markscheme answers.

Source: IB数学AA  HL 分章练习/IB数学AA-Mathmatics HL IB Question Bank/Topic N/
  - HL-paper1/2/3.pdf         (questions, separated by light horizontal lines)
  - markscheme-HL-paper1/2/3.pdf (answers; same separators exist but DO NOT align
                                   with question boundaries — use prompt matching)

Output:
  backend/public/figures/Topic{N}/{paper_slug}/q{i}_p{k}.jpg
  backend/public/figures/Topic{N}/{paper_slug}/a{i}_p{k}.jpg
  backend/data/math_topic_manifest.json

Note: image paths stored in the manifest are RELATIVE to public/figures/
(e.g. "Topic_1/hl_paper1/q02_p1.jpg") and served as /figures/<path>.
There is intentionally NO "math_topic/" prefix. The question path uses an
absolute topic_dir under FIG_ROOT; the answer path is computed relative then
resolved to an absolute file under FIG_ROOT before saving.
"""
import os, re, json, glob
import numpy as np
import pypdfium2 as pdfium
from PIL import Image

SRC_ROOT = "/Users/lucas.ma/Downloads/dp learning/IB数学AA  HL 分章练习/IB数学AA-Mathmatics HL IB Question Bank"
FIG_ROOT  = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/public/figures"
MANIFEST = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/data/math_topic_manifest.json"

SUBJECT = "Mathematics"
LEVEL = "HL"
CATEGORY = "topic"
SCALE = 2.0                       # render scale
SEP_STD_MAX = 10                  # separator rows have low std
SEP_BR_RANGE = (90, 250)          # light-line color range (exclude pure white 255)
INK_FRAC_MAX = 0.01               # separator rows have no text ink
HEADER_MAX_PX = 160               # page-header separator y in px (at SCALE=2)
SPAN_BOT_FRAC = 0.85              # band reaching below this = spans to next page

PAPER_TYPES = ["HL-paper1", "HL-paper2", "HL-paper3"]
MS_PREFIX = "markscheme-"


def render_page(page, scale=SCALE):
    return page.render(scale=scale).to_pil().convert("L")


def detect_separator_runs(img_gray):
    """Return list of (y0, y1) for runs of separator rows (light uniform, no ink)."""
    arr = np.asarray(img_gray)
    means = arr.mean(axis=1)
    stds = arr.std(axis=1)
    ink = (arr < 128).mean(axis=1)
    cand = (stds < SEP_STD_MAX) & (ink < INK_FRAC_MAX) & \
           (means > SEP_BR_RANGE[0]) & (means < SEP_BR_RANGE[1])
    H = arr.shape[0]
    runs = []
    y = 0
    while y < H:
        if cand[y]:
            y0 = y
            while y < H and cand[y]:
                y += 1
            runs.append((y0, y - 1))
        else:
            y += 1
    return runs


def page_bands(runs, H):
    """Return list of (y_top, y_bot, kind) where kind is 'header' or 'content'.

    The first band (0 -> first separator) is tentatively marked 'header', but
    `extract_questions` reclassifies it to 'content' unless its text actually
    matches the "HL Paper N" title pattern. This prevents real question content
    (e.g. "a. Solve..." at the top of a continuation page) from being silently
    dropped as a false header.
    """
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


def chars_in_band(page, y_top_px, y_bot_px):
    """Return list of (x_center, y_center, char) for chars whose charbox overlaps the band.

    Band is given in rendered image pixels (y-down). Charboxes are in PDF points (y-up).
    We convert the band to PDF points before comparison.
    """
    tp = page.get_textpage()
    n = tp.count_chars()
    if n == 0:
        return []
    H_pt = page.get_size()[1]   # PDF page height in points (y-up)
    # Convert band px (y-down) -> pdf pts (y-up).
    # pixel_y = H_px - pdf_y * SCALE  =>  pdf_y = (H_px - pixel_y)/SCALE = H_pt - pixel_y/SCALE
    y_low_pt = H_pt - y_bot_px / SCALE    # corresponds to pixel bottom (low pdf y)
    y_high_pt = H_pt - y_top_px / SCALE   # corresponds to pixel top (high pdf y)
    # Read full text once and index by char position (avoids pypdfium2 recursion).
    text = tp.get_text_range()
    chars = []
    for i in range(n):
        cb = tp.get_charbox(i)
        if cb is None:
            continue
        x0, y0, x1, y1 = cb
        # char overlaps band if its charbox overlaps [y_low_pt, y_high_pt]
        if y0 <= y_high_pt and y1 >= y_low_pt:
            cx = (x0 + x1) / 2
            cy = (y0 + y1) / 2
            if i < len(text):
                chars.append((cx, cy, text[i]))
    return chars


def band_text(page, y_top, y_bot):
    """Get text from chars in band, sorted top-to-bottom then left-to-right.

    Note: PDF charbox y grows UPWARD, so the top of the band has the largest y.
    We sort by -y to read top-to-bottom.
    """
    chars = chars_in_band(page, y_top, y_bot)
    chars.sort(key=lambda c: (-round(c[1] / 4), c[0]))
    return "".join(c[2] for c in chars).strip()


def render_crop(page, y_top, y_bot, out_path):
    """Render full page (RGB) then crop to y-band; save as JPEG."""
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
    """True iff a page's first content band looks like a continuation of the
    previous question rather than a brand-new question.

    Continuation signals (the band is a fragment / mid-sentence / next sub-part):
      - starts with a lowercase letter (mid-sentence fragment)
      - starts with a sub-part label like "(b)", "(c)", "(ii)", "(iii)" (a
        subsequent sub-part of the previous question)
      - starts with a common continuation word ("hence", "therefore", "so",
        "thus", "also", "this" followed by a fragment)
    Everything else (especially capitalized question stems: Let, Consider, Find,
    Show, Given, The, A, An, Solve, Prove, ...) is treated as a NEW question.
    This makes the cross-page merge conservative and prevents gluing a
    half-question to the next whole question.
    """
    s = (text or "").strip()
    if not s:
        return False  # empty band -> new question (safe default)
    # Sub-part continuation: (b), (c), (ii), (iii), (iv) ...
    if re.match(r"^\s*\(([a-z]|ii|iii|iv|vi?|vii)\b", s, re.IGNORECASE):
        return True
    # Lowercase start = mid-sentence fragment
    first_alpha = next((c for c in s if c.isalpha()), None)
    if first_alpha and first_alpha.islower():
        return True
    # Common math-proof continuation words (only if clearly a fragment, not
    # a full sentence — check that the band is short and doesn't end with '.')
    first_word = re.split(r"[\s(]", s, 1)[0].lower().rstrip(",.;:")
    if first_word in {"hence", "therefore", "thus", "so", "also"} and len(s) < 200:
        return True
    return False


def extract_questions(doc):
    """Yield question dicts by separator-band detection with cross-page merge.

    Pass 1: per page, compute bands (y_top, y_bot, kind), whether the page has
            a real header (first separator within HEADER_MAX_PX of the top), and
            the text of the first content band (for continuation-signal check).
    Pass 2: assign content bands to questions. A page's first content band is a
            *continuation* of the previous page's spanning tail iff:
              (a) this page has no header, AND
              (b) the previous page's last content band reached the bottom, AND
              (c) the first content band passes _is_continuation_signal (looks
                  like a fragment/sub-part, not a new question stem).
            All other content bands start a new question.
    """
    pages = []
    for pi in range(len(doc)):
        img = render_page(doc[pi])
        runs = detect_separator_runs(img)
        bands = page_bands(runs, img.height)
        # Reclassify the first band: only treat as a real 'header' (to be
        # skipped) if its text actually matches the "HL Paper N" title pattern
        # and is short. Otherwise it's real question content that was just
        # positioned at the top of the page (e.g. a continuation or a new
        # question on a page without a top separator) — reclassify as
        # 'content' so it isn't silently dropped.
        if bands:
            (yt0, yb0, k0) = bands[0]
            first_text = band_text(doc[pi], yt0, yb0)
            is_real_title = (
                bool(first_text)
                and TITLE_LEAD.match(first_text) is not None
                and len(first_text) < 100
            )
            if not is_real_title:
                bands[0] = (yt0, yb0, 'content')
        has_header = bool(bands) and bands[0][2] == 'header'
        # text of the first *content* band (for continuation-signal check)
        first_content_text = ""
        for (yt, yb, kind) in bands:
            if kind == 'content':
                first_content_text = band_text(doc[pi], yt, yb)
                break
        pages.append({
            'pi': pi, 'bands': bands, 'has_header': has_header,
            'H': img.height, 'first_content_text': first_content_text,
        })

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
            is_continuation = (
                first_content_on_page
                and not p['has_header']
                and prev_last_reached_bottom
                and bool(questions)
                and _is_continuation_signal(p['first_content_text'])
            )
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


# Matches the OCR'd page-header title that leaks into q01 text, e.g.
# "HLPaer1p", "HL Paper 1", "HLPaer1 p". Anchored at start, case-insensitive,
# tolerant to letter run-together from stylized title rendering.
TITLE_LEAD = re.compile(
    r"^\s*hl\.?\s*p\w*r\s*\d+\s*p?\s*[\r\n]*",
    re.IGNORECASE,
)


def strip_title(text):
    """Remove a leading 'HL Paper N' header token from text (if present)."""
    if not text:
        return text
    return TITLE_LEAD.sub("", text).strip()


def is_cover(text):
    """True iff text is just a cover/title page (no real question content).

    Heuristic: raw text contains a digit (the page-number part of the title),
    and after stripping the title token, fewer than 3 alphanumerics remain.
    Catches cover-only PDFs (Topic 7/8/10 P1/P2) while preserving short real
    questions like "Find." / "Solve." (no digit, or > 3 alnum after strip).
    """
    raw = (text or "").strip()
    if not raw:
        return False
    if not re.search(r"\d", raw):
        return False
    rest = strip_title(raw)
    alnum = re.sub(r"[^a-z0-9]", "", rest.lower())
    return len(alnum) < 3


def find_prompt_in_text(prompt_norm, text_norm, start=0):
    """Find prompt_norm in text_norm starting from `start` (case-insensitive, whitespace-normalized)."""
    if not prompt_norm:
        return -1
    p = prompt_norm.lower()
    t = text_norm.lower()
    # try descending substring lengths so we prefer a long distinctive match
    # but to keep it simple: find first occurrence
    idx = t.find(p, start)
    return idx


def build_markscheme_index(ms_doc):
    """Build full text, char->page mapping, char->y mapping (per page), and a
    normalized (lowercase, whitespace-collapsed) full text with a norm->raw position
    map so prompt matching can use fast str.find().
    """
    page_texts = []
    page_char_starts = []
    cursor = 0
    for i in range(len(ms_doc)):
        tp = ms_doc[i].get_textpage()
        t = tp.get_text_range()
        page_texts.append(t)
        page_char_starts.append(cursor)
        cursor += len(t) + 1  # join with \n
    full = "\n".join(page_texts)

    def pos_to_page(p):
        pi = 0
        for i, st in enumerate(page_char_starts):
            if st > p:
                break
            pi = i
        return pi

    # For each page, build char_index_on_page -> y_center lazily (only for pages
    # we actually render as answer images; building all 124 pages upfront is too slow).
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

    # Build norm_full (lowercase, whitespace-collapsed) + norm_to_raw mapping.
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

    return {
        'full': full,
        'norm_full': norm_full,
        'norm_to_raw': norm_to_raw,
        'page_texts': page_texts,
        'page_char_starts': page_char_starts,
        'get_page_char_ys': get_page_char_ys,
        'pos_to_page': pos_to_page,
    }


def extract_answer_for_question(ms_index, prompt_text, prev_end=0):
    """Return (answer_text, answer_image_paths, end_pos) for this question.

    Strategy: locate the question's prompt in the markscheme text (first occurrence
    AFTER `prev_end`; each prompt is unique), then take the region up to the
    last '[N marks]' anchor within ~3000 chars as the answer (prompt + solution).
    Render the markscheme page(s) covering that text range as the answer_image.

    If prompt matching fails (too short, not found, or the matched region is
    before prev_end), fall back to a window starting at `prev_end` so the answer
    is at least in the right REGION of the markscheme (not always q01's).
    Returns (answer_text, paths, end_pos) where end_pos is the char index where
    this question's answer ended — pass it as prev_end to the next question.
    """
    full = ms_index['full']
    norm_full = ms_index['norm_full']
    norm_to_raw = ms_index['norm_to_raw']
    prompt_norm = normalize(prompt_text)
    end_pos = prev_end  # default; updated on successful match
    if len(prompt_norm) < 8:
        return _fallback_answer(ms_index, prev_end)
    # Build an alphanumeric-only needle: the markscheme strips math symbols from the
    # repeated prompt, so we match on the word prefix that survives in both.
    # The question_text often has a stripped variable def (e.g. "Let .") at the
    # start that the markscheme keeps ("Let z = 1−cos2θ..."). To get a needle
    # that actually matches the markscheme, prefer starting from the first
    # sub-part label ("a." / "(a)") if present — the sub-part text is what
    # reliably survives in both.
    alpha_only = re.sub(r"[^a-z0-9 ]+", " ", prompt_norm.lower())
    alpha_only = re.sub(r"\s+", " ", alpha_only).strip()

    def _find(needle, start):
        return norm_full.find(needle, start)

    npos = -1
    # Try needles in order of preference; the first that finds a match >= prev_end wins.
    # 1) Start at the first sub-part marker in alpha_only
    m_sub = re.search(r"\b(?:a\.|b\.|c\.|i\.|ii\.|iii\.|iv\.|v\.|\(a\)|\(b\)|\(c\)|\(i\)|\(ii\))", alpha_only)
    if m_sub:
        cand = alpha_only[m_sub.start(): m_sub.start() + 80].strip()
        if len(cand) >= 8:
            npos = _find(cand, prev_end)
    # 2) First 60 chars of the full alpha_only
    if npos < 0:
        cand = alpha_only[: min(60, len(alpha_only))]
        if len(cand) >= 8:
            npos = _find(cand, prev_end)
    # 3) First 40 chars (original short needle)
    if npos < 0:
        cand = alpha_only[: min(40, len(alpha_only))]
        if len(cand) >= 8:
            npos = _find(cand, prev_end)
    if npos < 0:
        return _fallback_answer(ms_index, prev_end)
    raw_start = norm_to_raw[npos]
    # bound at last [N marks] within a window after the prompt
    scan_end = min(len(full), raw_start + 3000)
    region = full[raw_start:scan_end]
    last_anchor = -1
    for m in re.finditer(r"\[\d+\s*marks?\]", region):
        last_anchor = m.end()
    if last_anchor < 0:
        end = raw_start + min(1500, len(region))
    else:
        end = raw_start + last_anchor
    answer_text = full[raw_start:end].strip()
    paths = _render_answer_image(ms_index, raw_start, end)
    end_pos = end
    return answer_text, paths, end_pos


def _locate_prompt_in_raw(full, needle_norm):
    """Find the position in raw `full` where a window normalizes to start with needle_norm."""
    if not needle_norm:
        return None
    # scan with a sliding window; for efficiency use a coarse step then refine
    L = len(needle_norm)
    step = 5
    i = 0
    while i < len(full):
        win = full[i:i + L * 2]
        win_norm = normalize(win).lower()
        if win_norm.startswith(needle_norm.lower()):
            return i
        # advance by 1 char, but skip newlines faster
        i += step if win_norm and win_norm[0] == needle_norm[0].lower() else 1
    return None


def _fallback_answer(ms_index, prev_idx):
    """Fallback when prompt-matching fails (usually badly OCR'd question stems).

    IMPORTANT: `end_pos` (3rd return value) MUST advance past the consumed
    region. The old version returned `prev_idx` unchanged as end_pos, so every
    consecutive unmatched question reused the SAME markscheme window -> hundreds
    of identical wrong answers/images. Now we consume exactly one markscheme
    "[N marks]" block starting at `prev_idx` and return its end as `end_pos`,
    so consecutive fallbacks progress through distinct, in-order blocks (which,
    since the markscheme is ordered, usually lands on the correct next answer).
    Returns (answer_text, image_paths, end_pos).
    """
    full = ms_index['full']
    start = prev_idx
    # Consume from `start` up to the end of the next "[N marks]" block.
    m = re.search(r"\[\d+\s*marks?\]", full[start:start + 6000])
    if m:
        end = start + m.end()
    else:
        end = min(len(full), start + 1500)
    return full[start:end].strip(), _render_answer_image(ms_index, start, end), end


def _render_answer_image(ms_index, start_char, end_char):
    """Render markscheme page(s) covering [start_char, end_char), cropped to y-range."""
    paths = []
    page_char_starts = ms_index['page_char_starts']
    page_texts = ms_index['page_texts']
    pos_to_page = ms_index['pos_to_page']
    get_page_char_ys = ms_index['get_page_char_ys']

    pi_start = pos_to_page(start_char)
    pi_end = pos_to_page(max(start_char, end_char - 1))

    # We need the ms_doc reference; close over via module global
    ms_doc = _MS_DOC

    for pi in range(pi_start, pi_end + 1):
        # local char range on this page
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
        # convert from pdf pts to rendered px: y_px = H - y_pt * SCALE (pypdfium y-up).
        img = ms_doc[pi].render(scale=SCALE).to_pil()
        H_px = img.height
        # Convert y_top/y_bot (PDF pts, y-up) to pixel coords
        py_top = H_px - int(y_bot * SCALE) - 6
        py_bot = H_px - int(y_top * SCALE) + 6
        py_top = max(0, py_top)
        py_bot = min(H_px, py_bot)
        crop = img.crop((0, py_top, img.width, py_bot)).convert("RGB")
        rel = _ANSWER_IMG_PATH(pi)            # e.g. "Topic_1/hl_paper1/a02_p1.jpg"
        out = os.path.join(FIG_ROOT, rel)     # ABSOLUTE: under public/figures
        os.makedirs(os.path.dirname(out), exist_ok=True)
        crop.save(out, "JPEG", quality=85)
        paths.append(rel)                     # manifest stores the relative path
    return paths


_MS_DOC = None
_ANSWER_IMG_PATH = None


# ---------------- main ----------------

def slug_topic(n):
    return f"Topic_{n}"


def paper_slug(paper):
    return paper.replace("-", "_").lower()   # HL-paper1 -> hl_paper1


def main():
    global _MS_DOC, _ANSWER_IMG_PATH

    records = []
    only_topic = int(os.environ.get('MT_TOPIC', '0')) or None
    for tn in range(1, 11):
        if only_topic and tn != only_topic:
            continue
        tdir = os.path.join(SRC_ROOT, f"Topic {tn}")
        if not os.path.isdir(tdir):
            continue
        for paper in PAPER_TYPES:
            qpdf = os.path.join(tdir, paper + ".pdf")
            mspdf = os.path.join(tdir, MS_PREFIX + paper + ".pdf")
            if not os.path.exists(qpdf) or not os.path.exists(mspdf):
                continue

            slug = paper_slug(paper)
            topic_dir = os.path.join(FIG_ROOT, slug_topic(tn), slug)
            os.makedirs(topic_dir, exist_ok=True)

            q_doc = pdfium.PdfDocument(qpdf)
            ms_doc = pdfium.PdfDocument(mspdf)
            _MS_DOC = ms_doc

            # ---- questions
            questions = extract_questions(q_doc)

            # ---- markscheme index (for prompt matching)
            ms_index = build_markscheme_index(ms_doc)
            prev_end = 0  # markscheme char position where the previous Q's answer ended

            # for each question, build record
            prev_prompt_idx = 0
            for qi, q in enumerate(questions, start=1):
                # Build question text FIRST so we can detect cover-only pages
                # before writing any image files.
                q_text_parts = []
                for (pi, yt, yb) in q['bands']:
                    t = band_text(q_doc[pi], yt, yb)
                    if t:
                        q_text_parts.append(t)
                question_text_raw = "\n\n".join(q_text_parts)
                if is_cover(question_text_raw) or len(question_text_raw.strip()) < 5:
                    # Drop cover-only pages AND empty/blank questions (artifact of
                    # a header being skipped on a page that has no real content).
                    print(f"  SKIP cover/blank: Topic {tn} {paper} q{qi:02d} text={question_text_raw!r}")
                    continue
                question_text = strip_title(question_text_raw)

                # question images: crop each band
                q_imgs = []
                for band_i, (pi, yt, yb) in enumerate(q['bands'], start=1):
                    outp = os.path.join(topic_dir, f"q{qi:02d}_p{band_i}.jpg")
                    render_crop(q_doc[pi], yt, yb, outp)
                    q_imgs.append(os.path.relpath(outp, FIG_ROOT).replace(os.sep, "/"))

                # ---- answer
                def _a_path(pi):
                    return os.path.relpath(os.path.join(topic_dir, f"a{qi:02d}_p{pi + 1}.jpg"), FIG_ROOT).replace(os.sep, "/")
                _ANSWER_IMG_PATH = _a_path
                answer_text, a_imgs, prev_end = extract_answer_for_question(ms_index, question_text, prev_end)
                answer_text = strip_title(answer_text)

                # source value: stable id for idempotent re-import
                src = f"Math_AA_HL_Topic{tn}_{paper}_q{qi:02d}"
                rec = {
                    'id': src.replace('Math_AA_HL_', 'MA_HL_topic_'),  # e.g. MA_HL_topic_1_HL_paper1_q01
                    'source': src,
                    'subject': SUBJECT,
                    'level': LEVEL,
                    'category': CATEGORY,
                    'topic': f'Topic {tn}',
                    'paper_type': paper,
                    'question_text': question_text,
                    'answer_text': answer_text,
                    'question_image': ",".join(q_imgs),
                    'answer_image': ",".join(a_imgs),
                    'marks': None,
                    'review_status': 'new',
                    'command_term': None,
                }
                records.append(rec)
                print(f"  Topic {tn} {paper} Q{qi:02d}: q_imgs={len(q_imgs)} a_imgs={len(a_imgs)} text_q={len(question_text)}c text_a={len(answer_text)}c")

    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(records)} records to {MANIFEST}")


if __name__ == '__main__':
    main()