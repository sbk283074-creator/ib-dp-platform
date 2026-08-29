#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Second-pass gate diagnostic: count digit vs letter left-margin markers and
model the relaxed gate that accepts continuation pages."""
import os, re, sys, gc
from collections import Counter
import booklib as B
import pypdfium2 as pdfium

DP = "/Users/lucas.ma/Downloads/dp learning"
BOOK_PATH = (f"{DP}/Physics-HLSL-Oxford Textbook(First exam 2025)/"
             f"Physics - Course Companion - Homer, Piętka and Heathcote - "
             f"Fifth Edition - Oxford 2023.pdf")

EXCLUDE_RE = B.EXCLUDE_RE
INTRO_RE = B.INTRO_RE
HEAD_PAT = re.compile('|'.join(B.EXERCISE_HEADERS), re.I)
LET_RE = re.compile(r'^\(?[a-eA-E]\)?[.)]?\s+\S')


def stats(page, x0frac=0.20):
    H = float(page.get_height()); W = float(page.get_width())
    lines = B.pdfium_lines(page)
    txt = '\n'.join(t for _, t, _ in lines)
    head_txt = '\n'.join(t for _, t, _ in lines[:8])
    margin = x0frac * W
    digit = 0
    letter = 0
    for top, text, x0 in lines:
        if (0 <= top < 0.05 * H or top > 0.94 * H) and len(text) < 15:
            continue
        n = B._line_start_number(text, True)
        if n is not None and x0 <= margin:
            digit += 1
        elif LET_RE.match(text) and x0 <= margin:
            letter += 1
    reasons = []
    if EXCLUDE_RE.search(txt[:400]):
        reasons.append('EXCLUDE')
    if INTRO_RE.search(txt[:600]):
        reasons.append('INTRO')
    if B.has_toc_dots(page):
        reasons.append('TOC')
    has_head = bool(HEAD_PAT.search(head_txt))
    bad = any(r in reasons for r in ('EXCLUDE', 'INTRO', 'TOC'))
    # proposed relaxed gate: not bad, AND (heading OR digit>=1 OR letter>=2)
    relaxed = (not bad) and (has_head or digit >= 1 or letter >= 2)
    return dict(digit=digit, letter=letter, has_head=has_head, bad=bad,
                reasons=reasons, relaxed=relaxed)


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    pdf = pdfium.PdfDocument(BOOK_PATH)
    n = len(pdf)
    tot = relaxed = 0
    d1 = d2 = d3plus = letter_cont = head_only = 0
    digit_sum = 0
    reason_counter = Counter()
    for i in range(n):
        page = pdf[i]
        try:
            s = stats(page)
        except Exception as e:
            print(f"  p{i+1} ERR {e}", flush=True)
            page = None; gc.collect(); continue
        tot += 1
        if s['relaxed']:
            relaxed += 1
        if s['digit'] >= 1:
            d1 += 1
            digit_sum += s['digit']
        if s['digit'] >= 2:
            d2 += 1
        if s['digit'] >= 3:
            d3plus += 1
        if s['digit'] == 0 and s['letter'] >= 2 and not s['bad']:
            letter_cont += 1
        if s['has_head'] and s['digit'] == 0 and s['letter'] < 2:
            head_only += 1
        for r in s['reasons']:
            reason_counter[r] += 1
        if limit and i + 1 >= limit:
            break
        page = None; gc.collect()
    print(f"PAGES={tot}", flush=True)
    print(f"RELAXED_PASS={relaxed}", flush=True)
    print(f"pages digit>=1 ={d1}  digit>=2 ={d2}  digit>=3 ={d3plus}", flush=True)
    print(f"continuation(0 digit,>=2 letter,notbad)={letter_cont}", flush=True)
    print(f"head_only(heading,0 digit,<2 letter)={head_only}", flush=True)
    print(f"SUM digit markers on digit>=1 pages={digit_sum} (lower bound on questions)", flush=True)
    print("REJECT_REASON_COUNTS:", dict(reason_counter), flush=True)
    pdf.close()


if __name__ == '__main__':
    main()
