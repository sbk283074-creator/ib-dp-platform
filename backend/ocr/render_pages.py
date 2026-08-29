#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render specific pages of a PDF to PNG for visual research.

Usage: python render_pages.py <BOOKID|PDFPATH> <page1> <page2> ... [--dpi 110]
Output: /tmp/research/<name>_p<page>.png
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pypdfium2 as pdfium
from extract_books import BOOKS

OUT = "/tmp/research"
os.makedirs(OUT, exist_ok=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('book')
    ap.add_argument('pages', nargs='+', type=int)
    ap.add_argument('--dpi', type=int, default=110)
    args = ap.parse_args()
    bk = next((b for b in BOOKS if b['id'] == args.book and not b.get('scanned')), None)
    path = bk['path'] if bk else args.book
    if not os.path.exists(path):
        print("path not found:", path); sys.exit(1)
    name = bk['id'] if bk else os.path.splitext(os.path.basename(path))[0]
    pdf = pdfium.PdfDocument(path)
    for p in args.pages:
        if p < 1 or p > len(pdf):
            print(f"skip p{p} (out of range 1..{len(pdf)})"); continue
        page = pdf[p-1]
        scale = args.dpi/72.0
        img = page.render(scale=scale).to_pil()
        out = os.path.join(OUT, f"{name}_p{p}.png")
        img.save(out, 'PNG')
        print("wrote", out, img.size)
    pdf.close()

if __name__ == '__main__':
    main()
