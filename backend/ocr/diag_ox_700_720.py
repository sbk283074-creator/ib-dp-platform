import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as B
import pypdfium2 as pdfium

BOOK_ID = 'PH-OX-2023'
PDF_LO, PDF_HI = 700, 720
book = next(b for b in E.BOOKS if b['id'] == BOOK_ID)
path = book['path']
patterns = book.get('exercise_patterns'); cfg = book.get('seg')
sc = B._seg_cfg(cfg)
det_min_markers = sc.get('min_markers', 3)
gate_numbered = book.get('gate_numbered', True)
exclude_re = book.get('page_exclude_re')
pdf = pdfium.PdfDocument(path)
prev = False
for i in range(PDF_LO - 1, PDF_HI):
    page = pdf[i]
    ok, hdr, kind = B.is_exercise_page_pdfium(page, patterns=patterns, min_markers=det_min_markers, exclude_re=exclude_re)
    if gate_numbered and kind == 'numbered' and not prev:
        ok = False
    bands = []
    if ok:
        bands = B.question_bands_pdfium(page, cfg=cfg)
    prev = ok
    qs = [b[1] for b in bands] if bands else []
    print(f"pdf {i+1:4d} ok={ok!s:5} kind={str(kind):12} hdr={hdr!r:30} nbands={len(bands)} qnums={qs} bands={[(round(b[0],1),b[1]) for b in bands]}")
