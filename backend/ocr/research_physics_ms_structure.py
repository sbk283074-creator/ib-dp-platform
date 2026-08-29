#!/usr/bin/env python3
"""Deeper probe: print full markscheme text for a few physics topics to learn
the exact answer-delimit structure (prompt repetition, Examiners report,
marks notation). READ-ONLY."""
import os, re
import pypdfium2 as pdfium

SRC = "/Users/lucas.ma/Downloads/dp learning/Physics-HL-Topic questions"

def full_text(path):
    doc = pdfium.PdfDocument(path)
    return "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))

def dump(fol, paper):
    qp = os.path.join(SRC, fol, paper + ".pdf")
    msp = os.path.join(SRC, fol, "markscheme-" + paper + ".pdf")
    if not os.path.exists(msp):
        # try Capital M
        msp = os.path.join(SRC, fol, "Markscheme-" + paper + ".pdf")
    print("\n" + "="*70)
    print(f"{fol} / {paper}")
    print("="*70)
    ms = full_text(msp)
    print("--- FULL MARKSCHEME TEXT (repr) ---")
    print(repr(ms))
    print("--- COUNTS ---")
    print("  [N marks]:", len(re.findall(r"\[\d+\s*marks?\]", ms)))
    print("  [N] bare  :", len(re.findall(r"\[\d+\]", ms)))
    print("  'Examiners report' occurrences:", len(re.findall(r"Examiners report", ms, re.I)))
    print("  'Markscheme' header occurrences:", len(re.findall(r"Markscheme", ms)))

for fol, paper in [("Topic 1","HL-paper1"), ("Topic 12","HL-paper3"), ("Option B","HL-Paper-1")]:
    dump(fol, paper)
