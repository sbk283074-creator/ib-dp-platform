import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as B
import pypdfium2
BOOK_ID='PH-OX-2023'
book=next(b for b in E.BOOKS if b['id']==BOOK_ID)
pdf=pypdfium2.PdfDocument(book['path'])
for i in [706,707,708,709]:  # 0-indexed -> pdf 707..710
    page=pdf[i]
    H=float(page.get_height()); W=float(page.get_width())
    kind,gutter=B.detect_columns(page)
    figs=B.page_figure_bboxes(page)
    print(f"pdf {i+1}: cols_kind={kind} gutter={gutter} W={W:.1f} nfigs={len(figs)}")
    cfg=book.get('seg'); sc=B._seg_cfg(cfg)
    bands=B.question_bands_pdfium(page,cfg=cfg)
    print(f"   single-col bands={[(round(b[0],1),b[1]) for b in bands]}")
    if kind=='two-col' and gutter:
        left_lines=B.column_lines(page,0.0,gutter,dedup_against=None,exclude_rects=figs)
        right_lines=B.column_lines(page,gutter,W,dedup_against=[(t,tx) for (t,tx,_) in left_lines],exclude_rects=figs)
        bl=B.question_bands_from_lines(left_lines,H,cfg=cfg,ref_x=0.0,page_width=W,page=page)
        br=B.question_bands_from_lines(right_lines,H,cfg=cfg,ref_x=gutter,page_width=W,page=page)
        print(f"   two-col left_bands={[(round(b[0],1),b[1]) for b in bl]}")
        print(f"   two-col right_bands={[(round(b[0],1),b[1]) for b in br]}")
