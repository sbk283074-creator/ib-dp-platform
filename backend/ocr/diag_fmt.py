#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dump how PH-OX-2023 numbers its questions: for selected pages, print lines
that start with a digit/letter and their x0 fraction, so we can see the real
question-numbering format (e.g. '1.', '1.1', '(a)', 'Q1')."""
import sys
import booklib as B
import pypdfium2 as pdfium

DP = "/Users/lucas.ma/Downloads/dp learning"
BOOK_PATH = (f"{DP}/Physics-HLSL-Oxford Textbook(First exam 2025)/"
             f"Physics - Course Companion - Homer, Piętka and Heathcote - "
             f"Fifth Edition - Oxford 2023.pdf")

pages = [int(x) for x in sys.argv[1:]] or list(range(50, 700, 50))


def main():
    pdf = pdfium.PdfDocument(BOOK_PATH)
    for pno in pages:
        if pno - 1 >= len(pdf):
            continue
        page = pdf[pno - 1]
        H = float(page.get_height()); W = float(page.get_width())
        lines = B.pdfium_lines(page)
        print(f"\n===== p{pno}  (H={H:.0f} W={W:.0f}) =====")
        shown = 0
        for top, text, x0 in lines:
            if re_num_start(text):
                print(f"  top={top/H:.3f} x0={x0/W:.3f}  | {text[:70]!r}")
                shown += 1
            if shown >= 18:
                break
        if shown == 0:
            # show first 5 raw lines for context
            for top, text, x0 in lines[:5]:
                print(f"  raw top={top/H:.3f} x0={x0/W:.3f} | {text[:70]!r}")
        page = None
    pdf.close()


def re_num_start(text):
    import re
    return bool(re.match(r'^(\d{1,3})(\.\d+)?[.)]?\s', text)) or \
        bool(re.match(r'^\(?[a-e]\)?[.)]?\s', text))


if __name__ == '__main__':
    main()
