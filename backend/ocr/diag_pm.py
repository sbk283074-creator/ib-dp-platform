#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flag stem-bleed in physics raw Q-PDF parsing.

Bleed = a next-question number (cur+1 or cur+2) appears MID-LINE inside a
sub-part (or intro) of the previous question, because pdfplumber merged the
new question's "N." onto the previous line. parse_qpdf then appends it to the
previous sub-part instead of starting a new question.
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_pm as E

# mid-line question start: number not preceded/followed by a digit, followed
# by whitespace + capital or "(" (stem or sub-part). Excludes decimals "16.0".
Q_MID = re.compile(r"(?<!\d)(\d{1,2})\.(?!\d)\s+(?=[A-Z(])")

REF_WORDS = ("figure", "fig.", "fig ", "eq", "equation", "section", "step",
             "diagram", "table", "graph", "refer", "see ", "as in", "shown in",
             "the ", "of ", "in ", "a ", "is ", "was ")

TERMINATORS = ".!?):]"

def scan_paper(label, disp, paper, tz, qpath):
    if not qpath or not os.path.exists(qpath):
        return
    text = E.pdf_text(qpath)
    if not text:
        return
    qs = E.parse_qpdf(E.strip_noise(text))
    nums = sorted(qs.keys())
    for qnum in nums:
        q = qs[qnum]
        seq = [("__intro__", q["intro"])]
        for letter in sorted(q["parts"].keys()):
            seq.append((letter, q["parts"][letter]))
        for part_key, lines in seq:
            for ln in lines:
                s = ln.strip()
                for m in Q_MID.finditer(s):
                    nn = int(m.group(1))
                    if nn != qnum + 1 and nn != qnum + 2:
                        continue
                    pre = s[:m.start()].rstrip()
                    pre_end = pre[-1:] if pre else ""
                    if pre_end not in TERMINATORS:
                        continue  # e.g. "d 2." variable, not a new question
                    if any(w in pre.lower() for w in REF_WORDS):
                        continue
                    print(f"  [{label} {paper}{(' '+tz) if tz else ''}] Q{qnum} part={part_key} -> mid-line NEXT Q{nn}: {s[:90]!r}")

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None  # e.g. "Paper 3"
    for label, disp, paper, tz, qpath, _mspath in E.phy_raw_walker():
        if target and paper != target:
            continue
        scan_paper(label, disp, paper, tz, qpath)

if __name__ == "__main__":
    main()
