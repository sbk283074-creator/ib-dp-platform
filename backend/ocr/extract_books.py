#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Driver: extract concentrated exercise sets from a registry of IB books and
emit per-book JSON consumable by POST /api/books/import.

Memory-friendly: uses pypdfium only (no pdfplumber caches).
"""
import os, re, json, argparse, sys, logging, warnings, gc
warnings.filterwarnings('ignore')
logging.getLogger('pdfminer').setLevel(logging.CRITICAL)
logging.getLogger('pdfplumber').setLevel(logging.CRITICAL)
import booklib as B
import pypdfium2 as pdfium
from PIL import Image as _Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, 'book_json')
os.makedirs(OUT_DIR, exist_ok=True)

DP = "/Users/lucas.ma/Downloads/dp learning"

# ---------------------------------------------------------------- registry
# Math textbook end-of-chapter / mixed-practice headings ONLY (exclude
# per-section "Exercise N" pages, worked examples and theory).
MATH_CHAPTER_END = [
    r'mixed\s+practice',
    r'mixed\s+review',
    r'review\s+set',
    r'chapter\s+review',
    r'self[\s-]?test',
    r'test\s+yourself',
    r'practice\s+questions?',
    r'mixed\s+questions?',
    r'revision\s+(exercise|set|questions?)',
    r'end[\s-]?of[\s-]?chapter\s+(questions?|exercises?)',
]

# Headings that mark a CONCENTRATED-PRACTICE page in any IB textbook
# (textbook-only — workbooks process every page).  This set is deliberately
# NARROW: only end-of-chapter, end-of-topic, mixed practice, review, and
# self-test pages qualify.  Per-section "Exercise N" pages, worked
# examples, theory, and the many in-chapter "Check your understanding"
# sub-lists are NOT included — those are the source of the over-extraction
# that previously produced ~1800 rows for Haese and ~1500 for Oxford.
PRACTICE_PATTERNS = [
    r'end[\s\-]?of[\s\-]?chapter\s+(questions?|exercises?)',
    r'end[\s\-]?of[\s\-]?topic\s+questions?',
    r'end[\s\-]?of[\s\-]?unit',
    r'mixed\s+practice',
    r'mixed\s+review',
    r'mixed\s+questions?',
    r'review\s+set',
    r'chapter\s+review',
    r'self[\s-]?test',
    r'test\s+yourself',
    r'practice\s+questions?',            # Oxford CS "Practice questions"
    r'topic\s+review',                  # Oxford CS "Topic review"
    r'revision\s+(exercise|set|questions?)',
    r'exam[\s\-]?style\s+(questions?|practice)',
    r'summary\s+questions?',
]

BOOKS = [
    dict(id='CS-OX-2025', subject='CS', level='HL',
         title='Computer Science Coursebook (Oxford 2025)',
         publisher='Oxford', edition='MacKenty & Stephenson 2025',
         path=f'{DP}/Computer Science - MacKenty and Stephenson - Oxford 2025.pdf',
         answer_path=None, has_answers=False, answer_source='ai-generated',
         # CS coursebook: concentrated practice = ONLY the end-of-topic and
         # topic-review pages at the end of each topic (8 topics).  The many
         # sub-section "Practice questions" pages mid-topic are NOT
         # concentrated end-of-chapter practice and must be excluded.
         exercise_patterns=[
             r'end[\s\-]?of[\s\-]?topic\s+questions?',
             r'topic\s+review',
         ],
         seg=dict(min_markers=3, crop_top=6, crop_bottom=6),
    ),
    dict(id='PH-OX-2023', subject='Physics', level='HL',
         title='Physics Course Companion (Oxford 5ed)',
         publisher='Oxford', edition='Homer, Piętka & Heathcote 2023',
         path=f'{DP}/Physics-HLSL-Oxford Textbook(First exam 2025)/Physics - Course Companion - Homer, Piętka and Heathcote - Fifth Edition - Oxford 2023.pdf',
         answer_path=f'{DP}/Physics-HLSL-Oxford Textbook(First exam 2025)/Physics - ANSWERS - Homer, Piętka and Heathcote - Fifth Edition - Oxford 2023 [semi-official].pdf',
         has_answers=True, answer_source='Oxford ANSWERS 2023',
         # Oxford practice pages carry explicit headings; require them (the
         # fallback PRACTICE_PATTERNS missed these, so the gate fell back to
         # bare min_markers and let theory / worked-example / IA / index pages
         # through).  page_exclude_re kills the non-question pages the user
         # reported (IA, "How do" inquiry boxes live on practice pages so they
         # are handled at the band level, not here).
         exercise_patterns=[
             r'practice questions',
             r'extended-response questions',
             r'end-of-the-theme questions',
             r'end-of-the-theme',
             r'topic\s+\d+\s+questions',
             r'test yourself',
             r'mixed review',
             r'\breview\b',
         ],
         page_exclude_re=(
             r'(worked example|^\s*solution\b|internal assessment|'
             r'approaching your internal assessment|^\s*index\b|'
             r'^\s*glossary\b|topic\s+[a-z]\.\d)'
         ),
         # Oxford numbers questions two ways: "Practice questions" pages use
         # bare left-margin digits ("8 The …"), while "Extended-response
         # questions" pages spell them out as "Question 1", "Question 2" — the
         # bare-digit detector never sees those, so they merged into one crop.
         # worded_qnum catches the spelled-out form.  no_bare_dot stops misread
         # "ii." sub-parts (". Calculate …") from spawning numberless bands, and
         # reject_bare_digit_alone drops lone graph-axis labels ("120") that
         # otherwise slip through as a fake qnum.
         seg=dict(min_markers=4, crop_top=6, crop_bottom=6,
                  worded_qnum=True, no_bare_dot=True,
                  reject_bare_digit_alone=True),
    ),
    dict(id='PH-CAMB-ANS', subject='Physics', level='HL',
         title='Cambridge Coursebook Answers',
         publisher='Cambridge', edition='Tsokos 7ed',
         path=f'{DP}/Physics-HLSL-Cambridge-Textbook Answers(First exam 2025)/Coursebook answers.pdf',
         answer_path=None, has_answers=True, answer_source='Cambridge Coursebook answers',
         skip_extract=True),  # companion answer file, not a question source
    # Scanned workbooks: processed by extract_books_scanned.py
    dict(id='PH-TSOKOS-WB', subject='Physics', level='HL',
         title='Tsokos Physics Workbook (7ed)',
         publisher='Cambridge', edition='Tsokos 7ed', scanned=True,
         path=f'{DP}/Tsokos 7th edition Workbok.pdf',
         answer_path=f'{DP}/Tsokos 7th edition Workbook ANSWERS.pdf',
         has_answers=True, answer_source='Tsokos Workbook ANSWERS'),
    dict(id='PH-CAMB-WB', subject='Physics', level='HL',
         title='Cambridge Physics Workbook (7ed)',
         publisher='Cambridge', edition='Tsokos 7ed', scanned=True,
         path=f'{DP}/Physics-HLSL-Cambridge-Workbook(First exam 2025)/Physics - WORKBOOK - K.A. Tsokos - Seventh Edition - Cambridge 2023（扫描版）.pdf',
         answer_path=f'{DP}/Physics-HLSL-Cambridge-Textbook Answers(First exam 2025)/Coursebook answers.pdf',
         has_answers=True, answer_source='Cambridge Coursebook answers'),
    dict(id='MA-HODDER-WB', subject='Math AA HL', level='HL',
         title='Math AA HL Exam Practice Workbook (Hodder 2021)',
         publisher='Hodder', edition='Fannon, Kadelburg & Ward 2021', scanned=True,
         path=f'{DP}/HL Workbook/Mathematics - Analysis and Approaches HL - Exam Practice Workbook - Hodder 2021.pdf',
         answer_path=f'{DP}/HL Workbook/Mathematics - Analysis and Approaches HL - Exam Practice Workbook - ANSWERS - Hodder 2021.pdf',
         has_answers=True, answer_source='Hodder ANSWERS 2021'),
    # Math AA HL textbooks (current syllabus, end-of-chapter / mixed practice only)
    dict(id='MA-HODDER-2019', subject='Math AA HL', level='HL',
         title='Mathematics AA HL (Hodder 2019)',
         publisher='Hodder', edition='Fannon, Kadelburg & Ward 2019',
         path=f'{DP}/Mathematics - Analysis and Approaches HL - Hodder 2019.pdf',
         answer_path=None, has_answers=False, answer_source='ai-generated',
         strict_qnum=True,
         seg=dict(min_markers=3, crop_top=8, crop_bottom=8),
    ),
    dict(id='MA-OXFORD-2019', subject='Math AA HL', level='HL',
         title='Mathematics AA HL (Oxford 2019)',
         publisher='Oxford', edition='Wathall et al. 2019',
         path=f'{DP}/HL OXFPRD 教材/Mathematics HL - Analysis and Approaches - OXFORD 2019.pdf',
         answer_path=None, has_answers=False, answer_source='ai-generated',
         strict_qnum=True,
         # Two-column pages throughout (Chapter review, Mixed practice, and
         # many end-of-section Exercise pages).  The gutter position varies
         # 374-518 of 855 between pages, so the previous fixed gutter_x=440
         # mis-split many pages.  Drop the fixed gutter and auto-detect
         # with a wider search band.
         two_col=True,
         gutter_search={'search_lo': 0.40, 'search_hi': 0.62, 'blank_thr': 0.72},
         seg=dict(qnum_margin=0.16, min_markers=3, crop_top=6, crop_bottom=6),
    ),
    dict(id='MA-HAESE-AA2', subject='Math AA HL', level='HL',
         title='Mathematics AA HL 2 (Haese 2019)',
         publisher='Haese', edition='Haese, Humphries, Ng et al. 2019',
         path=f'{DP}/HAESE AND HARRIS 最新教材/Mathematics - Analysis and Approaches HL 2 - Haese 2019.pdf',
         answer_path=f'{DP}/HAESE AND HARRIS 最新教材/Mathematics - Analysis and Approaches HL 2 - WORKED SOLUTIONS - Haese 2020.pdf',
         has_answers=True, answer_source='Haese WORKED SOLUTIONS',
         crop_dpi=150, strict_qnum=True,
         # Haese exercise pages use a text|figure two-column layout where the
         # figure side flips per question. The figure is a VECTOR drawing, so
         # page_image_bboxes() finds nothing — the vector-fallback branch in
         # the figure-separation block uses the text-line x-distribution to
         # mark the opposite column as the figure region and emit a separate
         # figure_image crop alongside the (full-width) question_image.
         figure_separate=True,
         # Concentrated practice in Haese = end-of-chapter "Review set" (and
         # chapter-end "Review") pages ONLY.  Per-section "Exercise 2A/2B/…"
         # drill pages must be EXCLUDED (textbook scope is end-of-chapter /
         # mixed practice, not per-section exercises).  Restricting the
         # detector headings prevents re-introducing the ~1800-row
         # over-extraction seen under the loose default patterns.
         exercise_patterns=[
             r'review\s+set',
             r'mixed\s+review',
             r'chapter\s+review',
             r'\breview\b',
             r'end[\s\-]?of[\s\-]?chapter\s+(questions?|exercises?)',
             r'end[\s\-]?of[\s\-]?topic\s+questions?',
         ],
         seg=dict(min_markers=3, max_step=3, crop_top=6, crop_bottom=6),
    ),
    dict(id='MA-HAESE-CORE1', subject='Math AA HL', level='HL',
         title='Mathematics Core Topics HL 1 (Haese 2019)',
         publisher='Haese', edition='Haese, Humphries, Ng et al. 2019',
         path=f'{DP}/HAESE AND HARRIS 最新教材/Mathematics - Core Topics HL 1 - Haese 2019.pdf',
         answer_path=f'{DP}/HAESE AND HARRIS 最新教材/Mathematics - Core Topics HL 1 - WORKED SOLUTIONS - Haese 2019.pdf',
         has_answers=True, answer_source='Haese WORKED SOLUTIONS',
         crop_dpi=150, strict_qnum=True,
         figure_separate=True,
         # Concentrated practice in Haese = end-of-chapter "Review set" (and
         # chapter-end "Review") pages ONLY.  Per-section "Exercise …" drill
         # pages are excluded.  See MA-HAESE-AA2 for the full rationale.
         exercise_patterns=[
             r'review\s+set',
             r'mixed\s+review',
             r'chapter\s+review',
             r'\breview\b',
             r'end[\s\-]?of[\s\-]?chapter\s+(questions?|exercises?)',
             r'end[\s\-]?of[\s\-]?topic\s+questions?',
         ],
         seg=dict(min_markers=3, max_step=3, crop_top=6, crop_bottom=6,
                 visual_split=True),
    ),
]


def first_left_letter_top(page, margin):
    """Top (PDF pts) of the first left-margin letter sub-part on a page, used to
    find where a continuation question's body begins. Returns 0.0 if none."""
    H = float(page.get_height())
    for top, text, x0 in B.pdfium_lines(page):
        if (0 <= top < 0.05 * H or top > 0.94 * H) and len(text) < 15:
            continue
        if B.LET_RE.match(text) and x0 <= margin:
            return top
    return 0.0


def stitch_continuation(carry_fp, page, ytop, W, H, dpi):
    """Append a continuation page's body (from `ytop` to page bottom, full width)
    vertically beneath an existing question image, in place. Keeps a question
    that spans two pages whole instead of losing its tail sub-parts."""
    import os as _os
    tmp = carry_fp + '.cont.tmp.jpg'
    B.render_page_crops_xy(page, [(0.0, W, ytop, H)], [tmp], dpi=dpi)
    base = _Image.open(carry_fp).convert('RGB')
    cont = _Image.open(tmp).convert('RGB')
    if cont.width != base.width:
        cont = cont.resize((base.width, int(cont.height * base.width / cont.width)))
    combined = _Image.new('RGB', (base.width, base.height + cont.height), 'white')
    combined.paste(base, (0, 0))
    combined.paste(cont, (0, base.height))
    combined.save(carry_fp, 'JPEG', quality=88)
    try:
        _os.remove(tmp)
    except OSError:
        pass


def extract_text_book_pdfium(book, dry_run=False):
    """Extract a text-based book using only pypdfium (memory-friendly)."""
    questions = []
    order = 0
    prev_section = None      # raw label in effect at the END of the last page
    prev_classified = False  # was the previous page an exercise page?
    section = None
    carry_order = None       # order of the question currently receiving
    carry_fp = None          #   continuation pages (spill-over sub-parts)
    path = book['path']
    patterns = book.get('exercise_patterns') or PRACTICE_PATTERNS
    dpi = book.get('crop_dpi', 200)
    cfg = book.get('seg')
    sc = B._seg_cfg(cfg)
    # Per-book detector min_markers: real concentrated-practice pages always
    # have multiple left-margin numbered questions.  The previous hard-coded
    # value of 1 (in the call below) is what caused the textbook over-
    # extraction — any page with a single numbered list (theory, worked
    # example, TOC) was treated as a practice page and absorbed thousands
    # of questions across Haese / Oxford / Hodder / CS.
    det_min_markers = sc.get('min_markers', 3)
    # For textbooks, a page counts as a concentrated-practice page ONLY if it
    # carries a real practice HEADING (end-of-chapter / mixed / review set / …)
    # on its first page, OR it is a CONTINUATION of an already-accepted
    # exercise page (heading was on the previous page; this page only has the
    # numbered questions / sub-parts).  A standalone page that merely contains
    # >=min_markers numbered items but NO practice heading (a theory page with
    # an enumerated list, a worked-example page, a sub-section "Exercise N"
    # page) MUST be rejected — otherwise we re-introduce the 1500-1800 row
    # over-extraction.  Scanned workbooks use a different pipeline and are not
    # affected by this flag.
    gate_numbered = book.get('gate_numbered', True)
    pdf = pdfium.PdfDocument(path)
    try:
        n_pages = len(pdf)
        for i in range(n_pages):
            page = pdf[i]
            try:
                ok, hdr, kind = B.is_exercise_page_pdfium(page, patterns=patterns,
                                                       min_markers=det_min_markers,
                                                       exclude_re=book.get('page_exclude_re'))
            except Exception as e:
                sys.stderr.write(f"detect fail p{i+1}: {e}\n"); continue
            # Textbook gate: a page that classifies ONLY by left-margin numbers
            # ('numbered' kind) and is NOT a continuation of an already-
            # accepted exercise page must be rejected.  Such a page is a
            # theory / worked-example / sub-section page that happens to have
            # a numbered list, NOT a concentrated-practice page.  Heading-
            # matched pages ('head') and continuation pages ('continuation')
            # pass through unchanged.
            if gate_numbered and kind == 'numbered' and not prev_classified:
                ok = False
            if not ok:
                # Page skipped: do NOT trust section inheritance across a
                # non-exercise page (the banner may be many pages back and
                # belong to a different chapter). A skipped page also breaks
                # any in-progress continuation chain.
                prev_classified = False
                carry_order = None
                page = None; gc.collect(); continue
            section = B.section_for_page_pdfium(page, prev_section) or (hdr or 'Exercises')
            chapter = B.page_chapter_pdfium(page)
            # Section banners can start mid-page (Haese review sets flow
            # continuously): assign each question band the banner above it.
            trans = B.section_transitions_pdfium(page)
            base = prev_section if prev_classified else None

            def band_section(y0):
                lab = base
                for ttop, tlab in trans:
                    if ttop <= y0:
                        lab = tlab
                if lab is None:
                    lab = section
                if chapter and lab and not lab.startswith(chapter):
                    return f'{chapter} — {lab}'
                return lab or 'Exercises'

            try:
                bands = B.question_bands_pdfium(page, cfg=cfg)
            except Exception as e:
                sys.stderr.write(f"bands fail p{i+1}: {e}\n"); bands = []
            # ------------------------------------------------------------------
            # Column-aware page split: some math textbooks (Oxford 2019 "Chapter
            # review" / "Review set" pages) use a two-column layout. Full-width
            # horizontal cropping shreds them — left-column graphs get attached
            # to right-column questions at the same y. Detect columns, then
            # process each column independently with its own x-range, merging
            # questions that wrap across the gutter.
            # ------------------------------------------------------------------
            H = float(page.get_height()); W = float(page.get_width())
            if book.get('gutter_x') is not None:
                # Use a fixed gutter (calibrated visually) for books whose
                # rendered and text-histogram approaches both fail. This
                # is the Oxford 2019 case: the gutter zone has too much
                # text (axis labels, prompts straddling columns) for
                # automatic detection to be reliable.
                kind, gutter = ('two-col', float(book['gutter_x']))
            elif book.get('two_col'):
                # Forced two-column book: prefer a per-book gutter_search
                # (wider zone) so page-to-page variation in the gutter
                # position (Oxford 2019 ranges 374-518 of 855) is captured.
                # Falls back to a permissive central search if the book
                # does not specify its own.
                gs = book.get('gutter_search') or dict(
                    search_lo=0.40, search_hi=0.62, blank_thr=0.72)
                kind, gutter = B.detect_columns(page, gutter_search=gs)
            else:
                kind, gutter = B.detect_columns(page)
            gdicts = []  # final per-question crop dicts for this page
            if kind == 'two-col' and gutter:
                # Figure regions (raster + vector) to exclude when collecting a
                # column's text lines: a side figure's axis labels / caption
                # must not be read as a question band in the "other" column.
                fig_rects = B.page_figure_bboxes(page)
                # Build lines per column with mutual phantom dedup against the
                # other column (kills the rightward-shifted DRM text layer).
                left_lines = B.column_lines(page, 0.0, gutter, dedup_against=None,
                                            exclude_rects=fig_rects)
                right_lines = B.column_lines(page, gutter, W,
                                             dedup_against=[(t, tx) for (t, tx, _) in left_lines],
                                             exclude_rects=fig_rects)
                bl = B.question_bands_from_lines(left_lines, H, cfg=cfg, ref_x=0.0, page_width=W, page=page)
                br = B.question_bands_from_lines(right_lines, H, cfg=cfg, ref_x=gutter, page_width=W, page=page)
                # Coloured-number recovery: Haese renders some question numbers
                # in colour with no text-layer glyph, so the two adjacent
                # questions merged into one band. Recover the missing number
                # visually and split the band at it (per column x-range).
                if sc.get('visual_split'):
                    bl = B.apply_visual_splits(
                        bl, B.visual_missing_qnums(page, 0.0, gutter))
                    br = B.apply_visual_splits(
                        br, B.visual_missing_qnums(page, gutter, W))
                # Wrap-merge: if the last left-column band and the first right-
                # column band share the same question number, it's a single
                # question that overflowed into the right column. Merge into
                # one full-width band so the crop captures both halves.
                merged = False
                if bl and br:
                    ln = str(bl[-1][0]) if bl[-1][0] is not None else ''
                    rn = str(br[0][0]) if br[0][0] is not None else ''
                    if ln and ln == rn and ln.isdigit():
                        bl[-1] = (bl[-1][0], bl[-1][1], max(bl[-1][2], br[0][2]))
                        br = br[1:]
                        merged = True
                # Build gdicts. The wrap-merged (last left) band spans full width.
                gdicts = []
                for idx_l, (t, yo, y1) in enumerate(bl):
                    is_wrap = merged and idx_l == len(bl) - 1
                    gdicts.append(dict(tok=t, x0=0, x1=(W if is_wrap else gutter),
                                       y0=yo, y1=y1))
                for (t, yo, y1) in br:
                    gdicts.append(dict(tok=t, x0=gutter, x1=W, y0=yo, y1=y1))
            else:
                # Single-column page: full-width bands.
                if sc.get('visual_split'):
                    bands = B.apply_visual_splits(
                        bands, B.visual_missing_qnums(page, 0.0, W))
                for (t, yo, y1) in bands:
                    gdicts.append(dict(tok=t, x0=0, x1=W, y0=yo, y1=y1))

            # Drop fragment bands (overlapping-render noise) whose height is too
            # small to be a real question.
            MIN_BAND_PT = sc['min_band_pt']
            gdicts = [g for g in gdicts if (g['y1'] - g['y0']) >= MIN_BAND_PT]

            # Image attribution: enlarge each band to include any image object
            # whose centre lies near the band's y range and within the band's x
            # range (or is a full-width image). This keeps figures with their
            # owning question even when the figure sits at a y not exactly
            # inside the text band (e.g. a figure hanging at the bottom of a
            # question with the next question starting just below).
            imgs = B.page_image_bboxes(page)
            if imgs and gdicts:
                hs = sorted([g['y1'] - g['y0'] for g in gdicts])
                h_med = hs[len(hs) // 2] if hs else 80
                margin = 0.4 * h_med
                for g in gdicts:
                    gcy = (g['y0'] + g['y1']) / 2
                    for (ix0, iy0, ix1, iy1) in imgs:
                        icy = (iy0 + iy1) / 2
                        if icy < g['y0'] - margin or icy > g['y1'] + margin:
                            continue
                        x_ok = (ix0 >= g['x0'] - 10 and ix1 <= g['x1'] + 10)
                        full_w = (ix0 < 5 and ix1 > W - 5)
                        if not (x_ok or full_w):
                            continue
                        g['y0'] = min(g['y0'], iy0 - 4)
                        g['y1'] = max(g['y1'], iy1 + 4)
                        g['x0'] = min(g['x0'], ix0 - 4)
                        g['x1'] = max(g['x1'], ix1 + 4)

            # Crop padding: extend each band a few points beyond its text
            # boundary (clamped to the page and to the next band's top) so the
            # rendered question image is never clipped at top or bottom.
            for g in gdicts:
                g['y0'] = max(0.0, g['y0'] - sc['crop_top'])
                g['y1'] = min(H, g['y1'] + sc['crop_bottom'])

            # Figure separation for two-column text|figure layouts (e.g. Haese
            # exercise pages where the question text sits in one column and a
            # figure sits in the OTHER column, with the side flipping per
            # question). We do NOT restrict the question_image band — it stays
            # full-width so the complete view (text + figure together) is
            # preserved. Instead we set g['_fig_bbox'] to the figure region so
            # the render block emits a SEPARATE figure_image as a bonus crop.
            #
            # Two figure-detection strategies, tried in order:
            #  (1) Raster figures: page_image_bboxes() returns a figure in
            #      the column OPPOSITE the question's text.
            #  (2) Vector figures (Haese, where drawings are paths, not
            #      raster): use the x-distribution of the question's own text
            #      lines. If text is strongly lopsided (>= 80% in one half),
            #      the OPPOSITE half over the band's y-range is the figure
            #      region. A lopsidedness gate keeps Type A pages (sub-parts
            #      spanning full width, ~50/50 text) from being mis-split.
            if book.get('figure_separate') or book.get('vector_figure'):
                gx = float(book['gutter_x']) if book.get('gutter_x') is not None else (W * 0.5)
                plines = B.pdfium_lines(page)
                for g in gdicts:
                    ys0, ys1 = g['y0'], g['y1']
                    tlines = [(tx, x0) for (t, tx, x0) in plines
                              if (ys0 - 6) <= t <= (ys1 + 6)]
                    if not tlines:
                        continue
                    left_chars = sum(len(tx) for (tx, x0) in tlines if x0 < gx)
                    right_chars = sum(len(tx) for (tx, x0) in tlines if x0 >= gx)
                    total = left_chars + right_chars
                    if total < 20:
                        continue
                    text_is_left = left_chars >= right_chars
                    fig = None
                    # (1) raster-figure branch
                    for (ix0, iy0, ix1, iy1) in (imgs or []):
                        icy = (iy0 + iy1) / 2
                        if icy < ys0 - 14 or icy > ys1 + 14:
                            continue
                        icx = (ix0 + ix1) / 2
                        in_fig_col = (text_is_left and icx >= gx) or \
                                     ((not text_is_left) and icx < gx)
                        if in_fig_col:
                            fig = (ix0, iy0, ix1, iy1)
                            break
                    # (2) vector-figure fallback: opposite-column rectangle
                    if fig is None and (book.get('vector_figure') or book.get('figure_separate')):
                        dom = max(left_chars, right_chars)
                        if dom / total >= 0.80:
                            if text_is_left:
                                fig = (gx, ys0, g['x1'], ys1)
                            else:
                                fig = (g['x0'], ys0, gx, ys1)
                    g['_fig_bbox'] = fig

            # Render / append. Three cases:
            #  (a) normal exercise page with digit-anchored question bands -> create
            #      one question per band (sub-parts never split into questions).
            #  (b) continuation page (only sub-part letters, no digit number) that
            #      follows an exercise page -> stitch it beneath the previous
            #      question so the big question stays whole.
            #  (c) heading-only page with no questions -> nothing to emit; reset carry.
            if gdicts:
                # Render the page ONCE, crop each band (x- and y-clipped) to its
                # own JPEG. Memory-friendly for pages holding many questions.
                groups = gdicts
                band_tuples = [(g['x0'], g['x1'], g['y0'], g['y1']) for g in groups]
                out_paths = []
                fig_paths = []  # parallel to out_paths: (order, rel, fp) or None
                for g in groups:
                    order += 1
                    rel, fp = B.save_crop_relname(book['id'], 'q', i + 1, order)
                    out_paths.append((order, rel, fp))
                    if g.get('_fig_bbox'):
                        rel, fp = B.save_crop_relname(book['id'], 'f', i + 1, order)
                        fig_paths.append((order, rel, fp))
                    else:
                        fig_paths.append(None)
                if groups and not dry_run:
                    try:
                        B.render_page_crops_xy(page, band_tuples, [p for _, _, p in out_paths], dpi=dpi)
                    except Exception as e:
                        sys.stderr.write(f"crop fail {book['id']} p{i+1}: {e}\n")
                    # Haese figure_column mode: render a separate figure crop per
                    # question that has a figure in the opposite column.
                    fig_bands = [(fb[0], fb[1], fb[2], fb[3]) for fb in
                                 (g.get('_fig_bbox') for g in groups) if fb]
                    if fig_bands:
                        try:
                            B.render_page_crops_xy(
                                page, fig_bands,
                                [fp[2] for fp in fig_paths if fp], dpi=dpi)
                        except Exception as e:
                            sys.stderr.write(f"fig crop fail {book['id']} p{i+1}: {e}\n")
                        # Suppress blank figure crops: questions with no figure in
                        # the opposite column would otherwise get an empty rectangle.
                        from PIL import Image
                        for k, fp in enumerate(fig_paths):
                            if not fp:
                                continue
                            try:
                                im = Image.open(fp[2]).convert('L')
                                mn, _ = im.getextrema()
                                if mn >= 245:  # darkest pixel still near-white => blank
                                    fig_paths[k] = None
                            except Exception:
                                pass
                for g, (order, rel, fp), figp in zip(groups, out_paths, fig_paths):
                    # Per-page question number (band's leading token, e.g. "12" or
                    # "12.") — recorded so pair_answers.py can match answers by the
                    # REAL question number instead of guessing from the page number.
                    tok_val = g.get('tok')
                    tok_clean = str(tok_val) if tok_val is not None else ''
                    qnum_suffix = f' Q{tok_clean}' if tok_clean.isdigit() else ''
                    # Determine initial answer/explanation defaults.
                    # Books WITHOUT a companion answer file: write placeholders that
                    # the importer can patch as AI-generated. NOTE: book questions
                    # are ALWAYS authored_by='import' (they come from textbooks, not
                    # AI generation) — the AI-pending status lives in the answer
                    # placeholder text, never in authored_by.
                    has_companion = bool(book.get('answer_path'))
                    if has_companion:
                        answer_default = ''
                        explanation_default = f'Source: {book["title"]}, page {i+1}. See companion answer file for answer key.'
                    else:
                        answer_default = '__AI_FILL__'  # sentinel for importer to fill
                        explanation_default = '__AI_FILL__'
                    authored = 'import'
                    band_sec = band_section(g['y0'])
                    questions.append(dict(
                        id=f"{book['id']}-Q{order}",
                        subject=book['subject'], level=book['level'], topic=band_sec,
                        subtopic=None, paper_type=None, command_term=None,
                        marks=None, difficulty=None,
                        question=f"[See question image. Source: {book['title']}, page {i+1}.]",
                        answer=answer_default,
                        explanation=explanation_default,
                        source=f"{book['title']} · p{i+1}{qnum_suffix}",
                        tags=['book', book['publisher'].lower()],
                        knowledge_point_ids=[],
                        book_id=book['id'], book_section=band_sec, book_page=i + 1,
                        in_book_order=order, source_type='book',
                        question_image=('/figures/' + rel) if not dry_run else None,
                        figure_image=('/figures/' + figp[1]) if (figp and not dry_run) else None,
                        answer_image=None,
                        authored_by=authored,
                        _ai_fill=(not has_companion),
                    ))
                # Section in effect at the END of this page = last banner, else
                # keep carrying whatever was in effect (page-level section).
                if trans:
                    prev_section = trans[-1][1]
                elif section and section != 'Exercises':
                    prev_section = section
                prev_classified = True
                # carry the last emitted question so a spill-over page can stitch to it
                carry_order = out_paths[-1][0]
                carry_fp = out_paths[-1][2]
            elif kind == 'continuation' and carry_order is not None and not dry_run:
                # Body of the previous question spills onto this page (only sub-
                # part letters at the margin). Append it below that question's
                # image instead of starting a new question.
                ytop = first_left_letter_top(page, 0.20 * W)
                try:
                    stitch_continuation(carry_fp, page, ytop, W, H, dpi)
                except Exception as e:
                    sys.stderr.write(f"stitch fail {book['id']} p{i+1}: {e}\n")
                # prev_classified stays True; carry_order / carry_fp unchanged.
            else:
                carry_order = None
            page = None
            gc.collect()
    finally:
        pdf.close()
    return dict(book=dict(
        id=book['id'], subject=book['subject'], title=book['title'],
        publisher=book['publisher'], edition=book['edition'],
        has_answers=1 if book.get('has_answers') else 0,
        answer_source=book.get('answer_source'),
        cover_path=None, total_questions=len(questions),
        created_at=None,
    ), questions=questions)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--book', help='only this book id')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    targets = [b for b in BOOKS if (not args.book or b['id'] == args.book) and not b.get('scanned') and not b.get('skip_extract')]
    for book in targets:
        print(f"== {book['id']} ({book['title']}) ==", flush=True)
        res = extract_text_book_pdfium(book, dry_run=args.dry_run)
        if args.dry_run:
            print(f"   would extract {len(res['questions'])} questions")
            continue
        # Pre-fill empty answers/explanations so the importer's validateQuestion()
        # accepts every question. Pair-answers pass (if any) overwrites these.
        for q in res['questions']:
            if not q.get('answer'):
                q['answer'] = '[Answer pending — see source / companion material.]'
            if not q.get('explanation'):
                q['explanation'] = (
                    f'Extracted from {book["title"]}, page {q.get("book_page")}. '
                    'Answer will be supplemented from companion material.'
                )
            q.pop('_ai_fill', None)
        out = os.path.join(OUT_DIR, f"{book['id']}.json")
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        print(f"   extracted {len(res['questions'])} questions -> {out}")


if __name__ == '__main__':
    main()