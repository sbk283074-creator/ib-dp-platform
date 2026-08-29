"""Refined Haese Core 1 merge detector: flag pages where the detected qnum
sequence has an INTRA-PAGE non-consecutive jump (gap>1), which means a colored
/outlined qnum was missed and the neighbouring questions merged. The trailing
band (extends to page bottom) is NOT counted as a merge.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as B
import pypdfium2 as pdfium

BOOK = next(b for b in E.BOOKS if b['id'] == 'MA-HAESE-CORE1')
doc = pdfium.PdfDocument(BOOK['path'])
patterns = BOOK.get('exercise_patterns') or E.PRACTICE_PATTERNS
merges = []
for i in range(len(doc)):
    page = doc[i]
    try:
        ok, hdr, kind = B.is_exercise_page_pdfium(page, patterns=patterns, min_markers=3)
    except Exception:
        continue
    if not ok:
        continue
    try:
        bands = B.question_bands_pdfium(page, cfg=BOOK.get('seg'))
    except Exception:
        continue
    nums = [b[0] for b in bands if isinstance(b[0], int)]
    if len(nums) < 3:
        continue
    # intra-page gaps > 1 (ignore the very last band's implied jump to H)
    gaps = []
    for a, b in zip(nums, nums[1:]):
        if b - a > 1:
            gaps.append((a, b))
    if gaps:
        merges.append((i + 1, hdr, nums, gaps))
print(f"pages with intra-page qnum gaps (missed colored qnum -> merged): {len(merges)}")
for pg, hdr, nums, gaps in merges:
    print(f"  PDF p{pg:3d} hdr={hdr!r:22} seq={nums} gaps={gaps}")
