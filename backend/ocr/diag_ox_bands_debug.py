import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as B
import pypdfium2
BOOK_ID='PH-OX-2023'
book=next(b for b in E.BOOKS if b['id']==BOOK_ID)
pdf=pypdfium2.PdfDocument(book['path'])
cfg=book.get('seg'); sc=B._seg_cfg(cfg)
print("sc=",sc)
page=pdf[706]  # pdf 707
H=float(page.get_height()); W=float(page.get_width())
gutter=246.0
right_lines=B.column_lines(page,gutter,W,dedup_against=[])
# replicate question_bands_from_lines candidate logic manually for debug
margin=sc['qnum_margin']*W
print("margin(pt)=",margin, "ref_x=gutter=",gutter)
cands=[]
for top,text,x0 in right_lines:
    if top<0: continue
    mq=B._QUESTION_WORD_RE.search(text) if sc.get('worded_qnum') else None
    if mq and mq.start()<=16 and (x0-gutter)<=margin:
        cands.append((top,'WORD',int(mq.group(1)),repr(text))); continue
    num=B._line_start_number(text, sc['strict_qnum'])
    if num is not None:
        if (x0-gutter)>margin: continue
        if sc.get('reject_bare_digit_alone') and __import__('re').match(r'^\d{1,3}$', text.strip()):
            cands.append((top,'BARE-DROP',num,repr(text))); continue
        cands.append((top,'NUM',num,repr(text))); continue
    alt=B._line_start_number_alt_glyph(text)
    if alt is not None and (x0-gutter)<=margin:
        cands.append((top,'ALT',alt,repr(text))); continue
    if not sc.get('no_bare_dot') and B._bare_dot(text):
        cands.append((top,'DOT',None,repr(text)))
print("RIGHT candidate scan (pdf707):")
for c in cands:
    print("  ",c)
