#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Re-OCR of IB 计算机分类真题.pdf (scanned, 547 pages) but KEEP bounding boxes.
Output: ocr_boxes.jsonl with {page, lines:[{bbox:[x0,y0,x1,y1] (PDF points), text, conf}]}
These boxes are required to (a) locate each question/markscheme's vertical band on
its page and (b) crop figure regions from the rendered page raster.

Resumable: pages already present in the output file are skipped.
Usage:
  python3 ocr_cs_boxes.py --start 1 --end 20      # sample
  python3 ocr_cs_boxes.py                          # full (all pages)
"""
import argparse, json, os, sys
import numpy as np
import pypdfium2 as pdfium
from PIL import Image

PDF = "/Users/lucas.ma/Downloads/dp learning/IB 计算机分类真题.pdf"
DPI = 250
LANGS = ["en", "ch_sim"]
SCALE = DPI / 72.0          # pypdfium2 render scale for OCR
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "ocr_boxes.jsonl")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--dpi", type=int, default=DPI)
    ap.add_argument("--langs", default=",".join(LANGS))
    args = ap.parse_args()
    langs = [l.strip() for l in args.langs.split(",") if l.strip()]

    print(f"[ocr-box] loading easyocr langs={langs} ...", flush=True)
    import easyocr
    reader = easyocr.Reader(langs, gpu=False)

    pdf = pdfium.PdfDocument(PDF)
    n = len(pdf)
    end = args.end or n
    end = min(end, n)
    print(f"[ocr-box] pages {args.start}..{end} (total {n})", flush=True)

    done = set()
    if os.path.exists(args.out):
        with open(args.out, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["page"])
                except Exception:
                    pass
        print(f"[ocr-box] resuming; {len(done)} pages already done", flush=True)

    with open(args.out, "a", encoding="utf-8") as out:
        for pno in range(args.start, end + 1):
            if pno in done:
                continue
            try:
                page = pdf[pno - 1]
                pil = page.render(scale=args.dpi / 72.0).to_pil()
                res = reader.readtext(np.array(pil), detail=1, paragraph=False)
                lines = []
                for item in res:
                    bbox, text, conf = item[0], item[1], item[2]
                    pts = np.array(bbox, dtype=float)
                    x0, y0 = pts[:, 0].min(), pts[:, 1].min()
                    x1, y1 = pts[:, 0].max(), pts[:, 1].max()
                    # convert OCR-pixel coords -> PDF points (scale-independent)
                    lines.append({
                        "bbox": [round(x0 / SCALE, 1), round(y0 / SCALE, 1),
                                 round(x1 / SCALE, 1), round(y1 / SCALE, 1)],
                        "text": text,
                        "conf": round(float(conf), 3),
                    })
                rec = {"page": pno, "lines": lines}
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                print(f"[ocr-box] page {pno}/{end} lines={len(lines)}", flush=True)
            except Exception as e:
                print(f"[ocr-box] page {pno} ERROR: {type(e).__name__}: {e}", flush=True)
                continue
    print("[ocr-box] DONE", flush=True)


if __name__ == "__main__":
    main()
