#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crop per-question FIGURES for the scanned CS book, using the bounding boxes from
ocr_boxes.jsonl (re-OCR with detail=1).

Why a different approach than crop_figures.py:
  The CS source is a SCANNED pdf (one raster per page) -> pdfplumber finds no
  vector figure objects. So instead we render each page and treat any "ink" that
  is NOT covered by OCR text lines as a figure, then associate each figure to
  the question/markscheme block it falls inside.

Pipeline:
  - load ocr_boxes.jsonl (page -> [lines{bbox(points), text}])
  - detect markscheme-start page (a line == "Markschemes")
  - for each page, split into blocks by the IB code lines; each block owns the
    question id of its starting code (carried across pages when a question spans)
  - render page, build a text mask from OCR line bboxes, find figure-ink blobs
    outside the mask, crop+save JPEGs, link to figure/answer_figure
  - CS only. Resumable via crop_cs_checkpoint.json.
Usage:
  python3 crop_cs_figures.py
"""
import json, os, re, sqlite3, sys
import numpy as np
import pypdfium2 as pdfium
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BOXES = os.path.join(HERE, "ocr_boxes.jsonl")
FIG_DIR = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/public/figures"
DB_PATH = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/data/app.db"
PDF = "/Users/lucas.ma/Downloads/dp learning/IB 计算机分类真题.pdf"
CKPT = os.path.join(HERE, "crop_cs_checkpoint.json")

CROP_SCALE = 2.2
PAD = 10
TEXT_PAD = 5
# A real figure is a sizeable ink region that is NOT a thin text-like strip.
# Filter by pixel area and aspect (strip = very wide & short, or very tall & narrow).
MIN_AREA = 5000          # min ink pixels
MIN_W, MIN_H = 25, 22    # min raw box size (points) to avoid specks
MAX_STRIP_RATIO = 6.0    # if width/height >= this, treat as a text strip -> drop
GAP = 10

CODE = re.compile(r"(?<!\d)(\d{2}[MN])\s*\.\s*(\d+)\s*\.\s*([SH]L)\s*\.\s*TZ\s*[O0]?\s*(\d*)\.\s*(\d+)")

os.makedirs(FIG_DIR, exist_ok=True)


def norm_key(s):
    return re.sub(r"[^A-Za-z0-9]", "", s.replace("O", "0").upper())


def load_boxes():
    pages = {}
    if not os.path.exists(BOXES):
        return pages
    with open(BOXES, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            pages[r["page"]] = r["lines"]
    return pages


def find_ms_start(pages):
    for pno in sorted(pages):
        for ln in pages[pno]:
            t = (ln.get("text") or "").strip()
            if t.lower().startswith("markscheme"):
                return pno
    return 224


def detect_figure_blobs(gray, textmask, y0, y1):
    """Within band [y0,y1] (render px), return list of (x0,x1,y0,y1) figure boxes."""
    H, W = gray.shape
    ink = gray < 128
    band0, band1 = max(0, int(y0)), min(H, int(y1))
    if band1 <= band0:
        return []
    sub_ink = ink[band0:band1, :] & (~textmask[band0:band1, :])
    row_width = sub_ink.sum(axis=1)  # per-row figure-ink width
    fig_rows = np.where(row_width > MIN_W)[0]
    if fig_rows.size == 0:
        return []
    # group consecutive rows (allowing small gaps)
    blobs = []
    start = fig_rows[0]
    prev = fig_rows[0]
    for r in fig_rows[1:]:
        if r - prev <= GAP:
            prev = r
        else:
            blobs.append((start, prev))
            start = r
            prev = r
    blobs.append((start, prev))
    out = []
    for s, e in blobs:
        ys = band0 + s
        ye = band0 + e
        h = ye - ys
        if h < MIN_H:
            continue
        cols = np.where(sub_ink[s:e + 1, :].any(axis=0))[0]
        if cols.size == 0:
            continue
        xs, xe = int(cols[0]), int(cols[-1])
        w = xe - xs
        if w < MIN_W or (w * h) < MIN_AREA:
            continue
        # drop thin strips (text-line fragments): very wide & short, or very tall & narrow
        if w >= MAX_STRIP_RATIO * h or h >= MAX_STRIP_RATIO * w:
            continue
        if h > 0.85 * H:   # skip near-full-page blobs
            continue
        # require real ink density: a figure fills ~5%+ of its bounding box;
        # a watermark / low-density popup / faded page-bottom content does not.
        ink_px = int(sub_ink[ys:ye + 1, xs:xe + 1].sum())
        if ink_px < 0.04 * (w * h):
            continue
        out.append((xs, xe, ys, ye))
    return out


def main():
    pages = load_boxes()
    if not pages:
        raise SystemExit("ocr_boxes.jsonl empty - run ocr_cs_boxes.py first")
    ms_start = find_ms_start(pages)
    print(f"[crop-cs] pages={len(pages)} ms_start={ms_start}", flush=True)

    db = sqlite3.connect(DB_PATH)
    rows = db.execute("SELECT id FROM questions WHERE subject='CS'").fetchall()
    idnorm = {norm_key(r[0]): r[0] for r in rows}
    # reset stale figure columns so re-runs start clean
    db.execute("UPDATE questions SET figure=NULL, answer_figure=NULL WHERE subject='CS'")
    db.commit()
    print("[crop-cs] cleared CS figure/answer_figure columns", flush=True)

    ckpt = {"done": []}
    if os.path.exists(CKPT):
        try:
            ckpt = json.load(open(CKPT))
        except Exception:
            pass
    done = set(ckpt["done"])

    stats = {"Q_linked": 0, "A_linked": 0, "Q_no": 0, "A_no": 0, "files": 0}
    last_id = None  # carry question id across pages (spanning questions)

    for pno in sorted(pages):
        if pno in done:
            continue
        lines = sorted(pages[pno], key=lambda ln: ln["bbox"][1])
        # mark code-line indices
        code_idx = []
        for i, ln in enumerate(lines):
            t = (ln.get("text") or "").strip()
            if CODE.match(t):
                code_idx.append(i)
        # build blocks: (y_top, y_bot, owning_id)
        blocks = []
        if code_idx:
            for k, idx in enumerate(code_idx):
                y_top = lines[idx]["bbox"][1]
                y_bot = lines[code_idx[k + 1]]["bbox"][1] if k + 1 < len(code_idx) else 1e9
                code = CODE.match(lines[idx]["text"].strip()).group(0)
                rid = idnorm.get(norm_key("CS-" + code))
                if rid is not None:
                    last_id = rid  # a real question now "owns" the carry
                blocks.append((y_top, y_bot, rid, idx))
            # content above the first code line belongs to the carried question
            if lines[code_idx[0]]["bbox"][1] > 1 and last_id is not None:
                blocks.insert(0, (0.0, lines[code_idx[0]]["bbox"][1], last_id, -1))
        else:
            # no code on this page (OCR-garbled or continuation): carry previous id
            if last_id is not None:
                blocks = [(0.0, 1e9, last_id, -1)]

        is_ms = pno >= ms_start
        col = "answer_figure" if is_ms else "figure"

        # render page once
        pdf = pdfium.PdfDocument(PDF)
        try:
            page = pdf[pno - 1]
            Wpt, Hpt = page.get_size()
            pil = page.render(scale=CROP_SCALE).to_pil().convert("L")
        finally:
            pdf.close()
        gray = np.asarray(pil)
        H, W = gray.shape
        textmask = np.zeros((H, W), dtype=bool)
        # build text mask from all line bboxes (points -> px)
        for ln in lines:
            x0, y0, x1, y1 = ln["bbox"]
            px0 = max(0, int(x0 * CROP_SCALE) - TEXT_PAD)
            py0 = max(0, int(y0 * CROP_SCALE) - TEXT_PAD)
            px1 = min(W, int(x1 * CROP_SCALE) + TEXT_PAD)
            py1 = min(H, int(y1 * CROP_SCALE) + TEXT_PAD)
            if px1 > px0 and py1 > py0:
                textmask[py0:py1, px0:px1] = True

        linked_any = False
        for (y_top, y_bot, rid, _) in blocks:
            if rid is None:
                continue
            yb = Hpt if y_bot == 1e9 else y_bot
            blobs = detect_figure_blobs(gray, textmask,
                                        y_top * CROP_SCALE, yb * CROP_SCALE)
            if not blobs:
                continue
            seq = 0
            paths = []
            for (xs, xe, ys, ye) in blobs:
                seq += 1
                fkey = f"cs-{norm_key(rid)}-p{pno}-f{seq}.jpg"
                out_path = os.path.join(FIG_DIR, fkey)
                if not os.path.exists(out_path):
                    crop = pil.crop((max(0, xs - PAD), max(0, ys - PAD),
                                     min(W, xe + PAD), min(H, ye + PAD)))
                    crop.save(out_path, quality=88)
                    stats["files"] += 1
                paths.append("/figures/" + fkey)
            if paths:
                cur = db.execute(f"SELECT {col} FROM questions WHERE id=?", (rid,)).fetchone()
                existing = (cur[0] or "")
                merged = list(dict.fromkeys([p for p in existing.split(",") if p] + paths))
                db.execute(f"UPDATE questions SET {col}=? WHERE id=?",
                           (",".join(merged), rid))
                stats["A_linked" if is_ms else "Q_linked"] += 1
                linked_any = True
        db.commit()
        done.add(pno)
        ckpt["done"] = sorted(done)
        with open(CKPT, "w") as f:
            json.dump(ckpt, f)
        print(f"  [crop-cs] page {pno} ({'MS' if is_ms else 'Q'}) blocks={len(blocks)} "
              f"linked={'Y' if linked_any else 'n'}", flush=True)

    print(f"[crop-cs] DONE: {stats}", flush=True)
    db.close()


if __name__ == "__main__":
    main()
