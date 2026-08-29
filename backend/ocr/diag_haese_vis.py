import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as B
import pypdfium2
book=next(b for b in E.BOOKS if b['id']=='MA-HAESE-CORE1')
pdf=pypdfium2.PdfDocument(book['path'])
i=482  # raw pdf 483 = printed 482
page=pdf[i]
W=float(page.get_width()); H=float(page.get_height())
print("page W,H=",W,H)
for xhi in (0.10,0.13,0.16):
    for mw in (8,12,16):
        vt=B.visual_qnum_tops(page, dpi=200, x_frac_lo=0.0, x_frac_hi=xhi,
                              min_h=6, max_h=42, min_w=mw, max_w=55)
        uniq=[]
        for v in vt:
            if not uniq or v-uniq[-1]>4: uniq.append(v)
        print(f"  xhi={xhi} min_w={mw}: -> {len(uniq)} tops {[round(u,1) for u in uniq]}")
