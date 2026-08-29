#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
screenshot_questions.py — render each NUMBER-LED question to its own image.

USER RULES (enforced here):
  * A question starts with a NUMBER  (1. 2. 3.).
  * A question that starts with a LETTER (a) b) a.) is a SUBQUESTION, NOT a
    question — it belongs to the enclosing number-led question.  Letter-led
    items are never promoted to their own question row.
  * Exactly ONE full question per question area:
      - two questions are never merged into one crop,
      - a question is never split across two database rows,
      - a sub-question from one question is NEVER placed into another question's
        area (no sub-part leakage).
  * DIFFERENT file structures use DIFFERENT detection strategies:
      - "number" : number-led anchors (most past papers / exercise banks).
      - "line"   : questions are separated ONLY by full-width horizontal lines
                   and carry NO leading number in the text (e.g. Physics HL
                   Topic multiple-choice papers). We segment by those lines and
                   number the regions sequentially.
  * Every question keeps its OWN figure/diagram: the crop band is expanded to
    include any embedded image whose centre falls inside the question region.
  * A question that continues / "turns over" onto the next page is stitched
    across the involved pages so nothing is lost.

HOW IT WORKS:
  1. pdfplumber finds top-level number anchors (a bare integer "N." / "N)" at
     the left margin, not a decimal, not a two-level heading). For "line"
     strategy it instead finds full-width horizontal separator rules.
  2. Each question occupies the vertical band from its start down to the next
     start (or the page/section end), trimmed at any separator line so a later
     question (or its sub-parts) can never bleed in. Cross-page bands are
     stitched.
  3. pypdfium2 renders each band; PIL stitches them into one PNG per question.
  4. A JSONL manifest records every question (id, number, page span, subpart
     count, image path) so the import step can build a 1:1 database mapping.

MODES:
  --dry-run   detection only. Prints per-file question counts + numbers.
  default     renders crops + writes manifest (resumable via checkpoint).

USAGE:
  python3 screenshot_questions.py <pdf> --profile physics_topic \
      --prefix PHY-TOPIC1-P1 [--dry-run] [--dpi 200] [--limit 5] \
      [--markscheme <ms.pdf>] [--out <dir>]
"""
import argparse, json, os, re, sys
from collections import defaultdict

import pdfplumber
import pypdfium2 as pdfium
from PIL import Image

# ----------------------------------------------------------------- config
ROOT = "/Users/lucas.ma/Downloads/dp learning"
SHOTS_DIR = os.path.join(ROOT, "ib-dp-platform", "backend", "public", "figures", "shots")
MANIFEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshot_manifest.jsonl")
CKPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshot_ckpt.json")

# Top-level question anchor: a bare integer at the line start, followed by "."
# or ")" — but the character AFTER the dot must NOT be a digit (excludes
# decimals like "1.2" and two-level headings like "1.1 Kinematics").
ANCHOR_RE = re.compile(r"^(\d{1,3})[.)]")

# Subquestion markers (letter-led) — used only to COUNT subparts; never anchors.
SUBPART_RE = re.compile(r"^\(?[a-z]\)?\.?(\s|$)")

# Lines that are page furniture (headers/footers), not question content.
HEADER_RE = re.compile(
    r"^(HL|IB|Paper|Name|Date|Candidate|Page|Turn over|Total|Maximum|"
    r"For examiner|This document|Read these|Instructions|–\s*\d|\.\s*\d)$", re.I)

PROFILES = {
    # Recent IB past papers: single column, numbers at left margin, sequential.
    "math_past":      dict(columns=1, strategy="number", left_margin=True, max_qnum=60, expect_sequence=True),
    "physics_past":   dict(columns=1, strategy="number", left_margin=True, max_qnum=60, expect_sequence=True),
    "cs_past":        dict(columns=1, strategy="number", left_margin=True, max_qnum=60, expect_sequence=True),
    # Topic / classified exercise sets: single column, numbers at left margin,
    # but counts can be large and numbering may restart per section.
    "topic_exercise": dict(columns=1, strategy="number", left_margin=True, max_qnum=300, expect_sequence=False),
    # Older two-column past papers: detect the column gap, process each column.
    "two_column":     dict(columns=2, strategy="number", left_margin=True, max_qnum=60, expect_sequence=True),
    # Line-preferred, number-fallback. Used for PDFs whose questions are
    # separated by full-width horizontal rules and carry NO leading number in
    # the text (e.g. Physics HL Topic multiple-choice sets, and IB Question-Bank
    # chapter-exercise sets). Segments by those rules and numbers regions
    # sequentially; adaptively falls back to number anchors per page if a page
    # has no separators but does have numbers, and to a whole-page region as a
    # last resort.
    "line_pref":      dict(columns=1, strategy="line",   left_margin=True, max_qnum=300, expect_sequence=False),
}

MARGIN_TOL = 46.0   # pt tolerance for "at the left margin"
COL_GAP_MIN = 36.0  # pt minimum vertical whitespace gap that signals two columns
SEP_MIN_FRAC = 0.5  # a separator rule must span at least this fraction of page width


# ----------------------------------------------------------------- helpers
def load_ckpt():
    if os.path.exists(CKPT):
        try:
            return json.load(open(CKPT))
        except Exception:
            pass
    return {"done": []}


def save_ckpt(ck):
    tmp = CKPT + ".tmp"
    json.dump(ck, open(tmp, "w"))
    os.replace(tmp, CKPT)


def page_text_left(page):
    """Approximate left text edge of a page (min x0 over words)."""
    words = page.extract_words()
    if not words:
        return 0.0
    return min(w["x0"] for w in words)


def detect_columns(page, profile):
    """Return list of (x0, x1) column ranges for a page."""
    if profile["columns"] < 2:
        return [(0.0, float(page.width))]
    words = page.extract_words()
    if not words:
        return [(0.0, float(page.width))]
    edges = [(w["x0"], w["x1"]) for w in words]
    W = float(page.width)
    step = 4.0
    candidates = []
    x = step
    while x < W - step:
        covered = any(ex0 - 2 <= x <= ex1 + 2 for ex0, ex1 in edges)
        if not covered:
            candidates.append(x)
        x += step
    spans = []
    for gx in candidates:
        if spans and gx - spans[-1][1] <= step + 1:
            spans[-1] = (spans[-1][0], gx)
        else:
            spans.append((gx, gx))
    good = [s for s in spans if (s[1] - s[0]) >= COL_GAP_MIN]
    if not good:
        return [(0.0, W)]
    centre = W / 2
    good.sort(key=lambda s: abs((s[0] + s[1]) / 2 - centre))
    g0, g1 = good[0]
    return [(0.0, g0), (g1, W)]


def line_groups(page):
    """Group words on a page into lines: list of (top, x0, text)."""
    words = page.extract_words()
    by_top = defaultdict(list)
    for w in words:
        by_top[round(w["top"])].append(w)
    lines = []
    for top in sorted(by_top):
        ws = sorted(by_top[top], key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in ws)
        x0 = ws[0]["x0"] if ws else 0.0
        lines.append((top, x0, text))
    return lines


def detect_separators(page, profile):
    """Return deduplicated list of y-positions of full-width horizontal rules."""
    W = page.width
    min_w = SEP_MIN_FRAC * W
    seps = []
    for r in getattr(page, "rects", []):
        if abs(r["height"]) < 5 and (r["x1"] - r["x0"]) >= min_w:
            seps.append(r["top"])
    for l in getattr(page, "lines", []):
        if abs(l["top"] - l["bottom"]) < 3 and (l["x1"] - l["x0"]) >= min_w:
            seps.append(l["top"])
    seps = sorted(set(round(s, 1) for s in seps))
    dedup = []
    for s in seps:
        if not dedup or s - dedup[-1] > 3:
            dedup.append(s)
    return dedup


def _is_furniture(text, top, H):
    """True if a line is a header/footer, not question content."""
    s = text.strip()
    if not s:
        return True
    if HEADER_RE.match(s) and len(s.split()) <= 10:
        return True
    # lone page number near the bottom of the page
    if re.fullmatch(r"\d{1,3}", s) and top > H * 0.9:
        return True
    return False


def content_bounds(page, t0, t1):
    """Trim (t0,t1) to the first/last real content line in range.

    Excludes header/footer furniture so a question crop never starts with the
    running header or ends with the page number. If the range has no content,
    the original bounds are returned.
    """
    H = page.height
    first = None
    last_top = None
    for top, _x0, text in line_groups(page):
        if top < t0 - 1 or top > t1 + 1:
            continue
        if _is_furniture(text, top, H):
            continue
        if first is None:
            first = top
        last_top = top
    if first is None:
        return (t0, t1)
    # precise bottom: lowest word bottom near last_top
    last_bottom = t1
    for w in page.extract_words():
        if abs(w["top"] - last_top) < 4:
            last_bottom = max(last_bottom, w["bottom"])
    return (first, last_bottom)


def find_anchors(page, profile, col_range=None):
    """Return list of (top, x0, number) for top-level question anchors."""
    left = page_text_left(page)
    H = page.height
    anchors = []
    for top, x0, text in line_groups(page):
        if col_range and not (col_range[0] - 2 <= x0 <= col_range[1] + 2):
            continue
        if profile["left_margin"] and x0 > left + MARGIN_TOL:
            continue
        m = ANCHOR_RE.match(text.strip())
        if not m:
            continue
        num = int(m.group(1))
        after = text.strip()[m.end():]
        if after and after[0].isdigit():
            continue  # decimal / two-level heading
        if num == 0 or num > profile["max_qnum"]:
            continue
        # reject a lone page-number-like digit at the very bottom of the page
        if re.fullmatch(r"\d{1,3}", text.strip()) and top > H * 0.88:
            continue
        anchors.append((top, x0, num))
    return anchors


def expand_for_figures(page, t0, t1):
    """Expand the band to include any embedded image whose centre lies inside
    the band (so a question's diagram is never left out). Returns (t0, t1)."""
    if not getattr(page, "images", []):
        return (t0, t1)
    nt0, nt1 = t0, t1
    for im in page.images:
        c = (im["top"] + im["bottom"]) / 2.0
        # figure belongs to this question if its centre is within the band
        if t0 - 30 <= c <= t1 + 30:
            nt0 = min(nt0, im["top"])
            nt1 = max(nt1, im["bottom"])
    return (nt0, nt1)


# ----------------------------------------------------------------- render
def render_band(pdf, page_idx, top0, top1, scale, xr=None):
    """Render the horizontal band [top0, top1] (points, from top) of one page."""
    page = pdf.get_page(page_idx)
    Wpt, Hpt = page.get_size()
    pil = page.render(scale=scale).to_pil().convert("RGB")
    Wpx, Hpx = pil.size
    y0 = max(0, int(top0 * scale))
    y1 = min(Hpx, int(top1 * scale))
    if y1 <= y0:
        y1 = y0 + 1
    if xr:
        x0 = max(0, int(xr[0] * scale))
        x1 = min(Wpx, int(xr[1] * scale))
        if x1 <= x0:
            x1 = x0 + 1
        return pil.crop((x0, y0, x1, y1))
    return pil.crop((0, y0, Wpx, y1))


def stitch(images):
    if not images:
        return None
    W = max(im.width for im in images)
    H = sum(im.height for im in images)
    out = Image.new("RGB", (W, H), (255, 255, 255))
    y = 0
    for im in images:
        out.paste(im, (0, y))
        y += im.height
    return out


# ----------------------------------------------------------------- regions
def build_regions(plumb, anchors_by_page_col, profile):
    """Yield (number, [ (page_idx, top0, top1, xr) ... ]) question regions.

    Two strategies:
      "number": each anchor starts a region; region ends at the next anchor OR
                the next separator line (whichever is nearer) so a following
                question can never bleed in.
      "line"  : regions are the gaps between full-width separator rules,
                numbered sequentially; falls back to number anchors if no
                separator lines exist on any page.
    """
    strategy = profile["strategy"]

    # ---- line strategy (decided PER PAGE; see _regions_for_page) -----------
    if strategy == "line":
        npages = len(plumb.pages)
        out = defaultdict(list)
        for pi in range(npages):
            for (t0, t1) in _regions_for_page(plumb.pages[pi], profile):
                out[pi].append((t0, t1))
        for pi in out:
            out[pi].sort()
        # Drop the page-header band and page-footer band on the VERY FIRST page
        # when they are clearly not real questions (sit at the page edge and are
        # short). Only acts when the page has more than one band, so a lone
        # whole-page question on a single-page or continuation page is never
        # deleted. This keeps "one question per area" honest: the "HL Paper 1"
        # header and the trailing page-number sliver are not questions.
        if 0 in out and len(out[0]) > 1:
            H0 = plumb.pages[0].height
            if out[0] and out[0][0][0] <= 0.5 and (out[0][0][1] - out[0][0][0]) < 90:
                out[0].pop(0)
            if out[0] and out[0][-1][1] >= H0 - 1 and (out[0][-1][1] - out[0][-1][0]) < 90:
                out[0].pop()
        num = 0
        for pi in range(npages):
            for (t0, t1) in out.get(pi, []):
                num += 1
                yield num, [(pi, t0, t1, None)]
        return

    # ---- number strategy ------------------------------------------------
    flat = []
    for page_idx, col_range, anchors in anchors_by_page_col:
        for top, x0, num in sorted(anchors, key=lambda a: a[0]):
            flat.append((page_idx, col_range, top, num))
    flat.sort(key=lambda t: (t[0], t[1][0] if t[1] else 0, t[2]))

    # precompute separator lines per (page, col)
    sep_map = {}
    for pi in range(len(plumb.pages)):
        for col in (detect_columns(plumb.pages[pi], profile) if profile["columns"] >= 2 else [None]):
            sep_map[(pi, col)] = detect_separators(plumb.pages[pi], profile)

    npages = len(plumb.pages)
    for i, (page_idx, col_range, top, num) in enumerate(flat):
        # nearest following anchor in the same column stream
        nxt = None
        for j in range(i + 1, len(flat)):
            if flat[j][1] == col_range:
                nxt = flat[j]
                break
        # nearest separator line below this anchor (same page, same column)
        seps = sep_map.get((page_idx, col_range), [])
        below = [s for s in seps if s > top + 4]
        sep_end = min(below) if below else None

        spans = []
        if nxt is None:
            H = plumb.pages[page_idx].height
            spans.append((page_idx, top, H, col_range))
            for p in range(page_idx + 1, npages):
                spans.append((p, 0.0, plumb.pages[p].height, col_range))
        elif nxt[0] == page_idx:
            end = nxt[2] - 2.0
            if sep_end is not None:
                end = min(end, sep_end - 1.0)  # never cross into next question
            spans.append((page_idx, top, max(top + 1, end), col_range))
        else:
            H = plumb.pages[page_idx].height
            end = H
            if sep_end is not None:
                end = min(end, sep_end - 1.0)
            spans.append((page_idx, top, end, col_range))
            for p in range(page_idx + 1, nxt[0]):
                spans.append((p, 0.0, plumb.pages[p].height, col_range))
            spans.append((nxt[0], 0.0, max(0.0, nxt[2] - 2.0), col_range))
        yield num, spans


def _segment_by_numbers(page, profile, anchors, H):
    """Segment ONE page by number anchors, trimmed at a separator line below."""
    anchors = sorted(anchors, key=lambda a: a[0])
    seps = detect_separators(page, profile)
    regions = []
    for i, (top, x0, num) in enumerate(anchors):
        end = anchors[i + 1][0] - 2.0 if i + 1 < len(anchors) else H
        below = [s for s in seps if s > top + 4]
        if below:
            end = min(end, below[0] - 1.0)  # never cross into next question
        cb = content_bounds(page, top, end)
        regions.append((cb[0], cb[1]))
    return regions


def _regions_for_page(page, profile):
    """Return list of (t0, t1) regions for ONE page, by best available method.

    Priority:
      1. If the page carries full-width separator rules, segment by them
         (Physics HL Topic multiple-choice style). This is the intended mode.
      2. Guard: if rule-segmentation collapses to a single full-page region but
         the page actually holds several number-led questions, use numbers.
      3. Else if number anchors exist, segment by numbers.
      4. Else treat the whole (trimmed) page as one region.
    Deciding per page — not globally — avoids one stray rule forcing the whole
    file into line-mode and merging a number-led page into one crop.
    """
    H = page.height
    seps = detect_separators(page, profile)
    if seps:
        bounds = [0.0] + list(seps) + [H]
        regions = []
        for i in range(len(bounds) - 1):
            t0, t1 = bounds[i], bounds[i + 1]
            if t1 - t0 < 14:
                continue
            cb = content_bounds(page, t0, t1)
            if cb[1] - cb[0] < 14:
                continue
            regions.append((cb[0], cb[1]))
        if regions:
            anchors = find_anchors(page, profile, None)
            if len(regions) <= 1 and len(anchors) >= 2:
                return _segment_by_numbers(page, profile, anchors, H)
            return regions
    anchors = find_anchors(page, profile, None)
    if anchors:
        return _segment_by_numbers(page, profile, anchors, H)
    cb = content_bounds(page, 0.0, H)
    return [(cb[0], cb[1])]


# ----------------------------------------------------------------- process
def count_subparts(plumb, spans, profile):
    """Count letter-led subquestions inside a question's band (for metadata)."""
    count = 0
    for page_idx, top0, top1, _xr in spans:
        page = plumb.pages[page_idx]
        for top, _x0, text in line_groups(page):
            if top < top0 - 1 or top > top1 + 1:
                continue
            if SUBPART_RE.match(text.strip()):
                count += 1
    return count


def process_file(pdf_path, profile_name, prefix, out_dir, dpi, limit, dry_run, ms_path=None):
    profile = PROFILES[profile_name]
    scale = dpi / 72.0
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    file_out = os.path.join(out_dir, prefix or base)
    os.makedirs(file_out, exist_ok=True)

    with pdfplumber.open(pdf_path) as plumb:
        npages = len(plumb.pages)
        anchors_by_page_col = []
        for pi in range(npages):
            cols = detect_columns(plumb.pages[pi], profile)
            for col in cols:
                a = find_anchors(plumb.pages[pi], profile, col if profile["columns"] >= 2 else None)
                if a:
                    anchors_by_page_col.append((pi, col if profile["columns"] >= 2 else None, a))

        questions = list(build_regions(plumb, anchors_by_page_col, profile))
        if not questions:
            print(f"  [warn] {os.path.basename(pdf_path)}: 0 questions detected ({profile_name})", file=sys.stderr)

        if dry_run:
            nums = [num for num, _ in questions]
            print(f"  [dry] {os.path.basename(pdf_path)} ({profile_name}): {len(questions)} questions"
                  f"  numbers={nums[:30]}{'...' if len(nums) > 30 else ''}")
            return len(questions), nums

        pdf = pdfium.PdfDocument(pdf_path)
        written = 0
        for num, spans in questions:
            if limit and written >= limit:
                break
            qid = f"{prefix or base}-q{num:02d}"
            rel = f"/figures/shots/{os.path.basename(file_out)}/{qid}.png"
            abspath = os.path.join(file_out, f"{qid}.png")
            if os.path.exists(abspath):
                written += 1
                continue
            # trim to content + include attached figures per page-span
            trimmed = []
            for (p, t0, t1, xr) in spans:
                pg = plumb.pages[p]
                cb = content_bounds(pg, t0, t1)
                # only expand/trim partial page spans (full pages keep as-is)
                if t0 > 0.5 or t1 < pg.height - 0.5:
                    nt0, nt1 = expand_for_figures(pg, cb[0], cb[1])
                    # Rule #3 (figures win): expand_for_figures only triggers
                    # when an image sits in/near the band, so nt1 > t1 ONLY
                    # when a figure is present.  Keep the full figure bottom —
                    # the old clamp cut diagrams (e.g. Math 2024 May P2 Q4 v-t
                    # graph reported "missing part of the diagram").  A small
                    # leak of the next question's top is the accepted tradeoff
                    # so every question keeps its own figure.
                else:
                    nt0, nt1 = cb[0], cb[1]
                trimmed.append((p, nt0, nt1, xr))
            bands = [render_band(pdf, p, t0, t1, scale, xr) for (p, t0, t1, xr) in trimmed]
            img = stitch([b for b in bands if b is not None])
            if img is None:
                continue
            img.save(abspath, quality=90)
            subparts = count_subparts(plumb, trimmed, profile)
            rec = {
                "id": qid, "prefix": prefix, "source": os.path.relpath(pdf_path, ROOT),
                "profile": profile_name, "number": num,
                "pages": sorted({p for (p, *_ ) in trimmed}),
                "subparts": subparts, "image": rel, "type": "question",
            }
            if ms_path:
                rec["answer_image"] = screenshot_answer(ms_path, num, profile, file_out, qid, dpi)
            with open(MANIFEST, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1
        pdf.close()
    return written, [num for num, _ in questions]


def screenshot_answer(ms_path, num, profile, file_out, qid, dpi):
    """Find the matching answer band in the markscheme and screenshot it."""
    scale = dpi / 72.0
    try:
        with pdfplumber.open(ms_path) as pdf:
            target = None
            for pi in range(len(pdf.pages)):
                a = find_anchors(pdf.pages[pi], profile, None)
                for top, _x0, n in a:
                    if n == num:
                        target = (pi, top)
                        break
                if target:
                    break
            if not target:
                return None
            pi, top = target
            nxt_top = float(pdf.pages[pi].height)
            for p2 in range(pi, len(pdf.pages)):
                a = find_anchors(pdf.pages[p2], profile, None)
                for t, _x0, n in a:
                    if p2 == pi and t > top:
                        nxt_top = t
                        break
                if nxt_top != float(pdf.pages[pi].height):
                    break
            pdf2 = pdfium.PdfDocument(ms_path)
            band = render_band(pdf2, pi, top, nxt_top, scale, None)
            pdf2.close()
            arel = f"/figures/shots/{os.path.basename(file_out)}/{qid}-ans.png"
            abspath = os.path.join(file_out, f"{qid}-ans.png")
            band.save(abspath, quality=90)
            return arel
    except Exception as e:
        print(f"    [warn] answer shot failed for {qid}: {e}", file=sys.stderr)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", help="source PDF (question paper / exercise PDF)")
    ap.add_argument("--profile", required=True, choices=list(PROFILES))
    ap.add_argument("--prefix", default=None, help="stable id prefix, e.g. MATH-2024.5-P2-TZ1")
    ap.add_argument("--markscheme", default=None, help="paired markscheme PDF for answer images")
    ap.add_argument("--out", default=SHOTS_DIR)
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--limit", type=int, default=0, help="max questions to render (pilot)")
    ap.add_argument("--dry-run", action="store_true", help="detection only, no rendering")
    args = ap.parse_args()

    if not os.path.exists(args.pdf):
        print(f"ERROR: {args.pdf} not found", file=sys.stderr)
        sys.exit(1)

    ck = load_ckpt() if not args.dry_run else {"done": []}
    key = f"{args.prefix or ''}|{os.path.relpath(args.pdf, ROOT)}"
    if not args.dry_run and key in ck.get("done", []):
        print(f"  [skip] already processed {key}")
        return

    n, nums = process_file(args.pdf, args.profile, args.prefix, args.out,
                           args.dpi, args.limit, args.dry_run, args.markscheme)
    if args.dry_run:
        print(f"  detected {n} questions (dry-run, nothing rendered)")
        return
    ck.setdefault("done", []).append(key)
    save_ckpt(ck)
    print(f"  rendered {n} questions  -> {os.path.join(args.out, args.prefix or os.path.splitext(os.path.basename(args.pdf))[0])}")


if __name__ == "__main__":
    main()
