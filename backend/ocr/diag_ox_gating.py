"""Validate PH-OX-2023 gating (is_exercise_page_pdfium + question_bands_pdfium)
on a range of PDF pages, replicating extract_books.py's exact call site.

Oxford offset: printed = pdf - 8.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as B
import pypdfium2 as pdfium

BOOK_ID = 'PH-OX-2023'
PDF_LO, PDF_HI = 660, 720  # PDF page range (1-indexed)

book = next(b for b in E.BOOKS if b['id'] == BOOK_ID)
path = book['path']
patterns = book.get('exercise_patterns')
cfg = book.get('seg')
sc = B._seg_cfg(cfg)
det_min_markers = sc.get('min_markers', 3)
gate_numbered = book.get('gate_numbered', True)
exclude_re = book.get('page_exclude_re')

print(f"book={BOOK_ID} path exists={os.path.exists(path)}")
print(f"det_min_markers={det_min_markers} gate_numbered={gate_numbered}")
print(f"exclude_re={exclude_re!r}")
print(f"patterns={patterns}")
print()

pdf = pdfium.PdfDocument(path)
prev_classified = False
for i in range(PDF_LO - 1, PDF_HI):
    page = pdf[i]
    try:
        ok, hdr, kind = B.is_exercise_page_pdfium(
            page, patterns=patterns, min_markers=det_min_markers,
            exclude_re=exclude_re)
    except Exception as e:
        print(f"p{i+1:4d} (printed {i-7:4d}) DETECT-FAIL {e}")
        prev_classified = False
        continue
    # replicate textbook gate
    if gate_numbered and kind == 'numbered' and not prev_classified:
        ok = False
    n_bands = 0
    bands = []
    if ok:
        try:
            bands = B.question_bands_pdfium(page, cfg=cfg)
        except Exception as e:
            print(f"p{i+1:4d} (printed {i-7:4d}) BANDS-FAIL {e}")
            bands = []
        n_bands = len(bands)
    accepted = ok
    prev_classified = accepted
    flag = ''
    if i + 1 in (681, 682, 689, 697, 702, 709, 713, 714, 715, 717):
        flag = '  <-- REPORTED'
    print(f"pdf {i+1:4d} (printed {i-7:4d}) ok={ok!s:5} kind={str(kind):12} "
          f"hdr={hdr!r:32} bands={n_bands} {flag}")
    if accepted and bands:
        nums = [b[0] for b in bands]
        print(f"        qnums={nums}")
