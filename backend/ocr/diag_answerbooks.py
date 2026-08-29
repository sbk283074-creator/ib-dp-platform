"""Research the structure of the two companion answer/solution books (fast
text extraction via page.get_text())."""
import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import pypdfium2 as pdfium

def fast_text(page):
    try:
        return page.get_text()
    except Exception:
        return ''

def show(pdf, label, find_re, limit=None, topn=3):
    print(f"\n########## {label} ##########")
    print(f"file: {pdf}")
    if not os.path.exists(pdf):
        print("  !! FILE NOT FOUND"); return
    doc = pdfium.PdfDocument(pdf)
    N = len(doc)
    rng = range(N) if limit is None else range(0, min(limit, N))
    print(f"  pages={N} (scanning {limit or N})")
    hits = 0
    for i in rng:
        txt = fast_text(doc[i])
        if find_re.search(txt):
            hits += 1
            if hits <= topn:
                print(f"  --- match on PDF p{i+1} ---")
                for ln in txt.splitlines()[:16]:
                    print("    |", ln)
    print(f"  total matches in scan range: {hits}")

# 1. Haese worked solutions: find Review set 17B (should be late in book)
hb = next(b for b in E.BOOKS if b['id']=='MA-HAESE-CORE1')
show(hb['answer_path'], 'HAESE WORKED SOLUTIONS (Review set 17B)', re.compile(r'Review set 17B', re.I), limit=900)

# 2. Oxford answers: Theme headers (front) + 'Practice questions - Page N'
ob = next(b for b in E.BOOKS if b['id']=='PH-OX-2023')
show(ob['answer_path'], 'OXFORD ANSWERS (Theme header, first 40pp)', re.compile(r'^\s*Theme\s+[A-Z]', re.I|re.M), limit=40, topn=3)
show(ob['answer_path'], 'OXFORD ANSWERS (Practice questions - Page N, first 80pp)', re.compile(r'Practice questions\s*[–-]\s*Page', re.I), limit=80, topn=2)
