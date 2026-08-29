#!/usr/bin/env python3
"""One-time patch for math_topic_manifest.json.

Fixes two issues reported 2026-08-26:
  1. Cover/title-only pages (Topic 7 P1, Topic 8 P1, Topic 8 P2, Topic 10 P1, Topic 10 P2)
     were extracted as a single fake question containing just the page title "HL Paper N"
     (OCR'd as "HLPaerNp"). Those records are removed and their orphaned image files
     deleted from backend/public/figures/math_topic/.
  2. Real q01 records for topics that DO have questions have a leaked "HL Paper N"
     header prefix in their question_text and answer_text (the page title leaked into
     the first content band because the header separator was below HEADER_MAX_PX). The
     leading title token is stripped so stored text is clean.

Idempotent: re-running is a no-op (nothing left to drop; strip leaves non-matching text
unchanged).

Usage:
    cd backend && python3 ocr/patch_math_topic_cover.py
"""
import json, os, re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(BASE, "data", "math_topic_manifest.json")
FIG_ROOT = os.path.join(BASE, "public", "figures", "math_topic")

# Matches the OCR'd page-header title that leaks into q01 text, e.g.:
#   "HLPaer1p", "HL Paper 1", "HLPaer1 p", "HLPaer2p"
# Anchored at the start of the string, case-insensitive. Tolerant to letter
# run-together from stylized title rendering.
TITLE_LEAD = re.compile(
    r"^\s*hl\.?\s*p\w*r\s*\d+\s*p?\s*[\r\n]*",
    re.IGNORECASE,
)


def strip_title(text: str) -> str:
    """Remove a leading 'HL Paper N' header token from text (if present)."""
    if not text:
        return text
    return TITLE_LEAD.sub("", text).strip()


def is_cover(text: str) -> bool:
    """True iff text is just a cover/title page (no real question content).

    Heuristic: the raw text contains a digit (the page-number part of the title),
    and after stripping the title token, fewer than 3 alphanumerics remain. This
    catches the 5 known cover-only cases while preserving short real questions
    like "Find." / "Solve." (no digit, or > 3 alnum after strip).
    """
    raw = (text or "").strip()
    if not raw:
        return False
    if not re.search(r"\d", raw):
        return False
    rest = strip_title(raw)
    alnum = re.sub(r"[^a-z0-9]", "", rest.lower())
    return len(alnum) < 3


def main():
    with open(MANIFEST, "r", encoding="utf-8") as f:
        records = json.load(f)

    print(f"Loaded {len(records)} records from {MANIFEST}")

    kept, dropped, images_to_delete = [], [], []
    for r in records:
        if is_cover(r.get("question_text", "")):
            dropped.append(r)
            for key in ("question_image", "answer_image"):
                rel = r.get(key) or ""
                for p in rel.split(","):
                    p = p.strip()
                    if p:
                        images_to_delete.append(os.path.join(FIG_ROOT, p))
        else:
            r["question_text"] = strip_title(r.get("question_text", ""))
            r["answer_text"] = strip_title(r.get("answer_text", ""))
            kept.append(r)

    print(f"\nDropping {len(dropped)} cover-only record(s):")
    for r in dropped:
        print(f"  - {r['topic']} {r['paper_type']:11s} {r['id']}  text={r['question_text']!r}")

    # Delete orphan images
    deleted = 0
    for path in images_to_delete:
        if os.path.isfile(path):
            os.remove(path)
            deleted += 1
    print(f"\nDeleted {deleted} orphan image file(s) from {FIG_ROOT}")

    # Per-topic summary
    by_tp = {}
    for r in kept:
        by_tp[(r["topic"], r["paper_type"])] = by_tp.get((r["topic"], r["paper_type"]), 0) + 1
    print("\nPer-(topic, paper) counts after patch:")
    for tn in range(1, 11):
        for paper in ("HL-paper1", "HL-paper2", "HL-paper3"):
            n = by_tp.get((f"Topic {tn}", paper), 0)
            print(f"  Topic {tn:2d} {paper:11s}: {n}")

    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(kept)} records to {MANIFEST}  (was {len(records)})")


if __name__ == "__main__":
    main()
