import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as B
import pypdfium2
BOOK_ID='PH-OX-2023'
book=next(b for b in E.BOOKS if b['id']==BOOK_ID)
pdf=pypdfium2.PdfDocument(book['path'])
patterns=book.get('exercise_patterns'); cfg=book.get('seg')
sc=B._seg_cfg(cfg); det=sc.get('min_markers',3)
prev=False
print("Extended-response / continuation pages with >1 detected band (would over-split):")
bad=0
for i in range(len(pdf)):
    page=pdf[i]
    ok,hdr,kind=B.is_exercise_page_pdfium(page,patterns=patterns,min_markers=det,exclude_re=book.get('page_exclude_re'))
    if book.get('gate_numbered',True) and kind=='numbered' and not prev:
        ok=False
    if ok:
        bands=B.question_bands_pdfium(page,cfg=cfg)
        # include two-col split
        k,g=B.detect_columns(page)
        nb=len(bands)
        if k=='two-col' and g:
            figs=B.page_figure_bboxes(page)
            ll=B.column_lines(page,0.0,g,exclude_rects=figs)
            rl=B.column_lines(page,g,float(page.get_width()),exclude_rects=figs)
            bl=B.question_bands_from_lines(ll,float(page.get_height()),cfg=cfg,ref_x=0.0,page_width=float(page.get_width()),page=page)
            br=B.question_bands_from_lines(rl,float(page.get_height()),cfg=cfg,ref_x=g,page_width=float(page.get_width()),page=page)
            nb=len(bl)+len(br)
        if nb>1:
            bad+=1
            print(f"  pdf {i+1}: kind={kind} hdr={hdr!r} bands={nb}")
    prev=ok
print("total over-split exercise pages:", bad)
