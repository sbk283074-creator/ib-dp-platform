import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as BB
import pypdfium2
BOOK_ID='PH-OX-2023'
book=next(b for b in E.BOOKS if b['id']==BOOK_ID)
apdf=pypdfium2.PdfDocument(book['answer_path'])
# print answer pdf pages 50..53 (extended response region) lines
for i in range(49, min(53,len(apdf))):
    page=apdf[i]
    lines=[(top,t) for top,t,_ in BB.pdfium_lines(page)]
    print(f"=== ANS pdf page {i+1} ===")
    for top,t in lines:
        print(f"   top={top:7.1f} {t!r}")
