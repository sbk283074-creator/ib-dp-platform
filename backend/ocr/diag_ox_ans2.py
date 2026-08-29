import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as BB
import pypdfium2
BOOK_ID='PH-OX-2023'
book=next(b for b in E.BOOKS if b['id']==BOOK_ID)
apdf=pypdfium2.PdfDocument(book['answer_path'])
HDR_RE=re.compile(r'Practice questions\s+[–-]\s*Pages?\s*(\d+)(?:\s*[–-]\s*(\d+))?', re.I)
EXT_RE=re.compile(r'Extended Response Questions\s+[–-]\s*Pages?\s*(\d+)', re.I)
QN_RE=re.compile(r'^\s*(\d+)\s+[a-zA-Z]')
cur=None
for i in range(len(apdf)):
    page=apdf[i]
    lines=[(top,t) for top,t,_ in BB.pdfium_lines(page)]
    for top,t in lines:
        m=HDR_RE.search(t)
        if m:
            cur=(int(m.group(1)), int(m.group(2)) if m.group(2) else int(m.group(1)))
            print(f"ANS pdf p{i+1}: HDR printed={cur}")
            continue
        m=EXT_RE.search(t)
        if m:
            cur=('EXT', int(m.group(1)))
            print(f"ANS pdf p{i+1}: EXT header printed={m.group(1)}")
            continue
        if cur and QN_RE.match(t):
            print(f"   p{i+1} qnum={QN_RE.match(t).group(1)} top={top:.1f} cur={cur} text={t[:50]!r}")
