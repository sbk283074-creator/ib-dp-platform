#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare bleed universe (loose) vs what the FIX catches (terminator-gated).

For every physics raw Q-PDF, walk the lines and flag any MID-LINE occurrence of
the NEXT question number (cur+1 / cur+2) that is not a reference. Report whether
the fix's terminator gate would catch it, plus the full line for review.
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_pm as E

Q_MID = re.compile(r"(?<!\d)(\d{1,2})\.(?!\d)\s+(?=[A-Z(])")
REF = ("figure", "fig.", "equation", "section", "step", "diagram",
       "table", "graph", "refer", "see ", "as in", "shown in", "(", "[")
TERM = ".!?):]"

def naive_qnums(text):
    """Return list of (qnum, cur_part_context) by replaying line-start only."""
    qs = {}
    cur = None
    cur_qnum = 0
    for ln in text.split("\n"):
        s = ln.strip()
        m = E.Q_START.match(s)
        if m:
            qnum = int(m.group(1))
            if 0 < qnum <= 99:
                cur = qs.setdefault(qnum, [])
                cur_qnum = qnum
            continue
        if cur is None:
            continue
        # detect mid-line next-number bleed candidates
        for mm in Q_MID.finditer(s):
            nn = int(mm.group(1))
            if nn != cur_qnum + 1 and nn != cur_qnum + 2:
                continue
            pre = s[:mm.start()].rstrip()
            pre_tail = pre[-14:].lower()
            if any(w in pre_tail for w in REF):
                continue
            pre_end = pre[-1:] if pre else ""
            caught = pre_end in TERM
            qs.setdefault(cur_qnum, [])
            yield (cur_qnum, nn, caught, s)
    return qs

def main():
    totals = {"caught": 0, "missed": 0}
    for label, disp, paper, tz, qpath, _mspath in E.phy_raw_walker():
        if not qpath or not os.path.exists(qpath):
            continue
        text = E.pdf_text(qpath)
        if not text:
            continue
        for cur_qnum, nn, caught, line in naive_qnums(E.strip_noise(text)):
            totals["caught" if caught else "missed"] += 1
            tag = "FIX" if caught else "MISS"
            print(f"[{tag}] {label} {paper}{(' '+tz) if tz else ''} Q{cur_qnum}->Q{nn}: {line!r}")
    print(f"\nSUMMARY: caught_by_fix={totals['caught']} missed={totals['missed']}")

if __name__ == "__main__":
    main()
