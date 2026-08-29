#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crop full question + markscheme IMAGES for every CS question from the scanned
book `IB 计算机分类真题.pdf`, using the bounding boxes in ocr_boxes.jsonl.

Output: backend/public/figures/csq-*.jpg (question) and csa-*.jpg (answer)
plus cs_image_map.json: {normalized_code: {"q": [paths...], "a": [paths...]}}

Band logic: a question starts at its IB-code line and runs to the next code
line (across pages, including the top of the next code's page).
Sections: Questions pp 1-223, Markschemes pp 224-547 (landscape 842x595 pt).
"""
import json, os, re
import pypdfium2 as pdfium

HERE = os.path.dirname(os.path.abspath(__file__))
PDF = "/Users/lucas.ma/Downloads/dp learning/IB 计算机分类真题.pdf"
OCR = os.path.join(HERE, "ocr_boxes.jsonl")
OUTDIR = os.path.join(HERE, "..", "public", "figures")
MAP_OUT = os.path.join(HERE, "cs_image_map.json")

DPI = 150
SCALE = DPI / 72.0
Q_END = 223          # last page of Questions section
MS_START = 224
X0, X1 = 12, 830     # generous horizontal margins (landscape page, keep figures)
Y_TOP, Y_BOT = 16, 580

CODE = re.compile(r"^(\d{2}[MN]\.\d\.[SH]L\.TZ[O0]\.\d+)[O0lI]?$")  # trailing OCR noise ok

def norm(t):
    return t.replace("O", "0")

def load_pages():
    pages = {}
    with open(OCR, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            pages[rec["page"]] = rec["lines"]
    return pages

def find_markers(pages, lo, hi):
    """[(page, y0, code)] for code lines on pages lo..hi (1-based, inclusive)."""
    out = []
    for pno in range(lo, hi + 1):
        for l in pages.get(pno, []):
            m = CODE.match(l["text"].strip())
            if m:
                out.append((pno, l["bbox"][1], norm(m.group(1))))
    out.sort(key=lambda t: (t[0], t[1]))
    # dedupe repeated codes (keep first)
    seen, deduped = set(), []
    for p, y, c in out:
        if c in seen:
            continue
        seen.add(c)
        deduped.append((p, y, c))
    return deduped

def build_bands(markers, last_page):
    """code -> [(page, y0, y1)] covering the question from its code to the next code."""
    bands = {}
    for i, (pno, y0, code) in enumerate(markers):
        segs = []
        if i + 1 < len(markers):
            npno, ny0, _ = markers[i + 1]
        else:
            npno, ny0 = last_page + 1, None
        if npno == pno:
            segs.append((pno, y0, ny0))
        else:
            segs.append((pno, y0, Y_BOT))
            for pp in range(pno + 1, npno):
                segs.append((pp, Y_TOP, Y_BOT))
            if npno <= last_page:  # top of next marker's page belongs to this band
                segs.append((npno, Y_TOP, ny0))
        bands[code] = segs
    return bands

def main():
    pages = load_pages()
    os.makedirs(OUTDIR, exist_ok=True)

    q_marks = find_markers(pages, 1, Q_END)
    a_marks = find_markers(pages, MS_START, len(pages))
    print(f"[cs-img] question markers: {len(q_marks)}, markscheme markers: {len(a_marks)}", flush=True)

    q_bands = build_bands(q_marks, Q_END)
    a_bands = build_bands(a_marks, len(pages))

    pdf = pdfium.PdfDocument(PDF)
    n = len(pdf)
    print(f"[cs-img] pdf pages: {n}", flush=True)

    def code_fn(code):
        return code.replace(".", "-")

    def crop_bands(bands, prefix):
        result = {}
        cache_page, cache_img = -1, None
        for code, segs in bands.items():
            paths = []
            for (pno, y0, y1) in segs:
                if not (1 <= pno <= n):
                    continue
                if cache_page != pno:
                    cache_page, cache_img = pno, pdf[pno - 1].render(scale=SCALE).to_pil()
                img = cache_img.crop((int(X0 * SCALE), int(y0 * SCALE),
                                      int(X1 * SCALE), int(y1 * SCALE)))
                if img.height < 12:   # degenerate sliver
                    continue
                rel = f"/figures/{prefix}-{code_fn(code)}-p{pno}.jpg"
                img.save(os.path.join(OUTDIR, os.path.basename(rel)), "JPEG", quality=85)
                paths.append(rel)
            if paths:
                result[code] = paths
        return result

    print("[cs-img] cropping questions ...", flush=True)
    q_map = crop_bands(q_bands, "csq")
    print(f"[cs-img] questions cropped: {len(q_map)}", flush=True)
    print("[cs-img] cropping markschemes ...", flush=True)
    a_map = crop_bands(a_bands, "csa")
    print(f"[cs-img] markschemes cropped: {len(a_map)}", flush=True)

    out = {}
    for code in set(q_map) | set(a_map):
        out[code] = {"q": q_map.get(code, []), "a": a_map.get(code, [])}
    with open(MAP_OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    nq_img = sum(len(v) for v in q_map.values())
    na_img = sum(len(v) for v in a_map.values())
    print(f"[cs-img] DONE. {nq_img} question images, {na_img} answer images -> {MAP_OUT}", flush=True)

if __name__ == "__main__":
    main()
