#!/usr/bin/env python3
"""Regenerate ONLY physics classified (PHY-CLS-*) records using the fixed
separator-line-aware classified_blocks, and write them back into
physics_math_import.json without touching raw or math data.

Usage: python reimport... no — just: python reexport_physics_cls.py
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract_pm as E

OUT = E.OUT

def main():
    data = json.load(open(OUT, encoding="utf-8"))
    print(f"[load] total={len(data)}")

    # Separate physics classified from everything else.
    phy_cls = [q for q in data if q.get("id", "").startswith("PHY-CLS-")]
    rest = [q for q in data if not q.get("id", "").startswith("PHY-CLS-")]
    print(f"[split] phy_cls={len(phy_cls)}  rest(raw+math)={len(rest)}")

    # Regenerate physics classified.
    new_phy_cls = []
    for folder in sorted(os.listdir(E.PHY_CLS),
                         key=lambda x: (0, int(re.sub(r"\D", "", x) or 0)) if x.startswith("Topic") else (1, x)):
        fdir = os.path.join(E.PHY_CLS, folder)
        if not os.path.isdir(fdir):
            continue
        for paper in ("HL-paper1", "HL-paper2", "HL-paper3"):
            recs = E.classified_blocks(E.S_PHY, folder, paper, E.PHY_KP)
            if recs:
                print(f"  {folder} {paper}: {len(recs)}", flush=True)
            new_phy_cls.extend(recs)

    # Strip internal keys already done by classified_blocks output (it returns
    # dicts without '_cls'); ensure no stray keys.
    new_phy_cls = [{k: v for k, v in q.items() if not k.startswith("_")} for q in new_phy_cls]
    print(f"[regen] new_phy_cls={len(new_phy_cls)} (was {len(phy_cls)})")

    # Re-dedup new physics classified against raw physics (drop classified dupes
    # of raw 真题, keep raw). Use same token-overlap heuristic as main().
    raw_phy = [q for q in rest if q.get("subject") == E.S_PHY and q.get("id", "").startswith("PHY-RAW-")]
    raw_tok = [(E.norm_tokens(q["question"]),) for q in raw_phy]
    kept = []
    dropped = 0
    for q in new_phy_cls:
        ct = E.norm_tokens(q["question"])
        head = set(list(ct.elements())[:10])
        dup = False
        for (rt,) in raw_tok:
            if len(head & set(rt.elements())) < 4:
                continue
            inter = sum((ct & rt).values())
            union = sum((ct | rt).values())
            if union and inter / union >= 0.45:
                dup = True
                break
        if dup:
            dropped += 1
        else:
            kept.append(q)
    print(f"[dedup] phy_cls kept={len(kept)} dropped={dropped}")

    final = rest + kept
    final.sort(key=lambda q: (q["subject"], q.get("source") or "", q["id"]))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=1)
    by_subj = {}
    for q in final:
        by_subj[q["subject"]] = by_subj.get(q["subject"], 0) + 1
    print(f"[done] total={len(final)} -> {OUT}")
    for s, n in sorted(by_subj.items()):
        print(f"  {s}: {n}")

if __name__ == "__main__":
    main()
