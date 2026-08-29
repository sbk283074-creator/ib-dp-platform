#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared helpers for extracting concentrated exercise sets from IB textbooks /
workbooks into the question bank.

Key design decisions (per user request):
  * ONLY extract concentrated practice sets: end-of-chapter exercises,
    mixed-review / mixed-practice sections. Skip worked examples, explanations,
    theory pages.
  * Precisely CROP each question block (not the whole page). We locate the
    vertical band of each question's leading number via pdfplumber char layout,
    then render just that band with pypdfium2.
  * Pair with answers from a companion answer file when one exists; otherwise
    leave answer blank and let the importer mark it AI-generated.

Output per book: a dict { book: {...}, questions: [ {id, subject, level, topic,
  subtopic, paper_type, command_term, marks, difficulty, question, answer,
  explanation, source, tags, knowledge_point_ids, book_id, book_section,
  book_page, in_book_order, source_type, question_image, answer_image } ] }
"""
import os, re, json, sqlite3
import pdfplumber
import pypdfium2 as pdfium
from PIL import Image

# where crops are written (served at /figures/...)
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FIG_DIR = os.path.join(BACKEND_ROOT, 'public', 'figures')
os.makedirs(FIG_DIR, exist_ok=True)

DPI = 200  # render DPI for crops (balanced quality / size)

# ---- exercise-section detection -------------------------------------------
# A page is a "practice page" if it contains one of these headings/keywords
# AND is not primarily theory. We use a positive list so we never grab examples.
EXERCISE_HEADERS = [
    r'end[\s\-]?of[\s\-]?topic\s+questions?',
    r'end[\s\-]?of[\s\-]?chapter\s+exercises?',
    r'mixed\s+practice',
    r'mixed\s+review',
    r'review\s+questions?',
    r'chapter\s+review',
    r'practice\s+questions?',
    r'exercise\s+\d+',
    r'exercises?',
    r'questions?',
    r'problems?',
    r'test\s+yourself',
    r'self[\s\-]?test',
]
# pages whose heading contains these are EXCLUDED (theory / example)
EXCLUDE_HEADERS = [
    r'worked\s+example',
    r'example\s+\d+',
    r'let\s+us\s+(explore|investigate)',
    r'solution\s+to',
    r'key\s+idea',
    r'in\s+this\s+section',
    r'table\s+of\s+contents',
    r'\bcontents\b',
    r'index\b',
    r'how\s+to\s+use\s+this\s+book',
    r'introduction\b',
    r'foreword\b',
    r'acknowledgements?',
    # back-of-book ANSWERS section (Haese): running header '<page> ANSWERS'.
    # Line-anchored (EXCLUDE_RE compiled with re.M) so 'Give your answers
    # to 2 d.p.' never matches.
    r'^\s*\d{0,4}\s*answers\b',
]

EXERCISE_RE = re.compile('|'.join(EXERCISE_HEADERS), re.I)
EXCLUDE_RE = re.compile('|'.join(EXCLUDE_HEADERS), re.I | re.M)

# A line beginning with a single letter sub-part (a), (b), a. — used to detect
# EXERCISE CONTINUATION pages: a page that carries only sub-parts (no leading
# digit question number) because the parent question started on the prior page.
LET_RE = re.compile(r'^\(?[a-eA-E]\)?[.)]?\s+\S')


# Running-header pattern: a number followed by 1-3 short Title-case
# words (e.g. '1 Counting principles', '12 Mixed Practice'). Real question
# stems have lowercase words and are longer, so this stays specific.
HEADER_TITLE_RE = re.compile(r'^\d{1,3}[.)]?\s+(?:[A-Z][A-Za-z]*\s*){1,3}$')

# Math-font glyph confusion in Haese books: when the digit's stem is missing,
# pypdfium returns a different glyph. The most common single-character case
# is `4` extracted as `&` (the digit's right vertical stem doubles as the
# ampersand's left lobe in some Haese math fonts). `?` and missing digits
# crop to `?` are also seen rarely. Maps glyph -> digit the OCR misread.
HAESE_DIGIT_GLYPHS = {'&': '4', '?': '7'}

# ----------------------------------------------------------------------------
# Per-book segmentation configuration
# ----------------------------------------------------------------------------
# Every book can override any of these via its `seg` dict. The defaults below
# were chosen to make NUMBER question numbers the ONLY thing that starts a
# question (letter sub-parts are nested, never split), and to reject in-body
# spurious numbers ("2 The ...", equation indices) via left-margin discipline
# + an ascending-monotonic sequence check.
DEFAULT_SEG = dict(
    # A number is a question start only if its left edge sits within this
    # fraction of the (column) width measured from the column's left edge.
    # Real question numbers are set at the left margin; in-body numbers are
    # indented and therefore rejected. Per-book tunable.
    qnum_margin=0.18,
    # Require the number to be followed by a word starting with A-Z or a digit
    # (rejects formula fragments like "1 x", "2 +").
    strict_qnum=True,
    # Enforce that detected question numbers form an ascending sequence with
    # step <= max_step. Duplicates / descending / huge jumps are dropped
    # (these are sub-numbers or noise inside a question).
    monotonic=True,
    max_step=2,
    # Drop bands shorter than this (PDF pts) — too small to be a real question
    # (fragment / overlap-render noise).
    min_band_pt=20,
    # Vertical padding around the marker when splitting into bands (PDF pts).
    top_pad=6.0,
    bottom_pad=2.0,
    # Extra crop padding so the rendered question is never clipped
    # (PDF pts for text pipeline; converted to px in the scanned pipeline).
    crop_top=4.0,
    crop_bottom=4.0,
    # Minimum number of question markers for a page to count as an exercise
    # page (guards against intro / theory pages with a stray numbered list).
    min_markers=3,
    # Letter sub-question markers (a), (b) ... are NEVER question starts.
    allow_letter_starts=False,
    # (scanned pipeline) fraction of page width within which a number must
    # sit to be a question anchor.
    left_frac=0.30,
    # (scanned pipeline) minimum band height in pixels at the render DPI
    # (~2 text lines). Bands shorter than this are dropped as noise.
    min_band_px=None,
)


def _seg_cfg(cfg):
    """Merge user-supplied seg overrides onto DEFAULT_SEG."""
    d = dict(DEFAULT_SEG)
    if cfg:
        d.update({k: v for k, v in cfg.items() if v is not None})
    return d


def _line_start_number(text, strict):
    """If `text` begins a line with a question NUMBER (1-3 digits, optional
    '.' or ')'), return the integer; else None. `strict` requires a following
    word that starts with A-Z or a digit so formula fragments are rejected.

    Haese-specific relaxations (enabled when strict=True):
      * `5 a Draw the graph ...` — the question number is immediately followed
        by a single lowercase sub-part letter, then a real word. We accept
        `digit + lowercase-letter + spaces + letter` so the post-digit body
        shape `a Draw ...` doesn't reject Q5. A bare `1 x = 2` formula
        fragment still fails (its 2nd char is `=`, not a letter) so the
        tightening is preserved.
      * `12` alone on its own line — pypdfium sometimes splits `12 a Graph`
        into two y-buckets of `'12'` and `'a Graph'`. A bare-digit line at
        left margin is treated as a question start (the body got pushed to
        a sibling line). The left-margin discipline still discards in-body
        bare numbers (those sit far from the column edge).
    """
    # 1. Normal case: digit(s) + optional .)/ + whitespace + body.
    m = re.match(r'^(\d{1,3})[.)]?\s+', text)
    if m:
        num = int(m.group(1))
        after = text[m.end():]
        if not after.strip():
            return None
        # Axis-tick / number-sequence lines ("0 1 2 3 …", "100 120 brake pads")
        # are not questions — reject when the body is itself digits/spaces.
        if re.match(r'^[\d\s./]', after):
            return None
        if strict:
            # Standard: uppercase letter or digit after.
            if re.match(r'[A-Z\d]', after):
                return num
            # Relaxed: lowercase sub-part letter + spaces + word.
            # 'a Draw ...' / 'b Find ...' / 'c State ...' pass.
            # '1 x = 2' / '2 + 3' do NOT (need letter after spaces).
            if re.match(r'[a-z]\s+[A-Za-z]', after):
                return num
            return None
        return num
    # 2. Bare-digit line (no body text). Common in Haese review sets where
    #    pypdfium splits `12 a Graph` into `'12'` and `'a Graph'`. We only
    #    accept this when the line is JUST digits (no leading whitespace,
    #    no trailing characters) so we don't swallow subscripts or
    #    running-header numbers.
    m = re.match(r'^(\d{1,3})$', text.strip())
    if m:
        return int(m.group(1))
    return None


def _line_start_number_alt_glyph(text):
    """Return an int if the line begins with a math-font-confused digit
    glyph documented in HAESE_DIGIT_GLYPHS (e.g. '&' for '4'), followed
    by a body word — else None. Used as a recovery pass after the
    standard detector misses Haese review-set question numbers whose
    leading digit got OCR-misread.
    """
    for glyph, digit in HAESE_DIGIT_GLYPHS.items():
        # body must START with a letter so '&' as decorative separator /
        # '?' inside a sentence is not mis-classified.
        rx = re.compile(r'^' + re.escape(glyph) + r'\s+[A-Za-z]')
        if rx.match(text):
            return int(digit)
    return None


def _bare_dot(text):
    """Some textbooks render the question number as a bare '.' (the digits
    are missing from the text layer). Treat a line starting with '. ' + a
    capitalised word as a question boundary (number unknown)."""
    return bool(re.match(r'^\s*\.\s+[A-Z]', text)) and len(text) > 30


def page_text(pdfplumber_page):
    return pdfplumber_page.extract_text() or ''


def is_exercise_page(plumb_page, first_text_on_page=None):
    """Decide if a page belongs to a concentrated practice set."""
    txt = page_text(plumb_page)
    # need at least a couple of enumerated question numbers
    nums = re.findall(r'(?m)^\s*\(?(\d{1,3})[.)]\s', txt)
    # exclude theory/example pages
    if EXCLUDE_RE.search(txt.split('\n')[0]) or EXCLUDE_RE.search(txt[:400]):
        return False, None
    m = EXERCISE_RE.search(txt)
    if m and len(nums) >= 3:
        return True, (m.group(0).strip())
    return False, None


def question_bands(plumb_page):
    """
    Return a list of (qnum, y0, y1) vertical bands, one per question on the page.
    We anchor on the leading number of each question: '1.', '2)', '(3)', 'a)', etc.
    """
    words = plumb_page.extract_words()
    if not words:
        return []
    H = float(plumb_page.height)
    # candidate question-start tokens: stand-alone numbers/letters at line start
    starts = []
    for w in words:
        t = (w.get('text') or '').strip()
        top = float(w['top'])
        if re.fullmatch(r'\d{1,3}[.)]', t) or re.fullmatch(r'\(\d{1,3}\)', t):
            starts.append((top, t))
        elif re.fullmatch(r'[a-e][.)]', t) or re.fullmatch(r'\([a-e]\)', t):
            # sub-part; only treat as start if near left margin (new question chain)
            if float(w['x0']) < 0.15 * float(plumb_page.width):
                starts.append((top, t))
    if not starts:
        return []
    starts.sort(key=lambda s: s[0])
    bands = []
    for i, (top, t) in enumerate(starts):
        nxt = starts[i + 1][0] if i + 1 < len(starts) else H
        bands.append((t, max(0.0, top - 6), min(H, nxt - 2)))
    return bands


def render_crop(pdfium_page, y0, y1, out_path, dpi=DPI):
    """Render the vertical band [y0,y1] (in PDF points) of a pypdfium page.

    Renders the WHOLE page first, then crops with PIL — robust against
    pypdfium's crop-coordinate quirks.
    """
    scale = dpi / 72.0
    W, H = pdfium_page.get_size()
    bmp = pdfium_page.render(scale=scale)
    img = bmp.to_pil()
    ph = img.height
    py0 = max(0, min(ph - 1, int(round(y0 * scale))))
    py1 = max(py0 + 4, min(ph - 1, int(round(y1 * scale))))
    if py1 - py0 < 4:
        return False
    crop = img.crop((0, py0, img.width, py1))
    crop.save(out_path, 'JPEG', quality=88)
    return True


def render_page_crops(pdfium_page, bands, out_paths, dpi=DPI):
    """Render the page ONCE, then crop each vertical band (y0,y1 in PDF points)
    to its own JPEG. Returns number of crops saved. Memory-friendly when a page
    holds many questions."""
    if not bands:
        return 0
    scale = dpi / 72.0
    W, H = pdfium_page.get_size()
    bmp = pdfium_page.render(scale=scale)
    img = bmp.to_pil()
    ph = img.height
    saved = 0
    for (y0, y1), out_path in zip(bands, out_paths):
        py0 = max(0, min(ph - 1, int(round(y0 * scale))))
        py1 = max(py0 + 4, min(ph - 1, int(round(y1 * scale))))
        if py1 - py0 < 4:
            continue
        crop = img.crop((0, py0, img.width, py1))
        crop.save(out_path, 'JPEG', quality=88)
        saved += 1
    return saved


def find_answer_for(answer_text, qnum):
    """Within an answer file's text, pull the answer block for question qnum."""
    # look for '\nqnum.' or '(qnum)' or 'qnum ' near start of a line
    pat = re.compile(r'(?m)(?:^|\n)\s*(?:\(?' + re.escape(str(qnum)) + r'\)?[.)])\s*(.*?)(?=\n\s*(?:\(?\d{1,3}\)?[.)])\s|\Z)', re.S)
    m = pat.search(answer_text)
    if m:
        return m.group(1).strip()
    return None


def load_pdf(path):
    return pdfplumber.open(path), pdfium.PdfDocument(path)


def page_iter(path):
    """Yield (plumb_page, pdfium_page) tuples for one book at a time, closing
    both documents when finished (saves memory on big books)."""
    pl = pdfplumber.open(path)
    pdf = pdfium.PdfDocument(path)
    try:
        n = len(pl.pages)
        for i in range(n):
            yield pl.pages[i], pdf[i]
    finally:
        pl.close()
        pdf.close()


def page_iter_pdfium(path):
    """Memory-friendly page iterator using pypdfium only.

    pdfplumber caches page objects across the whole doc which blows memory on
    700+ page textbooks. pypdfium is much lighter. We use pypdfium's text
    extraction to find exercise headers / question bands instead of pdfplumber.
    """
    pdf = pdfium.PdfDocument(path)
    try:
        for i in range(len(pdf)):
            yield pdf[i]
    finally:
        pdf.close()


# ----- pypdfium-only helpers (low memory) ------------------------------------
def pdfium_page_text(page):
    tp = page.get_textpage()
    t = tp.get_text_range() or ''
    tp.close()
    return t


def pdfium_page_search(page, pattern, ignore_case=True):
    """Search a regex on the page; return list of (x0,y0,x1,y1) bboxes in PDF points."""
    tp = page.get_textpage()
    out = []
    try:
        searcher = tp.search(pattern)
        while True:
            box = searcher.get_next()
            if box is None or len(box) == 0:
                break
            # pdfium returns (char_count, x0, y0, x1, y1) per get_next()
            if len(box) == 5:
                _, x0, y0, x1, y1 = box
            else:
                x0, y0, x1, y1 = box[:4]
            out.append((float(x0), float(y0), float(x1), float(y1)))
    except Exception:
        pass
    tp.close()
    return out


def pdfium_lines(page, tol=8.0):
    """Rebuild page text line-by-line from glyph positions (robust to PDFs
    whose text_range emits one character per line, e.g. some Oxford ebooks,
    and to overlapping multi-layer renders common in maths textbooks).
    Returns list of (y_top_screen, line_text) top→bottom."""
    H = float(page.get_height())
    tp = page.get_textpage()
    n_chars = tp.count_chars()
    chars = []
    for i in range(n_chars):
        try:
            box = tp.get_charbox(i)
            x0, y0, x1, y1 = float(box[0]), float(box[1]), float(box[2]), float(box[3])
            top_scr = H - y1
            bot_scr = H - y0
            chars.append((x0, top_scr, x1, bot_scr))
        except Exception:
            continue
    tp.close()
    if not chars:
        return []
    # O(n) fine bucketing (6px), then merge adjacent buckets ONLY when they are
    # the same visual line: either very close in y (<4px) or their tokens
    # heavily overlap (multi-layer renders repeat the same text). Adjacent
    # DISTINCT lines (small line-height PDFs like the CS textbook) stay split.
    from collections import defaultdict
    buckets = defaultdict(list)
    for c in chars:
        buckets[round(c[1] / 6) * 6].append(c)
    keys = sorted(buckets.keys())

    def bucket_text(k):
        rs = buckets[k]
        x0 = min(r[0] for r in rs); x1 = max(r[2] for r in rs)
        top = min(r[1] for r in rs); bot = max(r[3] for r in rs)
        y0_pdf = H - bot; y1_pdf = H - top
        tp2 = page.get_textpage()
        t = (tp2.get_text_bounded(x0 - 1, y0_pdf - 1, x1 + 1, y1_pdf + 1) or '').strip()
        tp2.close()
        return t

    def overlap(a, b):
        if not a or not b:
            return False
        ta = set(a.split()); tb = set(b.split())
        if not ta or not tb:
            return False
        inter = len(ta & tb)
        return inter / min(len(ta), len(tb)) > 0.55

    merged = []
    for k in keys:
        if not merged:
            merged.append([k, buckets[k]])
            continue
        pk = merged[-1][0]
        if (k - pk) <= 4:
            merged[-1][1].extend(buckets[k])
        else:
            prev_t = bucket_text(pk)
            cur_t = bucket_text(k)
            if overlap(prev_t, cur_t):
                merged[-1][1].extend(buckets[k])
            else:
                merged.append([k, buckets[k]])
    out = []
    for k, rs in merged:
        x0 = min(r[0] for r in rs); x1 = max(r[2] for r in rs)
        top = min(r[1] for r in rs); bot = max(r[3] for r in rs)
        if x1 - x0 < 2:
            continue
        y0_pdf = H - bot
        y1_pdf = H - top
        tp2 = page.get_textpage()
        t = (tp2.get_text_bounded(x0 - 1, y0_pdf - 1, x1 + 1, y1_pdf + 1) or '').strip()
        tp2.close()
        toks = t.split()
        seen = []
        for tk in toks:
            if seen and seen[-1] == tk:
                continue
            seen.append(tk)
        t2 = ' '.join(seen)
        if len(t2) > 0:
            out.append((top, t2, x0))
    out.sort(key=lambda r: r[0])
    return out


INTRO_RE = re.compile(
    r'(?im)^\s*(introduction|about\s+this\s+book|how\s+to\s+use\s+this|'
    r'preface|acknowledgements?|contents|index|welcome\s+to)\b')


def is_exercise_page_pdfium(page, patterns=None, min_markers=1, x0frac=0.20,
                            exclude_re=None):
    """Decide if a page belongs to a practice/exercise set, using pypdfium only.

    A page is treated as an exercise page when it is NOT front-matter / intro /
    a table of contents / a worked-example page, AND it shows ONE of:
      * an exercise heading near the top (EXERCISE_HEADERS / custom `patterns`),
      * >= `min_markers` left-margin DIGIT question numbers (a real numbered
        exercise, even with no visible heading),
      * >= 2 left-margin letter sub-parts (a CONTINUATION page whose parent
        question started on the previous page — its body spills over).

    Returns (ok, header_text, kind) where kind is one of
    None / 'head' / 'numbered' / 'continuation'. The caller uses 'continuation'
    to stitch the page onto the previous question instead of starting a new one
    (so a big question is never split into several sub-questions).
    """
    if patterns is None:
        patterns = EXERCISE_HEADERS
    lines = pdfium_lines(page)
    txt = '\n'.join(t for _, t, _ in lines)
    # explicit front-matter / intro rejection
    if EXCLUDE_RE.search(txt[:400]):
        return False, None, None
    if INTRO_RE.search(txt[:600]):
        return False, None, None
    # Reject table-of-contents pages (dense dot-leader rows). These are NOT
    # exercise pages even though they contain words like "Chapter review".
    if has_toc_dots(page):
        return False, None, None
    # Reject index / glossary pages by their leading banner line.
    if re.match(r'^\s*(index|glossary)\b', txt.strip(), re.I):
        return False, None, None
    # Per-book hard exclude (internal-assessment / worked-example / theory
    # "Topic X.Y" pages, etc.) checked over the WHOLE page. This overrides the
    # caller's continuation gate so a non-question page that happens to follow a
    # real exercise page is still rejected.
    if exclude_re and re.search(exclude_re, txt):
        return False, None, None
    H = float(page.get_height()); W = float(page.get_width())
    margin = x0frac * W
    digit = 0
    letter = 0
    for top, text, x0 in lines:
        if (0 <= top < 0.05 * H or top > 0.94 * H) and len(text) < 15:
            continue
        num = _line_start_number(text, True)
        if num is not None and x0 <= margin:
            digit += 1
        elif LET_RE.match(text) and x0 <= margin:
            letter += 1
    # The exercise heading must be a PAGE HEADING (near the top), not a word
    # buried in body text. This stops theory/intro pages that merely mention
    # "questions" from being treated as exercise pages.
    head_txt = '\n'.join(t for _, t, _ in lines[:8])
    m = re.compile('|'.join(patterns), re.I).search(head_txt)
    if m:
        return True, m.group(0).strip(), 'head'
    if digit >= min_markers:
        return True, 'numbered', 'numbered'
    if letter >= 2:
        return True, 'continuation', 'continuation'
    return False, None, None


def has_toc_dots(page):
    """True if the page looks like a table of contents (many dot-leader rows)."""
    txt = '\n'.join(t for _, t, _ in pdfium_lines(page))
    dot_rows = sum(1 for ln in txt.split('\n') if re.search(r'\.{6,}', ln))
    return dot_rows >= 6


def pdfium_lines_in(page, x_min=0.0, x_max=None):
    """Return full pdfium_lines filtered to lines whose START x0 lies in
    [x_min, x_max]. The underlying pdfium_lines already merges multi-layer
    offset duplicates by token overlap, so the kept line's x0 is the real
    (un-offset) column start — safe to filter by x0."""
    W = float(page.get_width())
    if x_max is None:
        x_max = W
    return [(t, tx, x0) for (t, tx, x0) in pdfium_lines(page)
            if x_min - 2 <= x0 <= x_max + 2]


def column_lines(page, cx0, cx1, max_x_gap=22.0, line_y_tol=5.0,
                 dedup_against=None, exclude_rects=None):
    """Build (top, text, x0) lines from chars whose x-centre lies in
    [cx0, cx1]. Uses the same bucket-then-overlap strategy as
    `pdfium_lines` so that two columns at the same y are NEVER merged
    into one line. dedup_against: optional list of (top, text) from the
    OTHER column. Lines in this column whose text heavily overlaps a
    same-y line from the other column are discarded — these are
    multi-layer offset duplicates of the other column."""
    H = float(page.get_height()); W = float(page.get_width())
    cx0 = max(0.0, cx0) - 1.0
    cx1 = min(W, cx1) + 1.0
    tp = page.get_textpage(); n = tp.count_chars()
    chars = []
    for i in range(n):
        try:
            b = tp.get_charbox(i)
            x0, y0, x1, y1 = float(b[0]), float(b[1]), float(b[2]), float(b[3])
        except Exception:
            continue
        cx = (x0 + x1) / 2.0
        if cx < cx0 or cx > cx1:
            continue
        top = H - y1; bot = H - y0
        chars.append((x0, top, x1, bot))
    tp.close()
    if not chars:
        return []
    from collections import defaultdict
    # 6pt y-bucket matches pdfium_lines (proven to handle cap-to-xheight
    # variation within a single visual line). Merge adjacent buckets only
    # when they're very close in y (<4pt) or text heavily overlaps.
    buckets = defaultdict(list)
    for c in chars:
        buckets[round(c[1] / 6) * 6].append(c)
    keys = sorted(buckets.keys())

    def bucket_text(rs):
        if not rs: return ''
        x0 = min(r[0] for r in rs); x1 = max(r[2] for r in rs)
        top = min(r[1] for r in rs); bot = max(r[3] for r in rs)
        y0_pdf = H - bot; y1_pdf = H - top
        tp2 = page.get_textpage()
        t = (tp2.get_text_bounded(x0 - 1, y0_pdf - 1, x1 + 1, y1_pdf + 1) or '').strip()
        tp2.close()
        return t, (x0, x1, top, bot)

    def overlap(a, b):
        if not a or not b: return False
        ta = set(a.split()); tb = set(b.split())
        if not ta or not tb: return False
        inter = len(ta & tb)
        return inter / min(len(ta), len(tb)) > 0.55

    merged = []
    for k in keys:
        if not merged:
            merged.append([k, buckets[k]]); continue
        pk = merged[-1][0]
        if (k - pk) <= 4:
            merged[-1][1].extend(buckets[k])
        else:
            prev_t, _ = bucket_text(merged[-1][1])
            cur_t, _ = bucket_text(buckets[k])
            if prev_t and cur_t and overlap(prev_t, cur_t):
                merged[-1][1].extend(buckets[k])
            else:
                merged.append([k, buckets[k]])
    out = []
    for k, rs in merged:
        t, (x0, x1, top, bot) = bucket_text(rs)
        if not t or (x1 - x0) < 2:
            continue
        # Skip lines that sit *inside* a figure (raster or vector). A side
        # figure's axis labels / caption text would otherwise be read as a
        # question band when this column is the "right column" of a page that
        # is really single-column-with-figure. Excluding them here keeps the
        # phantom axis labels (e.g. the HR-diagram "100") from becoming bands.
        if exclude_rects:
            inside = any(exx0 - 6 <= x0 <= exx1 + 6 and ey0 - 6 <= top <= ey1 + 6
                         for (exx0, ey0, exx1, ey1) in exclude_rects)
            if inside:
                continue
        # within-column dedup of adjacent same-y duplicates (multi-layer
        # renders that happen to fall in the same column): merge them,
        # keeping the longer text.
        if out and abs(top - out[-1][0]) <= 6:
            ta = set(t.split()); pa = set(out[-1][1].split())
            if ta and pa:
                jac = len(ta & pa) / len(ta | pa)
                if jac > 0.88:
                    if len(t) > len(out[-1][1]):
                        out[-1] = (float(top), t, float(x0))
                    continue
        out.append((float(top), t, float(x0)))
    # Post-process: a "2" or "3." sitting in its own bucket right before the
    # question text (e.g., Oxford "2 If f(1) = 2; g(3) = 1; h(2) = 3...") gets
    # detached because the digit's glyph bbox is a few pt higher/lower than
    # the body text. Merge a short numeric-only line into the next line if
    # the y-gap is small (<=8pt) and the next line starts with non-digit text.
    if out:
        merged_pp = []
        i = 0
        while i < len(out):
            top, t, x0 = out[i]
            if (i + 1 < len(out)
                    and re.match(r'^\d{1,3}[.)]?$', t.strip())
                    and (out[i + 1][0] - top) <= 8
                    and not re.match(r'^\d', out[i + 1][1])):
                ntop, ntext, nx0 = out[i + 1]
                # Prepend the question number token to the prompt
                new_text = f"{t.strip()} {ntext}"
                merged_pp.append((float(ntop), new_text, float(nx0)))
                i += 2
            else:
                merged_pp.append((top, t, x0))
                i += 1
        out = merged_pp
    # cross-column phantom dedup (offset duplicate of the other column)
    if dedup_against:
        def tok(s): return set(s.split())
        keep = []
        for (top, t, x0) in out:
            ta = tok(t)
            is_phantom = False
            if ta:
                for (otop, otxt) in dedup_against:
                    if abs(top - otop) > 12:
                        continue
                    tb = tok(otxt)
                    if not tb:
                        continue
                    jac = len(ta & tb) / len(ta | tb)
                    if jac > 0.88:
                        is_phantom = True; break
            if not is_phantom:
                keep.append((top, t, x0))
        out = keep
    out.sort(key=lambda r: r[0])
    return out


def detect_columns(page):
    """Detect single vs two-column layout by rendering the page and finding
    the widest truly-blank vertical strip in the middle of the page, flanked
    by text on both sides. This is the only reliable signal for two-col
    textbook pages whose right column is sparse (e.g., Oxford "Chapter
    review" with only ~7 questions on the right). The text-layer histogram
    fails for sparse right columns because the inter-column gutter is NOT
    the global density minimum."""
    gutter = find_gutter_by_whitespace(page)
    if gutter is None:
        return ('single', None)
    return ('two-col', float(gutter))


def find_gutter_by_whitespace(page, dpi=50, white_thr=240,
                              search_lo=0.40, search_hi=0.60,
                              flank_offset=0.05, flank_half=0.02,
                              blank_thr=0.80, min_quartile=0.62,
                              flank_blank_max=0.90, exclude_rects=None,
                              asymmetry_ratio=0.25):
    """Find the inter-column gutter x (PDF pts).

    Strategy: use the text-layer x-centroid histogram (every char's x
    centre, binned at 3pt). A two-column page has a WIDE valley of
    near-zero text density between two clusters; a single-column page
    has no such valley in the middle. This works even when the rendered
    blank strip approach is fooled by:
      - boxes/figures around the gutter
      - intra-column gaps on single-col pages that have a long blank
        y-stretch in the middle (the rendered approach saw such gaps
        as "blank" too, because the page has a lot of whitespace).
    The text-histogram approach is robust because the gutter zone on a
    true two-col page has essentially ZERO characters, while an intra-
    column gap on a single-col page has characters at nearby y (just
    spread out across x).

    `exclude_rects`: optional list of (x0,y0,x1,y1) [screen coords] to skip
    when building the histogram (e.g. raster/vector figure bboxes). A
    single-column page whose ONLY right-side text is a figure's axis labels
    would otherwise look like a right column; excluding the figure lets the
    detector see there is no real right column.
    `asymmetry_ratio`: a candidate gutter is rejected unless BOTH flanks
    carry substantial text — the right flank (excluding figures) must hold at
    least this fraction of the left flank's character count. A single-column
    page with a right-side figure fails this (its right side is figure axis
    labels, not prose), so it is correctly reported as single-column.
    """
    H = float(page.get_height()); W = float(page.get_width())
    tp = page.get_textpage()
    n = tp.count_chars()
    if n == 0:
        tp.close()
        return None
    bin_w = 3.0
    nbins = int(W / bin_w) + 1
    hist = [0] * nbins
    ex = exclude_rects or []
    xs = []; ys = []  # char x/y (screen coords) for the column-mass test
    for i in range(n):
        try:
            b = tp.get_charbox(i)
            x0, y0, x1, y1 = float(b[0]), float(b[1]), float(b[2]), float(b[3])
        except Exception:
            continue
        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0
        # Skip characters inside an excluded figure rect (screen coords).
        if ex:
            inside = any(exx0 - 6 <= cx <= exx1 + 6 and ey0 - 6 <= cy <= ey1 + 6
                         for (exx0, ey0, exx1, ey1) in ex)
            if inside:
                continue
        bi = int(cx / bin_w)
        if 0 <= bi < nbins:
            hist[bi] += 1
        # Record y for the column-mass (vertical occupancy) test below.
        ys.append(cy); xs.append(cx)
    tp.close()
    # Smooth 2 bins
    smooth = [0.0] * nbins
    for i in range(nbins):
        a = max(0, i - 1); b = min(nbins, i + 2)
        smooth[i] = sum(hist[a:b]) / (b - a)
    lo = int(search_lo * W / bin_w)
    hi = int(search_hi * W / bin_w)
    # Find the WIDEST contiguous run of bins with count < 3.0 (essentially
    # empty). A real gutter spans at least 5 bins (15pt). Reject runs where
    # the text density on the two sides of the gutter is very asymmetric
    # (one side has many more chars than the other) — that's the signature
    # of a single-col page with side-by-side sub-parts, not a real two-col
    # layout.
    FLANK = 16  # 16 bins = 48pt on each side of the candidate gutter
    best_len = 0; best_mid = None
    cur = 0; cs = lo

    def col_mass_ok(mid_b, min_occ=0.55, min_chars=40, left_lo=0.0):
        """A genuine two-column gutter sits between TWO continuous text
        columns: on both sides, text must occupy most of the page height
        (not just a few axis labels from a side figure). Returns True only
        if the left and right regions each carry substantial, tall text."""
        gx = mid_b * bin_w
        ls_x = max(0.0, gx - FLANK * bin_w)
        rs_x = min(W, gx + FLANK * bin_w)
        ly = [y for (x, y) in zip(xs, ys) if ls_x <= x <= gx]
        ry = [y for (x, y) in zip(xs, ys) if gx <= x <= rs_x]
        if len(ly) < min_chars or len(ry) < min_chars:
            return False
        # Fraction of vertical bins (10% of page height) holding any text.
        nb = max(1, int(H / (0.10 * H)))
        lset = set(int(y / (H / nb)) for y in ly)
        rset = set(int(y / (H / nb)) for y in ry)
        return (len(lset) / nb) >= min_occ and (len(rset) / nb) >= min_occ

    def gutter_empty_ok(mid_b, cs, cur):
        """A genuine gutter sits in a near-EMPTY vertical strip: the bin at the
        gutter position must carry almost no text. We locate the empty sub-run
        inside [cs, cs+cur] and require the centre of that empty strip to be
        near-empty (smooth < 1.0). A single-column page whose 'valley' is just a
        density dip BETWEEN two text spans (not a real gap) fails this because
        the mid-point lands inside the left text cluster, not in an empty band."""
        # find the widest empty sub-run within [cs, cs+cur]
        best_a = cs; best_run = 0; run = 0; run_a = cs
        for x in range(cs, cs + cur):
            if smooth[x] < 1.0:
                if run == 0:
                    run_a = x
                run += 1
                if run > best_run:
                    best_run = run; best_a = run_a
            else:
                run = 0
        if best_run < 3:
            return False
        empty_mid = best_a + best_run / 2.0
        return smooth[int(empty_mid)] < 1.0

    for x in range(lo, hi + 1):
        if smooth[x] < 3.0:
            if cur == 0:
                cs = x
            cur += 1
        else:
            if cur >= 5:
                mid_b = cs + cur / 2.0
                ls = max(0, cs - FLANK)
                le = cs
                rs = cs + cur
                re = min(nbins, cs + cur + FLANK)
                left_chars = sum(hist[ls:le])
                right_chars = sum(hist[rs:re])
                # Both sides must have substantial text, and the right side
                # must hold at least asymmetry_ratio of the left side's chars.
                # A single-column page with a side figure fails the right-side
                # test (its right side is figure axis labels, not prose), so it
                # is correctly reported as single-column.
                if left_chars < 40 or right_chars < 40:
                    pass  # one side has too little text — not a real gutter
                elif min(left_chars, right_chars) < asymmetry_ratio * max(left_chars, right_chars):
                    pass  # sides are very asymmetric — not a real gutter
                elif not col_mass_ok(mid_b):
                    pass  # right side is not a continuous text column
                elif not gutter_empty_ok(mid_b, cs, cur):
                    pass  # gutter mid-point is not a genuinely empty strip
                elif cur > best_len:
                    best_len = cur; best_mid = mid_b
            cur = 0
    if cur >= 5:
        mid_b = cs + cur / 2.0
        ls = max(0, cs - FLANK)
        le = cs
        rs = cs + cur
        re = min(nbins, cs + cur + FLANK)
        left_chars = sum(hist[ls:le])
        right_chars = sum(hist[rs:re])
        if left_chars >= 40 and right_chars >= 40 and \
           min(left_chars, right_chars) >= asymmetry_ratio * max(left_chars, right_chars) and \
           col_mass_ok(mid_b):
            if cur > best_len:
                best_len = cur; best_mid = mid_b
    if best_mid is None:
        return None
    return best_mid * bin_w


def detect_columns(page, gutter_search=None, gutter_x=None):
    """Detect single vs two-column layout. Returns (kind, gutter_x or None).

    gutter_x: if provided, skip detection and return this fixed value
    (PDF pts). Use for books where automatic detection is unreliable.
    gutter_search: optional dict overriding find_gutter_by_whitespace params
    (e.g. {'search_lo':0.48, 'search_hi':0.58}) for per-book forced
    two-col detection where the gutter zone is known."""
    if gutter_x is not None:
        return ('two-col', float(gutter_x))
    if gutter_search:
        gutter = find_gutter_by_whitespace(page, **gutter_search)
    else:
        gutter = find_gutter_by_whitespace(page)
    if gutter is None:
        return ('single', None)
    return ('two-col', float(gutter))


def page_image_bboxes(page):
    """Return [(x0,y0_top,x1,y1_bottom)] in SCREEN coords (top-down y) for
    raster image objects on the page. Vector paths (graphs) are NOT included
    here — they render as part of the page bitmap and are captured naturally
    by full-width crops. Decorative page-spanning backgrounds are filtered."""
    H = float(page.get_height()); W = float(page.get_width())
    out = []
    IMAGE = 3
    try:
        for obj in page.get_objects(max_depth=8):
            try:
                t = obj.type
            except Exception:
                continue
            if t != IMAGE:
                continue
            try:
                l, b, r, ttop = obj.get_pos()
            except Exception:
                continue
            x0, x1 = float(l), float(r)
            y0_s = H - float(ttop)
            y1_s = H - float(b)
            if (x1 - x0) > 0.9 * W and (y1_s - y0_s) > 0.9 * H:
                continue
            if (x1 - x0) < 6 or (y1_s - y0_s) < 6:
                continue
            out.append((x0, y0_s, x1, y1_s))
    except Exception:
        pass
    return out


def page_figure_bboxes(page):
    """Return [(x0,y0_top,x1,y1_bottom)] SCREEN-coord bboxes for BOTH raster
    images and vector (path-drawn) figures. Used to exclude figure regions
    when collecting per-column text lines, so a side figure's axis labels /
    caption never masquerade as a question band. Only *large* vector objects
    count as figures (small paths are axis ticks / arrows / box rules)."""
    H = float(page.get_height()); W = float(page.get_width())
    out = page_image_bboxes(page)
    try:
        for obj in page.get_objects(max_depth=8):
            try:
                t = obj.type
            except Exception:
                continue
            if t == 3:  # raster already handled
                continue
            try:
                l, b, r, ttop = obj.get_pos()
            except Exception:
                continue
            x0, x1 = float(l), float(r)
            y0_s = H - float(ttop)
            y1_s = H - float(b)
            w = x1 - x0; h = y1_s - y0_s
            if w < 0.18 * W or h < 0.12 * H:
                continue  # too small to be a figure region
            if w > 0.9 * W and h > 0.9 * H:
                continue  # full-page background
            out.append((x0, y0_s, x1, y1_s))
    except Exception:
        pass
    return out


def visual_ink_mask(page, dpi=200, x_frac_lo=0.0, x_frac_hi=0.22,
                    min_sat=0, dark_lum=150):
    """Render the page and return the ink pixel set for the x-strip
    [x_frac_lo, x_frac_hi] of the page width, as a set of (y_px, x_px) in the
    RENDERED bitmap. A pixel is 'ink' if it is dark (luminance < dark_lum) OR
    strongly saturated (saturation > min_sat). Use min_sat>0 to isolate
    COLOURED question numbers (which a text-layer or plain-grey detector
    misses) while excluding black sub-part letters. Pure-white backgrounds
    and pale tints are excluded."""
    H = float(page.get_height()); W = float(page.get_width())
    scale = dpi / 72.0
    bmp = page.render(scale=scale)
    img = bmp.to_pil().convert('RGB')
    Wp, Hp = img.width, img.height
    x0 = int(x_frac_lo * Wp); x1 = int(min(Wp, x_frac_hi * Wp))
    px = img.load()
    ink = set()
    for py in range(Hp):
        for pxc in range(x0, x1):
            r, g, b = px[pxc, py]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            mx = max(r, g, b); mn = min(r, g, b)
            sat = mx - mn
            if lum < dark_lum or (min_sat > 0 and sat > min_sat):
                ink.add((py, pxc))
    return ink, (Wp, Hp), scale


def _components(ink, min_h, max_h, min_w, max_w):
    from collections import deque
    seen = set(); comps = []
    for seed in ink:
        if seed in seen:
            continue
        stack = deque([seed]); seen.add(seed); ys = []; xs = []
        while stack:
            y, x = stack.popleft()
            ys.append(y); xs.append(x)
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nb = (y + dy, x + dx)
                if nb in ink and nb not in seen:
                    seen.add(nb); stack.append(nb)
        h = max(ys) - min(ys) + 1
        w = max(xs) - min(xs) + 1
        if min_h <= h <= max_h and min_w <= w <= max_w:
            comps.append((min(ys) + max(ys)) / 2.0)
    return comps


def visual_qnum_tops(page, dpi=200, x_frac_lo=0.0, x_frac_hi=0.14,
                      min_h=6, max_h=42, min_w=4, max_w=60,
                      min_sat=0, dark_lum=150, y_min=0.0, y_max=1.0):
    """Colour-agnostic question-number detector for the LEFT MARGIN.

    Some maths textbooks (Haese) render question numbers in a coloured maths
    font whose glyphs have NO text-layer representation, so the text-layer
    detector merges adjacent questions. This renders the left margin strip and
    finds connected ink components (BFS flood fill on the ink pixel set); each
    component whose bounding box looks like a single digit/number glyph
    (reasonable height/width, sitting in the left margin) is a question number.
    With min_sat>0 it isolates COLOURED qnums only (black sub-part letters and
    the page header are excluded). Returns a sorted list of y-centres in PDF
    points (top-down), one per detected question number. No OCR."""
    ink, (Wp, Hp), scale = visual_ink_mask(page, dpi=dpi, x_frac_lo=x_frac_lo,
                                           x_frac_hi=x_frac_hi, min_sat=min_sat,
                                           dark_lum=dark_lum)
    if not ink:
        return []
    H = float(page.get_height())
    lo_y = max(0.0, y_min * H); hi_y = min(H, y_max * H)
    raw = _components(ink, min_h, max_h, min_w, max_w)
    tops = sorted(c / scale for c in raw if lo_y <= (c / scale) <= hi_y)
    return tops


def answer_qnum_positions(answer_page, dpi=200, x_frac_lo=0.0, x_frac_hi=0.5,
                           min_h=6, max_h=42, min_w=3, max_w=160,
                           min_sat=0, dark_lum=150):
    """For a WORKED-SOLUTIONS page: return sorted list of (y_pdf) positions of
    every left/leading number on the page (the worked solutions lead each
    question with its number). Used to match textbook questions to their
    answer by VERTICAL POSITION (same printed page geometry), avoiding OCR."""
    ink, (Wp, Hp), scale = visual_ink_mask(answer_page, dpi=dpi,
                                           x_frac_lo=x_frac_lo, x_frac_hi=x_frac_hi,
                                           min_sat=min_sat, dark_lum=dark_lum)
    if not ink:
        return []
    return sorted(c / scale for c in _components(ink, min_h, max_h, min_w, max_w))


# ---------------------------------------------------------------------------
# Coloured question-number recovery (Haese Core Topics HL 1).
#
# Haese renders the ENTIRE maths font in colour. Most question numbers are
# black in the text layer, but SOME are coloured (blue, hue ~150-185) and have
# NO text-layer glyph, so the text-layer detector merges the two adjacent
# questions into one band. We recover the missing number visually, with NO OCR:
#   * render the page, flood-fill ink (lum<dark OR sat>min_sat)
#   * find blue (hue 140-195), digit-sized, LEFT-EDGE components near a
#     text-number x0 cluster
#   * keep only those > GAP pt from every black text-layer number (i.e. they
#     sit inside a tall merged band, not inside a normal-length question)
# Each survivor is a genuine missing question number => a split point.
# ---------------------------------------------------------------------------
_VIS_HUE_LO = 140.0
_VIS_HUE_HI = 195.0
_VIS_GAP = 200.0
_VIS_DPI = 150

def visual_missing_qnums(page, x_lo, x_hi, dpi=_VIS_DPI, gap=_VIS_GAP):
    """Return sorted list of y-TOPS (PDF pt) of coloured question numbers the
    text layer missed, within the column x-range [x_lo, x_hi]. Each is a split
    point: a band containing it should be broken there."""
    H = float(page.get_height())
    # text-layer number clusters + black-number y tops, restricted to column
    xs, bys = [], []
    for top, t, x0 in pdfium_lines(page):
        if not (x_lo - 30 <= x0 <= x_hi + 30):
            continue
        if re.match(r'^\s*\d{1,2}\s+[A-Za-z]', t) and 0.05 * H <= top <= 0.95 * H:
            xs.append(x0); bys.append(float(top))
    if not xs:
        return []
    xs.sort(); grouped = []
    for x in xs:
        if grouped and x - grouped[-1][-1] <= 40:
            grouped[-1].append(x)
        else:
            grouped.append([x])
    clusters = [sum(c) / len(c) for c in grouped]
    ink, (Wp, Hp), scale = visual_ink_mask(page, dpi=dpi, x_frac_lo=0.0,
                                           x_frac_hi=1.0, min_sat=80,
                                           dark_lum=150)
    if not ink:
        return []
    img = page.render(scale=dpi / 72.0).to_pil().convert('HSV')
    px = img.load()
    from collections import deque
    seen = set(); splits = []
    for seed in ink:
        if seed in seen:
            continue
        stack = deque([seed]); seen.add(seed)
        ys = []; xs_ = []
        while stack:
            y, x = stack.popleft(); ys.append(y); xs_.append(x)
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nb = (y + dy, x + dx)
                if nb in ink and nb not in seen:
                    seen.add(nb); stack.append(nb)
        h = (max(ys) - min(ys) + 1) / scale
        w = (max(xs_) - min(xs_) + 1) / scale
        if not (14.0 <= h <= 23.0 and 5.0 <= w <= 28.0):
            continue
        cx0 = min(xs_) / scale
        if not any(abs(cx0 - c) <= 25 for c in clusters):
            continue
        # left-edge within column: nothing to the left of this component inside
        # the column (otherwise it is an in-body glyph, not a qnum)
        col_left = min(clusters, key=lambda c: abs(c - cx0)) - 25
        yb0 = int(round(min(ys))); yb1 = int(round(max(ys)))
        xa = int(round(col_left * scale)); xb = int(round((cx0 - 1.0) * scale))
        if xb > xa and any((py, pxc) in ink for py in range(yb0, yb1 + 1)
                           for pxc in range(xa, xb + 1)):
            continue
        # blue only
        hs = [px[pxc, py][0] for py in range(min(ys), max(ys) + 1)
              for pxc in range(min(xs_), max(xs_) + 1) if (py, pxc) in ink]
        if not (_VIS_HUE_LO <= (sum(hs) / len(hs) if hs else -1) <= _VIS_HUE_HI):
            continue
        cy = (min(ys) + max(ys)) / 2 / scale
        # far from every black text-layer number => sits inside a tall band
        dmin = min(abs(cy - b) for b in bys) if bys else 999
        if dmin > gap:
            splits.append(min(ys) / scale)  # split at the number's TOP
    return sorted(splits)


def apply_visual_splits(bands, split_ys):
    """Insert split points (y tops) into a list of (num, y0, y1) bands.

    The first sub-band of a split keeps the original number; each subsequent
    sub-band gets the next integer (num+1, num+2, ...) because the recovered
    coloured numbers ARE the consecutive question numbers that were missed —
    this keeps the `source` label correct (e.g. Q14 -> Q14, Q15). When the
    parent number is unknown (None) the sub-bands stay None."""
    if not split_ys:
        return bands
    out = []
    for (num, y0, y1) in bands:
        inner = sorted(s for s in split_ys if y0 < s < y1)
        if not inner:
            out.append((num, y0, y1)); continue
        prev = y0
        for k, s in enumerate(inner):
            nn = (num + k) if isinstance(num, int) else None
            out.append((nn, prev, s)); prev = s
        out.append(((num + len(inner)) if isinstance(num, int) else None, prev, y1))
    return out


def _filter_monotonic(candidates, sc):
    """Select the LONGEST ascending run of question numbers, dropping
    earlier noise (page-header numbers that overflow above the page, or
    running-header page numbers) and in-body sub-numbers.

    A 'run' is a sequence of numeric candidates whose numbers are strictly
    ascending with step <= max_step. We pick the longest such run; this is
    robust against a stray header number (e.g. a running '14' at the very
    top of a Mixed-Practice page that is NOT question 14) poisoning the
    start of the sequence, because the real run (1, 2, 3, ...) is always
    longer than the one- or two-element run from a header.

    Tie-break: if two runs have equal length, prefer the start whose top is
    NOT in the header zone (top >= 0.06*H) so a real question is chosen over
    a same-length header run further up.
    """
    cands = sorted(candidates, key=lambda c: c[0])
    if not cands:
        return []
    if not sc.get('monotonic'):
        return cands
    n = len(cands); nums = [c[1] for c in cands]
    run = [0]*n
    for i in range(n-1, -1, -1):
        ni = nums[i]
        if ni is None:
            run[i] = 0
        elif i == n-1:
            run[i] = 1
        else:
            nj = nums[i+1]
            if nj is not None and nj > ni and (nj - ni) <= sc['max_step']:
                run[i] = run[i+1] + 1
            else:
                run[i] = 1
    best_len = max(run)
    if best_len == 0:
        return cands  # only bare-dot candidates
    best = -1
    for i in range(n):
        if run[i] != best_len:
            continue
        if best == -1:
            best = i; continue
        if cands[best][0] < 0.06 and cands[i][0] >= 0.06:
            best = i
    kept = [best]
    for i in range(best+1, n):
        prev = cands[kept[-1]][1]; cur = cands[i][1]
        if prev is not None and cur is not None and cur > prev and (cur - prev) <= sc['max_step']:
            kept.append(i)
        elif cur is None and prev is not None:
            kept.append(i)
        else:
            break
    return [cands[i] for i in kept]


# "How do / How can ..." inquiry boxes are coloured info prompts, NOT practice
# questions. They sit above real practice questions on the same page, so they
# must not start a question band (but the page itself stays valid).
_INQUIRY_RE = re.compile(
    r'^\s*how\s+(can|do|does|is|are|would|could|might|many|much|will|far|'
    r'has|have|why|what|when|where|who)\b', re.I)

# Oxford "Extended-response questions" pages number questions as "Question 1",
# "Question 2" (spelled out, not a bare left-margin digit).  Catch those as
# real band starts when a book opts in via seg['worded_qnum'].  pypdfium often
# prepends a few garbage glyphs, so allow a short leading run before "Question".
_QUESTION_WORD_RE = re.compile(r'Question\s+(\d+)')


def question_bands_pdfium(page, cfg=None):
    """Return [(num, y0, y1), ...] for NUMBER question starts using pypdfium
    glyph layout.

    ONLY NUMBER question numbers begin a question; letter sub-parts (a), (b)
    are nested under their parent and never split. In-body spurious numbers
    ("2 The ...", equation indices) are rejected by left-margin discipline
    (the number must sit near the page's left edge) plus an ascending-
    monotonic sequence check.

    `cfg` is a per-book seg dict (merged onto DEFAULT_SEG). Tuples carry the
    integer question number, or None for bare-dot markers whose digits are
    missing from the text layer.

    Haese fallback: lines whose leading digit got OCR-misread to `&`/`?`
    (math-font glyph confusion) are recovered by `_line_start_number_alt_glyph`
    and treated as the standard digit. This catches Q4 / Q5 / etc. on review
    pages where pypdfium reads the stem-stripped 4 as the ampersand.
    """
    H = float(page.get_height()); W = float(page.get_width())
    sc = _seg_cfg(cfg)
    margin = sc['qnum_margin'] * W
    candidates = []  # (top_screen, num_or_None, x0)
    for top, text, x0 in pdfium_lines(page):
        # skip header/footer PAGE NUMBERS (short rows at top ~5% / bottom ~6%)
        if (0 <= top < 0.05 * H or top > 0.94 * H) and len(text) < 15:
            continue
        # page header = page number + ALL-CAPS section title -- never a question
        if top < 0.06 * H and re.match(r'^\d{1,3}\s+[A-Z]{2,}', text):
            continue
        # running header like '1 Counting principles' / '12 Mixed Practice':
        if top < 0.05 * H and len(text) <= 35 and HEADER_TITLE_RE.match(text):
            continue
        # Inquiry boxes ("How do / How can ...") are coloured info prompts, not
        # practice questions — never anchor a band on them.
        if _INQUIRY_RE.match(text):
            continue
        # Oxford "Question N" spelled-out numbering (extended-response pages).
        # pypdfium sometimes prepends a few garbage glyphs, so search anywhere
        # but require the match to sit near the line start (a real question
        # label, not a body reference to "Question N").
        if sc.get('worded_qnum'):
            mq = _QUESTION_WORD_RE.search(text)
            if mq and mq.start() <= 16 and x0 <= margin:
                candidates.append((float(top), int(mq.group(1)), float(x0)))
                continue
        num = _line_start_number(text, sc['strict_qnum'])
        if num is not None:
            # left-margin discipline: the number must sit near the page's left
            # edge. In-body numbers (indented) are rejected here.
            if x0 > margin:
                continue
            # Some books (Oxford) opt out of bare-digit-alone anchors because
            # graph-axis labels ("120") render as a lone number and masquerade
            # as a qnum.  Digit+body numbers (the normal case) are unaffected.
            if sc.get('reject_bare_digit_alone') and re.match(r'^\d{1,3}$', text.strip()):
                continue
            candidates.append((float(top), num, float(x0)))
            continue
        # Haese math-font glyph recovery: '&'-misread '4', '?'-misread '7'.
        alt = _line_start_number_alt_glyph(text)
        if alt is not None and x0 <= margin:
            candidates.append((float(top), alt, float(x0)))
            continue
        if not sc.get('no_bare_dot') and _bare_dot(text):
            candidates.append((float(top), None, float(x0)))
    # Drop any candidate sitting *inside* a raster figure's bbox. Coloured graph
    # axis labels, photo captions, and in-diagram numbers are text-layer glyphs
    # with no real question meaning; they live in the body, not the left margin,
    # so this catches the ones the left-margin rule misses.
    figs = page_image_bboxes(page)
    if figs:
        kept = []
        for (top, num, x0) in candidates:
            inside = any(ix0 - 6 <= x0 <= ix1 + 6 and iy0 - 6 <= top <= iy1 + 6
                         for (ix0, iy0, ix1, iy1) in figs)
            if inside:
                continue
            kept.append((top, num, x0))
        candidates = kept
    candidates = _filter_monotonic(candidates, sc)
    if not candidates:
        return []
    bands = []
    for i, (top, num, x0) in enumerate(candidates):
        nxt = candidates[i + 1][0] if i + 1 < len(candidates) else H
        y0 = max(0.0, top - sc['top_pad'])
        y1 = min(H, nxt - sc['bottom_pad'])
        bands.append((num, y0, y1))
    return bands


def extract_band_text_pdfium(page, y0, y1):
    """Extract text within a vertical band via pypdfium textpage."""
    H = float(page.get_height()); W = float(page.get_width())
    y0 = max(0.0, y0); y1 = min(H, y1)
    if y1 <= y0:
        return ''
    # we approximate by extracting full page text then filtering. pypdfium has
    # no direct rect-extraction, so this is the simplest reliable path.
    txt = pdfium_page_text(page)
    # crude line-based filtering by y-position is not feasible without bbox for
    # every glyph; for now we use a heuristic: filter by approximate line
    # containing the band (good enough for cropping context).
    return txt  # full-page text; sufficient for source-string fallback


def page_chapter_pdfium(page):
    """Chapter title from the header zone: 'SETS AND VENN DIAGRAMS (Chapter 2)'
    or '30 STRAIGHT LINES (Chapter 1)' -> 'Sets And Venn Diagrams'."""
    lines = [t for _, t, _ in pdfium_lines(page)]
    for l in lines[:10]:
        m = re.match(r'^(?:\d+\s+)?([A-Z][A-Z &,\-]{3,50})\s*\(Chapter\s*\d+\)',
                     l.strip())
        if m:
            return m.group(1).strip().title()
    return None


def _review_label(suffix):
    """Normalize a review-set suffix: '1A' -> 'Review set 1A'.

    Math-font glyph confusion makes 'B' extract as '8' and 'A' as '4' when
    the letter is missing its stem, so a pure-digit suffix of length >= 2
    ending in 4/8 is really N+A / N+B (Haese review sets ALWAYS carry an
    A/B suffix, so a bare number is always a misread).
    """
    s = re.sub(r'\s+', '', (suffix or '')).upper()
    if s.isdigit() and len(s) >= 2 and s[-1] in '48':
        s = s[:-1] + ('A' if s[-1] == '4' else 'B')
    return 'Review set ' + s


def section_transitions_pdfium(page):
    """Return [(top, label)] section banners on the page, sorted by top.

    A banner like 'REVIEW SET 1A' can start MID-PAGE (Haese review sets flow
    continuously), so questions on one page may belong to two different
    sections. Labels: 'Review set 1A', 'Test Yourself', 'Chapter Review', ...
    """
    trans = []
    for top, t, x0 in pdfium_lines(page):
        m = re.search(r'\breview\s+set\s+(\d+\s*[A-B0-9]?)\b', t, re.I)
        if m:
            trans.append((float(top), _review_label(m.group(1))))
            continue
        m = re.search(r'\b(test\s+yourself|mixed\s+practice|mixed\s+review|'
                      r'chapter\s+review|end[\s-]?of[\s-]?chapter\s+'
                      r'(questions?|exercises?)|revision\s+(exercise|set|questions?))'
                      r'\b', t, re.I)
        if m:
            trans.append((float(top), m.group(0).strip().title()))
    trans.sort(key=lambda r: r[0])
    return trans


def section_for_page_pdfium(page, prev):
    """Heuristic section label using pypdfium line-rebuilt text + first lines.

    Priority order (Haese books carry a 'REVIEW SET 3A' label, usually in the
    page header band; the chapter title line looks like 'SETS AND VENN
    DIAGRAMS (Chapter 2)'):
      1. 'Review set N A/B' label in the header zone -> combined with the
         chapter title when available ('Sets and Venn diagrams — Review set 2A')
      2. other practice headings (Test yourself, Chapter review, ...)
      3. generic chapter/section heading at line start
      4. previous page's section
    """
    lines = [t for _, t, _ in pdfium_lines(page)]
    head = lines[:10]

    def norm_title(s):
        return s.strip()[:60]

    # chapter title line: 'SETS AND VENN DIAGRAMS (Chapter 2)' or
    # '30 STRAIGHT LINES (Chapter 1)'
    chapter = None
    for l in head:
        m = re.match(r'^(?:\d+\s+)?([A-Z][A-Z &,\-]{3,50})\s*\(Chapter\s*\d+\)',
                     l.strip())
        if m:
            chapter = m.group(1).strip().title()
            break

    # review set label: 'REVIEW SET 3A' (may sit anywhere in the header zone)
    for l in head:
        m = re.search(r'\breview\s+set\s+(\d+\s*[A-B0-9]?)\b', l, re.I)
        if m:
            label = _review_label(m.group(1))
            return f'{chapter} — {label}' if chapter else label

    # other practice headings
    for l in head:
        m = re.search(r'\b(test\s+yourself|mixed\s+practice|mixed\s+review|'
                      r'chapter\s+review|end[\s-]?of[\s-]?chapter\s+'
                      r'(questions?|exercises?)|revision\s+(exercise|set))\b',
                      l, re.I)
        if m:
            label = m.group(0).strip().title()
            return f'{chapter} — {label}' if chapter else label

    for l in head:
        # tightened: require 'N.M TitleCase word' so math lines like
        # '0.36 ≤ x < ...' are not mistaken for section numbers
        if re.match(r'^(chapter|section|topic|unit)\b', l, re.I):
            return norm_title(l)
        if re.match(r'^\d+\.\d+\s+[A-Z][a-z]{2,}', l.strip()):
            return norm_title(l)
    return prev or 'Exercises'


def question_bands_from_lines(lines, H, cfg=None, ref_x=0.0, page_width=None, page=None):
    """Same as question_bands_pdfium but on a caller-supplied (already filtered
    by column) list of (top, text, x0). Header/footer filtering uses y-fractions
    of H. Returns [(num, y0, y1), ...].

    `ref_x` is the column's left edge (0 for single column / left column); the
    left-margin discipline is measured relative to it so two-column pages work.
    `page_width` is the full page width used to convert qnum_margin (a fraction)
    into points.
    """
    if not lines:
        return []
    sc = _seg_cfg(cfg)
    W = page_width if page_width else (
        max(x0 for _, _, x0 in lines) if lines else 1000.0)
    margin = sc['qnum_margin'] * W
    candidates = []
    for top, text, x0 in lines:
        if top < 0:
            continue
        if (0 <= top < 0.05 * H or top > 0.94 * H) and len(text) < 15:
            continue
        if top < 0.06 * H and re.match(r'^\d{1,3}\s+[A-Z]{2,}', text):
            continue
        if top < 0.05 * H and len(text) <= 35 and HEADER_TITLE_RE.match(text):
            continue
        num = _line_start_number(text, sc['strict_qnum'])
        if num is not None:
            if (x0 - ref_x) > margin:
                continue
            candidates.append((float(top), num, float(x0)))
            continue
        # Oxford "Question N" spelled-out numbering (extended-response pages).
        # Mirror question_bands_pdfium so the two-column split path applies the
        # same anchors; without this, spelled-out numbers only register on the
        # single-column path and the column path misses/splits them.
        if sc.get('worded_qnum'):
            mq = _QUESTION_WORD_RE.search(text)
            if mq and mq.start() <= 16 and (x0 - ref_x) <= margin:
                candidates.append((float(top), int(mq.group(1)), float(x0)))
                continue
        num = _line_start_number(text, sc['strict_qnum'])
        if num is not None:
            if (x0 - ref_x) > margin:
                continue
            # reject_bare_digit_alone drops lone graph-axis labels ("120").
            if sc.get('reject_bare_digit_alone') and re.match(r'^\d{1,3}$', text.strip()):
                continue
            candidates.append((float(top), num, float(x0)))
            continue
        # Haese math-font glyph recovery: '&'-misread '4', '?'-misread '7'.
        alt = _line_start_number_alt_glyph(text)
        if alt is not None and (x0 - ref_x) <= margin:
            candidates.append((float(top), alt, float(x0)))
            continue
        if not sc.get('no_bare_dot') and _bare_dot(text):
            candidates.append((float(top), None, float(x0)))
    # Drop any candidate sitting *inside* a raster figure's bbox. Coloured graph
    # axis labels, photo captions, and in-diagram numbers are text-layer glyphs
    # with no real question meaning; this is the figure-bbox filter from the
    # single-column path, applied here too so column-split pages are consistent.
    figs = page_image_bboxes(page)
    if figs:
        kept = []
        for (top, num, x0) in candidates:
            inside = any(ix0 - 6 <= x0 <= ix1 + 6 and iy0 - 6 <= top <= iy1 + 6
                         for (ix0, iy0, ix1, iy1) in figs)
            if inside:
                continue
            kept.append((top, num, x0))
        candidates = kept
    candidates = _filter_monotonic(candidates, sc)
    if not candidates:
        return []
    bands = []
    for i, (top, num, x0) in enumerate(candidates):
        nxt = candidates[i + 1][0] if i + 1 < len(candidates) else H
        y0 = max(0.0, top - sc['top_pad'])
        y1 = min(H, nxt - sc['bottom_pad'])
        bands.append((num, y0, y1))
    return bands


def render_page_crops_xy(page, boxes, out_paths, dpi=DPI):
    """Render the page ONCE, then PIL-crop each (x_min,x_max,y0,y1) box.
    boxes & out_paths are parallel lists. y is top-down screen-space (PDF pts).
    Robust against pypdfium's native crop quirks. Returns number saved."""
    if not boxes:
        return 0
    scale = dpi / 72.0
    bmp = page.render(scale=scale)
    img = bmp.to_pil()
    Wp, Hp = img.width, img.height
    saved = 0
    for (x0, x1, y0, y1), out_path in zip(boxes, out_paths):
        px0 = max(0, min(Wp - 1, int(round(x0 * scale))))
        px1 = max(px0 + 4, min(Wp, int(round(x1 * scale))))
        py0 = max(0, min(Hp - 1, int(round(y0 * scale))))
        py1 = max(py0 + 4, min(Hp, int(round(y1 * scale))))
        if px1 - px0 < 4 or py1 - py0 < 4:
            continue
        img.crop((px0, py0, px1, py1)).save(out_path, 'JPEG', quality=88)
        saved += 1
    return saved


def save_crop_relname(book_id, kind, page, idx):
    fname = f"book_{book_id}_{kind}_p{page}_{idx}.jpg"
    return fname, os.path.join(FIG_DIR, fname)
