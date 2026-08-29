#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract Physics classified bank — Option B (filenames HL-Paper-N.pdf)."""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_pm as E

def main():
    out = []
    for paper in ("HL-Paper-1", "HL-Paper-2", "HL-Paper-3"):
        recs = E.classified_blocks(E.S_PHY, "Option B", paper, E.PHY_KP)
        for r in recs:
            # normalize source/paper naming to match existing Option A/C/D format
            r["source"] = r["source"].replace(paper, "HL-paper" + re.sub(r"\D", "", paper))
            r["paper_type"] = "Paper " + re.sub(r"\D", "", paper)
            r["subtopic"] = r["paper_type"]
        print(f"Option B {paper}: {len(recs)} questions", flush=True)
        out.extend(recs)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "option_b_import.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"TOTAL {len(out)} -> {path}", flush=True)

if __name__ == "__main__":
    main()
