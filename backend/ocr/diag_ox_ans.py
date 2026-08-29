import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as B
import pypdfium2
BOOK_ID='PH-OX-2023'
book=next(b for b in E.BOOKS if b['id']==BOOK_ID)
ans_path=book['answer_path']
print("answer_path exists:", os.path.exists(ans_path), ans_path)
apdf=pypdfium2.PdfDocument(ans_path)
print("answer pdf pages:", len(apdf))
# dump first ~12 pages' text lines to understand structure
for i in range(min(12, len(apdf))):
    page=apdf[i]
    lines=[t for _,t,_ in B.pdfium_lines(page)]
    print(f"--- ANS pdf page {i+1} (lines={len(lines)}) ---")
    for ln in lines[:30]:
        print("   ", repr(ln))
