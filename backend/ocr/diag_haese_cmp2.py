import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as B
import pypdfium2
book=next(b for b in E.BOOKS if b['id']=='MA-HAESE-CORE1')
pdf=pypdfium2.PdfDocument(book['path'])
cfg=book.get('seg'); sc=B._seg_cfg(cfg)
for i in range(469,500):
    if i>=len(pdf): break
    page=pdf[i]
    ok,hdr,kind=B.is_exercise_page_pdfium(page,patterns=book.get('exercise_patterns'),min_markers=sc.get('min_markers',3),exclude_re=book.get('page_exclude_re'))
    if not ok: continue
    tbands=B.question_bands_pdfium(page,cfg=cfg)
    vt=B.visual_qnum_tops(page, dpi=200, x_frac_lo=0.0, x_frac_hi=0.14,
                          min_h=6,max_h=42,min_w=4,max_w=60, min_sat=80, y_min=0.10)
    uniq=[]
    for v in vt:
        if not uniq or v-uniq[-1]>4: uniq.append(v)
    ty=[round(y,0) for n,y,_ in tbands]
    flag = '  <-- COLORED QNUMS MISSED' if len(uniq) > len(tbands) else ''
    print(f"raw {i+1}: text={len(tbands)} colored_vis={len(uniq)} text_y={ty} vis_y={[round(u,0) for u in uniq]}{flag}")
