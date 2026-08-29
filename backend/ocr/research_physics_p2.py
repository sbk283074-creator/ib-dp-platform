#!/usr/bin/env python3
"""Session 5 research only: Physics HL Paper 2. No extraction/DB writes."""
import os,re,json
import pypdfium2 as pdfium

BASE='/Users/lucas.ma/Downloads/dp learning/Physics-HL-Past Papers&Mark Schemes(1999.05~2025.11)'
YEAR_RE=re.compile(r'^20(?:1[6-9]|2[0-5])')
QP_HEAD=re.compile(r'(?:^|[\r\n\ufffe])\s*(\d{1,2})\.(?!\d)\s+(?=[A-Z(])')
# Mark-scheme table rows. Both forms occur: "1. a" and "1 a i".
# Require a real subpart token after a no-dot number; this avoids numeric
# formula lines such as `2` followed by `el` being mistaken for Q2.
MS_ROW=re.compile(r'(?:^|[\r\n\ufffe])\s*(\d{1,2})(?:\.(?=\s)|(?=[ \t]+(?:\([a-z]\)|[a-z](?:[ \t\r\n]|$))))\s+')

def load(path):
 d=pdfium.PdfDocument(path)
 pages=[d[i].get_textpage().get_text_range() for i in range(len(d))]
 full='\n'.join(pages); imgs=[]
 for i in range(len(d)):
  for o in d[i].get_objects():
   try:
    if o.type==3: imgs.append((i+1,o.get_px_size(),o.get_bounds()))
   except Exception: pass
 d.close(); return pages,full,imgs

def q_hits(full):
 out=[]; exp=1
 for m in QP_HEAD.finditer(full):
  n=int(m.group(1))
  if n==exp: out.append(n); exp+=1
 return out

def ms_hits(full,expected):
 # Search after the first actual answer table header, not rubric instructions.
 poss=[m.start() for m in re.finditer(r'(?m)^\s*(?:Question|Q)\s+Answers\s+Notes\s+Total',full)]
 start=poss[0] if poss else 0
 out=[]; exp=1
 for m in MS_ROW.finditer(full,start):
  n=int(m.group(1))
  if n==exp: out.append(n); exp+=1
  if exp>expected: break
 return out,start

def main():
 rows=[]
 for d in sorted(os.listdir(BASE)):
  dp=os.path.join(BASE,d)
  if not os.path.isdir(dp) or not YEAR_RE.match(d): continue
  for f in sorted(os.listdir(dp)):
   lf=f.lower()
   if 'paper_2' not in lf or 'markscheme' in lf or any(x in lf for x in ('french','spanish','german')): continue
   ms=f[:-4]+'_markscheme.pdf'
   rows.append((d,f,ms,os.path.exists(os.path.join(dp,ms))))
 print('INVENTORY_COUNT',len(rows))
 for d,f,ms,ok in rows: print(json.dumps({'dir':d,'qp':f,'ms':ms,'ms_exists':ok},ensure_ascii=False))
 print('\nPROBE_TABLE')
 for d,f,ms,ok in rows:
  qp,qt,qi=load(os.path.join(BASE,d,f)); mp,mt,mi=load(os.path.join(BASE,d,ms))
  q=q_hits(qt); m,anchor=ms_hits(mt,len(q))
  q_pua=sum(0xE000<=ord(c)<=0xF8FF for c in qt); m_pua=sum(0xE000<=ord(c)<=0xF8FF for c in mt)
  q_sp=sum(1 for p in qp if 'Please do not write on this page' in p and len(p.strip())<180)
  m_sp=sum(1 for p in mp if 'Please do not write on this page' in p and len(p.strip())<180)
  print(f'{d}|{f}|QP_pages={len(qp)}|N={len(q)}|MS_pages={len(mp)}|MS_res={len(m)}|anchor={anchor}|QP_img={len(qi)}|MS_img={len(mi)}|PUA={q_pua}/{m_pua}|spacer={q_sp}/{m_sp}')
 print('\nREPRESENTATIVE_HEADERS')
 for d,f,ms,ok in rows:
  if d in ('2016 May Examination Session','2021 May 物理HL','2025.05','2025.11'):
   qp,qt,qi=load(os.path.join(BASE,d,f)); mp,mt,mi=load(os.path.join(BASE,d,ms)); q=q_hits(qt); mh,anchor=ms_hits(mt,len(q))
   print('\n---',d,f,'N=',len(q),'---')
   print('QP headers:',[x[:120] for x in qt.splitlines() if re.match(r'^\s*\d{1,2}\.\s+',x)][:8])
   print('MS first rows:',[x[:120] for x in mt[anchor:].splitlines() if re.match(r'^\s*\d{1,2}\.?\s+[a-z]',x)][:8])

if __name__=='__main__': main()
