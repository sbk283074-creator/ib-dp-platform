#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract concentrated exercise sets from SCANNED (no text-layer) IB workbooks
using OCR-based question-number detection.

Approach (validated on Tsokos 7ed WB):
  * Render each page at modest DPI.
  * easyocr detail=1 -> word boxes.
  * Question anchors = bare-integer tokens sitting in the left margin
    (x_center < LEFT_FRAC * page_width). In Tsokos these are consistently at
    ~22% width and spaced vertically — diagram labels / answer numbers live
    elsewhere on the page and are excluded by the margin filter.
  * Each pair of consecutive anchors defines a vertical band == one question.
    We crop that band directly in image (screen) coordinates with PIL.
  * We do NOT OCR every word verbatim (expensive); the image crop is the
    primary content. Question text is a source placeholder.

Output: per-book JSON consumable by POST /api/books/import (same schema as
extract_books.py text path).
"""
import os, re, json, gc, argparse, sys, logging, warnings
warnings.filterwarnings('ignore')
logging.getLogger('pdfminer').setLevel(logging.CRITICAL)
import pypdfium2 as pdfium
import numpy as np
import easyocr

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, 'book_json')
os.makedirs(OUT_DIR, exist_ok=True)

DP = "/Users/lucas.ma/Downloads/dp learning"

# left-margin fraction for question-number tokens
LEFT_FRAC = 0.25
DPI = 130
# min band height scales with DPI so it means ~2 text lines at any resolution
MIN_BAND_PX = int(DPI * 0.7)

# integer marker (optionally wrapped in parens), possibly followed by text
# e.g. "23", "23 Given that", "(a)", "a)"  — easyocr sometimes merges the
# leading number with the question prompt into one token.
INT_RE = re.compile(r'^\(?\d{1,3}\)?[.)]?\b')
LET_RE = re.compile(r'^\(?[a-e]\)?[.)]?\b')

# Lines near the top that indicate an answer / solution page -> skip entirely
ANSWER_RE = re.compile(r'^(answer|answers|solution|solutions|worked\s+solution)', re.I)


def build_reader():
    # limit torch/easyocr threads to reduce peak RAM (the environment is
    # memory-constrained: 4 node servers + easyocr)
    try:
        import torch
        torch.set_num_threads(2)
    except Exception:
        pass
    import os as _os
    _os.environ.setdefault('OMP_NUM_THREADS', '2')
    _os.environ.setdefault('MKL_NUM_THREADS', '2')
    return easyocr.Reader(['en'], gpu=False, verbose=False)


def page_ocr(arr, reader):
    """One OCR pass per page; return (H, W, res) where res is easyocr detail=1 output."""
    H, W = arr.shape[:2]
    res = reader.readtext(arr, detail=1, paragraph=False, batch_size=1)
    return H, W, res


def collect_markers(res, W, left_frac=0.25, top_zone=0.06, bot_zone=0.96):
    """From a detail=1 OCR result, pick question-start tokens.

    Robust rule: a question number is the LEFTMOST token on its text line
    AND an integer (1-3 digits), AND it sits in the left margin
    (lo_x/W <= left_frac), AND the same line carries follow-up text.

    Letter sub-part markers like '(a)', '(b)' are NEVER question starts
    (they always belong to the parent question and would over-split big
    questions into individual sub-parts). In-body numbers (equation indices,
    figure labels) are excluded by the left_frac margin discipline; the
    extract_scanned_book caller then runs a longest-ascending-run filter to
    drop remaining in-body sub-numbers.

    Running headers (top ~6%) and footers (bottom ~4%) are ignored.
    """
    H = None
    if res:
        H = max(max(pt[1] for pt in box) for box, _, _ in res)
    line_groups = {}
    for box, txt, conf in res:
        t = txt.strip()
        if not t:
            continue
        ys = [pt[1] for pt in box]; xs = [pt[0] for pt in box]
        key = round(min(ys) / 5) * 5
        line_groups.setdefault(key, []).append((min(xs), min(ys), max(ys), t))
    marks = []
    for key, items in line_groups.items():
        items.sort(key=lambda it: it[0])
        lo_x, y0, y1, t = items[0]
        if H and (y0 < top_zone * H or y0 > bot_zone * H):
            continue
        # NUMBER-ONLY: letter sub-parts are never question starts
        if not INT_RE.match(t):
            continue
        # LEFT-MARGIN discipline: in-body numbers (indented) are rejected
        if (lo_x / W) > left_frac:
            continue
        # reject a lone number with no question text anywhere on the line
        line_text = " ".join(it[3] for it in items)
        if not re.search(r'[A-Za-z]', line_text):
            continue
        tok = t.split()[0]
        m_num = re.match(r'^\(?(\d{1,3})\)?[.)]?', tok)
        if not m_num:
            continue
        marks.append((y0, y1, lo_x / W, int(m_num.group(1)), 1.0))
    marks.sort(key=lambda m: m[0])
    return marks


def _select_run(marks, max_step):
    """Longest-ascending-run selection for scanned question marks.
    Mirrors booklib._filter_monotonic: picks the longest strictly ascending
    run of integer numbers (step <= max_step), dropping earlier header noise
    and later in-body sub-numbers. Robust against a stray running-header
    number at the top poisoning the start of the sequence."""
    cands = sorted(marks, key=lambda m: m[0])
    n = len(cands)
    if n == 0:
        return cands
    nums = [m[3] for m in cands]
    run = [0] * n
    for i2 in range(n - 1, -1, -1):
        if i2 == n - 1:
            run[i2] = 1
        else:
            if nums[i2 + 1] > nums[i2] and (nums[i2 + 1] - nums[i2]) <= max_step:
                run[i2] = run[i2 + 1] + 1
            else:
                run[i2] = 1
    best_len = max(run)
    if best_len <= 1:
        return []  # no useful ascending run; force page rejection
    best = run.index(best_len)
    kept = [best]
    for i2 in range(best + 1, n):
        if nums[i2] > nums[kept[-1]] and (nums[i2] - nums[kept[-1]]) <= max_step:
            kept.append(i2)
        else:
            break
    return [cands[i2] for i2 in kept]


def is_toc_page_from_res(res, W):
    """TOC heuristic using an already-OCR'd result list."""
    right_page_nums = 0
    has_contents = False
    for box, txt, conf in res:
        t = txt.strip()
        xs = [pt[0] for pt in box]
        xc = (min(xs) + max(xs)) / 2.0
        if re.fullmatch(r'\d{2,3}', t) and (xc / W) > 0.75:
            right_page_nums += 1
        if t.lower() in ('contents', 'content'):
            has_contents = True
    return has_contents or right_page_nums >= 4



def is_answer_page(arr, reader, top_n_text=None):
    """Heuristic: skip pages that are pure answer keys."""
    # cheap: if very few markers, it's probably not an exercise page
    return False  # handled by caller via marker-count threshold


def extract_scanned_book(book, reader, dry_run=False, start=1, end=None,
                         order_offset=0, dpi=DPI, chunk_size=0):
    """Extract questions for pages [start..end].

    If chunk_size>0, a chunk JSONL file is flushed every `chunk_size` pages
    (crash-resilient; resume skips pages whose chunk file already exists).
    in_book_order is per-page (merge re-sorts by page anyway), so order_offset
    is ignored when chunk_size>0.
    """
    questions = []
    per_page_order = {}
    order = 0
    prev_section = book.get('default_section', 'Exercises')
    section = prev_section
    pdf = pdfium.PdfDocument(book['path'])
    n = len(pdf)
    end = min(end or n, n)
    page_questions = []   # buffer for the current chunk block
    block_start = start
    for pno in range(start, end + 1):
        # flush the previous 10-page block BEFORE processing this page, so
        # pages that `continue` (TOC / no markers / render error) can't
        # skip the flush. Runs at the first page of each new block.
        if chunk_size and pno > start and (pno - start) % chunk_size == 0:
            blk_start = pno - chunk_size
            ck = chunk_path(book['id'], blk_start)
            if not dry_run:
                with open(ck, 'w', encoding='utf-8') as f:
                    for qq in page_questions:
                        f.write(json.dumps(qq, ensure_ascii=False) + "\n")
            page_questions = []
            block_start = pno
        page = pdf[pno - 1]
        try:
            pil = page.render(scale=dpi / 72.0).to_pil()
            arr = np.asarray(pil)
            H, W, res = page_ocr(arr, reader)
            _cfg = book.get('seg') or {}
            marks = collect_markers(res, W, left_frac=_cfg.get('left_frac', 0.25))
        except Exception as e:
            sys.stderr.write(f"render/ocr fail {book['id']} p{pno}: {e}\n"); continue
        # skip TOC / front-matter pages
        try:
            if is_toc_page_from_res(res, W):
                arr = None; pil = None; res = None; gc.collect(); continue
        except Exception:
            pass
        # Per-book gating + longest-ascending-run filter for marks.
        cfg = book.get('seg') or {}
        min_markers = cfg.get('min_markers', 3)
        max_step = cfg.get('max_step', 2)
        crop_top_px = cfg.get('crop_top_px', 18)
        crop_bottom_px = cfg.get('crop_bottom_px', 28)
        min_band_px = cfg.get('min_band_px', MIN_BAND_PX)
        # LONGEST ascending run: drops header noise + in-body sub-numbers.
        marks = _select_run(marks, max_step)
        # require enough left-margin numeric markers (exercise-page gate)
        if len(marks) < min_markers:
            arr = None; pil = None; res = None; gc.collect(); continue
        # optional: capture a heading (first OCR line) for section label
        try:
            # reuse the detail=1 result: group tokens by line (y), take the
            # topmost line whose joined text looks like a heading.
            line_groups = {}
            for box, txt, conf in res:
                ys = [pt[1] for pt in box]
                key = round(min(ys) / 6) * 6
                line_groups.setdefault(key, []).append((min(pt[0] for pt in box), txt))
            for k in sorted(line_groups.keys())[:6]:
                line = " ".join(t for _, t in sorted(line_groups[k])).strip()
                if re.match(r'^(topic|chapter|section|unit|\d+\.\d+)', line, re.I) \
                        and len(line) < 60 and not INT_RE.match(line):
                    section = line[:60]; break
        except Exception:
            pass
        # build bands in image coords. A real question occupies several text
        # lines; drop spurious markers (diagram labels, lone answer numbers)
        # whose band would be too short to be a question.
        bands = []
        for i, m in enumerate(marks):
            y0 = max(0, int(m[0]) - 10 - crop_top_px)
            nxt = int(marks[i + 1][0]) if i + 1 < len(marks) else H
            y1 = min(nxt, nxt - 4 + crop_bottom_px)
            y1 = min(H, max(y1, y0 + 20))
            if (y1 - y0) < min_band_px:
                continue
            bands.append((m[3], y0, y1))
        # crop + emit
        for tok, y0, y1 in bands:
            order += 1
            per_page_order[pno] = per_page_order.get(pno, 0) + 1
            pp_order = per_page_order[pno]
            rel, fp = save_crop_relname(book['id'], 'q', pno, pp_order)
            if not dry_run:
                try:
                    crop = pil.crop((0, y0, W, y1))
                    crop.save(fp, 'JPEG', quality=86)
                except Exception as e:
                    sys.stderr.write(f"crop fail {book['id']} p{pno}: {e}\n")
            # Scanned workbooks: the companion answer file (if any) uses a
            # DIFFERENT numbering scheme than the workbook's running problem
            # numbers, so reliable auto-pairing is not possible. Per the user
            # rule, leave answers AI-pending and clearly mark them as such.
            q = dict(
                id=f"{book['id']}-Q{order}",
                subject=book['subject'], level=book['level'], topic=section,
                subtopic=None, paper_type=None, command_term=None,
                marks=None, difficulty=None,
                question=f"[See question image. Source: {book['title']}, page {pno}.]",
                answer='[Answer pending — to be supplemented (AI-generated).]',
                explanation=('Extracted from scanned workbook; answer key uses a '
                             'different numbering scheme and could not be auto-matched. '
                             'Answer to be supplemented (AI-generated).'),
                source=f"{book['title']} · p{pno}",
                tags=['book', book['publisher'].lower(), 'scanned'],
                knowledge_point_ids=[],
                book_id=book['id'], book_section=section, book_page=pno,
                in_book_order=pp_order, source_type='book',
                question_image=('/figures/' + rel) if not dry_run else None,
                answer_image=None,
                authored_by='import',
            )
            questions.append(q)
            page_questions.append(q)
        # free per-page buffers aggressively to keep RAM bounded
        arr = None; pil = None; res = None; marks = None; gc.collect()
    # final flush for the tail block (always write the file, even if empty, so
    # resume treats the block as done)
    if chunk_size and end >= start:
        ck = chunk_path(book['id'], block_start)
        if not dry_run:
            with open(ck, 'w', encoding='utf-8') as f:
                for qq in page_questions:
                    f.write(json.dumps(qq, ensure_ascii=False) + "\n")
    pdf.close()
    return dict(book=dict(
        id=book['id'], subject=book['subject'], title=book['title'],
        publisher=book['publisher'], edition=book['edition'],
        has_answers=1 if book.get('has_answers') else 0,
        answer_source=book.get('answer_source'),
        cover_path=None, total_questions=len(questions), created_at=None,
    ), questions=questions)


def save_crop_relname(book_id, kind, page, idx):
    from booklib import FIG_DIR
    fname = f"book_{book_id}_{kind}_p{page}_{idx}.jpg"
    return fname, os.path.join(FIG_DIR, fname)


# ---- scanned book registry (subset of extract_books.BOOKS with scanned=True)
SCANNED_BOOKS = [
    dict(id='PH-TSOKOS-WB', subject='Physics', level='HL',
         title='Tsokos Physics Workbook (7ed)',
         publisher='Cambridge', edition='Tsokos 7ed',
         path=f'{DP}/Tsokos 7th edition Workbok.pdf',
         answer_path=f'{DP}/Tsokos 7th edition Workbook ANSWERS.pdf',
         has_answers=True, answer_source='Tsokos Workbook ANSWERS',
         default_section='Problems',
         seg=dict(left_frac=0.22, min_markers=4, max_step=2, crop_top_px=20, crop_bottom_px=30),
    ),
    dict(id='PH-CAMB-WB', subject='Physics', level='HL',
         title='Cambridge Physics Workbook (7ed)',
         publisher='Cambridge', edition='Tsokos 7ed',
         path=f'{DP}/Physics-HLSL-Cambridge-Workbook(First exam 2025)/Physics - WORKBOOK - K.A. Tsokos - Seventh Edition - Cambridge 2023（扫描版）.pdf',
         answer_path=f'{DP}/Physics-HLSL-Cambridge-Textbook Answers(First exam 2025)/Coursebook answers.pdf',
         has_answers=True, answer_source='Cambridge Coursebook answers',
         default_section='Exercises',
         seg=dict(left_frac=0.22, min_markers=4, max_step=2, crop_top_px=20, crop_bottom_px=30),
    ),
    dict(id='MA-HODDER-WB', subject='Math AA HL', level='HL',
         title='Math AA HL Exam Practice Workbook (Hodder 2021)',
         publisher='Hodder', edition='Fannon, Kadelburg & Ward 2021',
         path=f'{DP}/HL Workbook/Mathematics - Analysis and Approaches HL - Exam Practice Workbook - Hodder 2021.pdf',
         answer_path=f'{DP}/HL Workbook/Mathematics - Analysis and Approaches HL - Exam Practice Workbook - ANSWERS - Hodder 2021.pdf',
         has_answers=True, answer_source='Hodder ANSWERS 2021',
         default_section='Practice',
         seg=dict(left_frac=0.20, min_markers=3, max_step=2, crop_top_px=25, crop_bottom_px=35),
    ),
]


def find_book(bid):
    return next((b for b in SCANNED_BOOKS if b['id'] == bid), None)


def chunk_path(book_id, start):
    return os.path.join(OUT_DIR, f"_chunk_{book_id}_{start:05d}.jsonl")


def merge_chunks(book_id):
    """Combine all per-chunk JSONL files for a book into book_json/{id}.json
    with a globally renumbered in_book_order."""
    reg = find_book(book_id)
    files = sorted(
        f for f in os.listdir(OUT_DIR)
        if f.startswith(f"_chunk_{book_id}_") and f.endswith('.jsonl')
    )
    questions = []
    for fn in files:
        with open(os.path.join(OUT_DIR, fn), 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    questions.append(json.loads(line))
    # sort by (book_page, in_book_order) then renumber order globally
    questions.sort(key=lambda q: (q['book_page'], q['in_book_order']))
    for i, q in enumerate(questions, 1):
        q['in_book_order'] = i
        q['id'] = f"{book_id}-Q{i}"
    book_meta = dict(
        id=book_id, subject=reg['subject'], title=reg['title'],
        publisher=reg['publisher'], edition=reg['edition'],
        has_answers=1 if reg.get('has_answers') else 0,
        answer_source=reg.get('answer_source'),
        cover_path=None, total_questions=len(questions), created_at=None,
    )
    out = os.path.join(OUT_DIR, f"{book_id}.json")
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(dict(book=book_meta, questions=questions),
                  f, ensure_ascii=False, indent=1)
    # NOTE: chunk files are intentionally KEPT so a later `--merge` after more
    # chunks are added re-reads everything (idempotent). Delete manually.
    print(f"   merged {len(questions)} questions -> {out}", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--book', help='only this book id')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--start', type=int, default=1)
    ap.add_argument('--end', type=int, default=None)
    ap.add_argument('--order-offset', type=int, default=0)
    ap.add_argument('--dpi', type=int, default=DPI, help='render DPI (lower = less RAM)')
    ap.add_argument('--sweep', nargs=2, type=int, metavar=('START', 'END'),
                    help='one model load over START..END, flushing 10-page chunks')
    ap.add_argument('--merge', metavar='BOOKID',
                    help='merge all chunk files for BOOKID into final json')
    args = ap.parse_args()
    if args.merge:
        merge_chunks(args.merge); return
    targets = [b for b in SCANNED_BOOKS if (not args.book or b['id'] == args.book)]
    reader = build_reader()
    for book in targets:
        print(f"== {book['id']} ({book['title']}) ==", flush=True)
        if args.sweep:
            res = extract_scanned_book(book, reader, dry_run=args.dry_run,
                                       start=args.sweep[0], end=args.sweep[1],
                                       dpi=args.dpi, chunk_size=10)
            print(f"   sweep pages {args.sweep[0]}..{args.sweep[1]}: "
                  f"{len(res['questions'])} questions (chunks flushed)", flush=True)
            continue
        ck = chunk_path(book['id'], args.start)
        if os.path.exists(ck) and not args.dry_run:
            print(f"   skip (already done): {ck}", flush=True)
            continue
        res = extract_scanned_book(book, reader, dry_run=args.dry_run,
                                  start=args.start, end=args.end,
                                  order_offset=args.order_offset, dpi=args.dpi)
        if args.dry_run:
            print(f"   would extract {len(res['questions'])} questions "
                  f"(pages {args.start}..{args.end or 'end'})", flush=True)
            continue
        ck = chunk_path(book['id'], args.start)
        with open(ck, 'w', encoding='utf-8') as f:
            for q in res['questions']:
                if not q.get('answer'):
                    q['answer'] = '[Answer pending — see companion material / will be AI-generated.]'
                f.write(json.dumps(q, ensure_ascii=False) + "\n")
        print(f"   chunk pages {args.start}..{args.end or 'end'}: "
              f"{len(res['questions'])} questions -> {ck}", flush=True)


if __name__ == '__main__':
    main()
