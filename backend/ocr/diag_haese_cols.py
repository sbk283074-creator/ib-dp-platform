import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as B
import pypdfium2
BOOK_ID='MA-HAESE-CORE1'
book=next(b for b in E.BOOKS if b['id']==BOOK_ID)
pdf=pypdfium2.PdfDocument(book['path'])
patterns=book.get('exercise_patterns') or E.PRACTICE_PATTERNS
cfg=book.get('seg'); sc=B._seg_cfg(cfg)
det_min_markers=sc.get('min_markers',3)
two_col_pages=0; single_ex_pages=0; total_ex=0
samples=[]
for i in range(len(pdf)):
    page=pdf[i]
    ok,hdr,kind=B.is_exercise_page_pdfium(page,patterns=patterns,min_markers=det_min_markers,exclude_re=book.get('page_exclude_re'))
    if not ok: continue
    total_ex+=1
    ck,gutter=B.detect_columns(page)
    if ck=='two-col':
        two_col_pages+=1
    else:
        single_ex_pages+=1
        if len(samples)<15:
            samples.append((i+1,hdr,kind))
print(f"{BOOK_ID}: exercise pages={total_ex} two-col={two_col_pages} single={single_ex_pages}")
print("single exercise-page samples (pdf_page, hdr, kind):")
for s in samples: print("  ",s)
