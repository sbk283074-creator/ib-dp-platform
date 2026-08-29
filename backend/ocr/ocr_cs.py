#!/usr/bin/env python3
"""
OCR pipeline for IB 计算机分类真题.pdf (scanned, 547 pages, no text layer).
Renders each page to a temp PNG, OCRs with easyocr, streams {page, text} to a JSONL.
Usage:
  python ocr_cs.py --out ocr.jsonl --start 1 --end 15        # sample
  python ocr_cs.py --out ocr_all.jsonl --start 1 --end 547   # full
  python ocr_cs.py --out ocr_all.jsonl                       # full (defaults to all pages)
"""
import argparse, json, os, sys, tempfile, io
import numpy as np
import pypdfium2 as pdfium
from PIL import Image

PDF = "/Users/lucas.ma/Downloads/dp learning/IB 计算机分类真题.pdf"
DPI = 250
LANGS = ["en", "ch_sim"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--dpi", type=int, default=DPI)
    ap.add_argument("--langs", default=",".join(LANGS))
    args = ap.parse_args()
    langs = [l.strip() for l in args.langs.split(",") if l.strip()]

    print(f"[ocr] loading easyocr langs={langs} ...", flush=True)
    import easyocr
    reader = easyocr.Reader(langs, gpu=False)

    print(f"[ocr] opening PDF", flush=True)
    pdf = pdfium.PdfDocument(PDF)
    n = len(pdf)
    end = args.end or n
    end = min(end, n)
    print(f"[ocr] pages {args.start}..{end} (total {n})", flush=True)

    # resume: skip pages already in out file
    done = set()
    if os.path.exists(args.out):
        with open(args.out, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    done.add(json.loads(line)["page"])
                except Exception:
                    pass
        print(f"[ocr] resuming; {len(done)} pages already done", flush=True)

    with open(args.out, "a", encoding="utf-8") as out:
        for pno in range(args.start, end + 1):
            if pno in done:
                continue
            try:
                page = pdf[pno - 1]
                pil = page.render(scale=args.dpi / 72.0).to_pil()
                # OCR (easyocr 1.7.2 needs a numpy array, not a PIL image)
                res = reader.readtext(np.array(pil), detail=0, paragraph=True)
                text = "\n".join(res).strip()
                rec = {"page": pno, "text": text}
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                print(f"[ocr] page {pno}/{end} chars={len(text)}", flush=True)
            except Exception as e:
                # Never let one bad page kill the whole run; resume will skip it next time.
                print(f"[ocr] page {pno} ERROR: {type(e).__name__}: {e}", flush=True)
                continue
    print("[ocr] DONE", flush=True)

if __name__ == "__main__":
    main()
