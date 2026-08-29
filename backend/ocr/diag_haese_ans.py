import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as BB
import pypdfium2
BOOK_ID='MA-HAESE-CORE1'
book=next(b for b in E.BOOKS if b['id']==BOOK_ID)
apdf=pypdfium2.PdfDocument(book['answer_path'])
print("Haese WORKED SOLUTIONS pages:", len(apdf))
REVIEW_RE=re.compile(r'Review set\s+(\d+[A-Z]?)', re.I)
seen=set()
for i in range(len(apdf)):
    page=apdf[i]
    for top,t,_x in BB.pdfium_lines(page, tol=8.0):
        m=REVIEW_RE.search(t)
        if m and t not in seen:
            seen.add(t)
            print(f"  ans pdf p{i+1}: {t!r}")
            break
