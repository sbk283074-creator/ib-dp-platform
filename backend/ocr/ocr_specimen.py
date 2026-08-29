#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCR Specimen Papers 2025 (Physics HL) -> specimen_ocr.jsonl (page -> text)."""
import argparse, json, os, sys
import numpy as np
import pypdfium2 as pdfium
import easyocr

PDF = "/Users/lucas.ma/Downloads/dp learning/Physics-HLSL-Specimen Papers(First exam 2025)/Specimen Papers 2025 - English.pdf"
DPI = 110

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "specimen_ocr.jsonl"))
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=None)
    args = ap.parse_args()
    import torch
    torch.set_num_threads(2)
    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    pdf = pdfium.PdfDocument(PDF)
    n = len(pdf)
    end = min(args.end or n, n)
    done = set()
    if os.path.exists(args.out):
        for line in open(args.out, encoding="utf-8"):
            try: done.add(json.loads(line)["page"])
            except Exception: pass
        print(f"[ocr] resume; {len(done)} pages done", flush=True)
    with open(args.out, "a", encoding="utf-8") as f:
        for pno in range(args.start, end + 1):
            if pno in done:
                continue
            try:
                pil = pdf[pno - 1].render(scale=DPI / 72.0).to_pil()
                arr = np.asarray(pil)
                res = reader.readtext(arr, detail=1, paragraph=True, batch_size=1)
                # keep line order: sort by (y, x); tolerate 2- or 3-tuples
                items = []
                for it in res:
                    if len(it) == 3:
                        box, txt, conf = it
                    elif len(it) == 2:
                        box, txt = it
                    else:
                        continue
                    ys = [pt[1] for pt in box]; xs = [pt[0] for pt in box]
                    items.append((min(ys), min(xs), str(txt).strip()))
                items.sort()
                text = "\n".join(t for _, _, t in items if t)
                f.write(json.dumps({"page": pno, "text": text}, ensure_ascii=False) + "\n")
                f.flush()
                if pno % 10 == 0:
                    print(f"[ocr] p{pno}/{end}", flush=True)
            except Exception as e:
                sys.stderr.write(f"p{pno} err {e}\n")
    pdf.close()
    print("[ocr] DONE", flush=True)

if __name__ == "__main__":
    main()
