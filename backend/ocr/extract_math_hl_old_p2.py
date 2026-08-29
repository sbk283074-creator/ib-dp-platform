#!/usr/bin/env python3
"""
Session 13 extractor - Math HL Paper 2, FULL HISTORY (2008-2020, old "Math HL" guide).
Text-layer extraction (pypdfium2). Mirrors extract_math_hl_old_p1.py: derives the
question COUNT from the markscheme, then walks the question paper by numbered
questions (1..N), pairing Q and A by question number. Same strict guard (N in 6-25,
len(qstarts)==len(mstarts)==N, ms present) so any unreliable/old-format year is
SKIPPED, never shipped broken. Per operating-contract rule #8 this is the permanent
policy for every subject: skip old/complicated-format years, don't OCR them.
Idempotent: stable ids; companion Node importer does DELETE+INSERT per paper.
"""
import pypdfium2 as pdfium, os, re, json
from datetime import datetime, timezone

BASE = "/Users/lucas.ma/Downloads/dp learning/IB 数学 AA  HL 历年真题/IB 数学 HL 真题（2006-23）"
ROOT = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform"
FIG  = os.path.join(ROOT, "backend/public/figures")
MANIFEST = os.path.join(ROOT, "backend/data/paper_aa_p2_old_manifest.json")

DPI = 150
SCALE = DPI / 72.0

numre = re.compile(r'(?m)^\s*(?:Question\s+(\d+)|(\d+)\.(?!\d)\s|(\d+)\s+METHOD\b|(\d+)\s+\([a-z]\))')
marks_re = re.compile(r'\[Maximum mark:\s*(\d+)\]|\[(\d+)\s*marks?\]', re.I)

def find_ms(qp):
    base=qp[:-4]
    for cand in (base+'_markscheme.pdf', base+'_markscheme 1.pdf', base+'_markscheme(1).pdf'):
        if os.path.exists(cand): return cand
    return None

CMDS = ["Hence or otherwise","Hence find","Hence show","Hence determine","Hence","Find the probability","Find the exact","Find the value","Find an expression",
        "Find the coordinates","Find the equation","Find","Show that","Show","Determine","Write down","Prove","Sketch","State","Calculate","Solve","Express",
        "Describe","Explain","Deduce","Verify","Using","Given that","Find the"]

_FRAC_PAIR = re.compile(r'[\uf0e6-\uf0f2][\uf0f6-\uf0fc]')
_DELIM_PAIR = re.compile(r'([\uf8eb\uf8ec\uf8ed\uf8ee\uf8ef\uf8f0\uf8f1\uf8f3])([\uf8f6\uf8f7\uf8f8\uf8f9\uf8fa\uf8fb\uf8f2\uf8f4])')
_DELIM_ADJ = {(0xF8EB,0xF8F6):'[',(0xF8EC,0xF8F7):']',(0xF8ED,0xF8F8):'(',(0xF8EE,0xF8F9):')',(0xF8EF,0xF8FA):'{',(0xF8F0,0xF8FB):'}',(0xF8F1,0xF8F2):'≤',(0xF8F3,0xF8F4):'≤'}
PUA_MAP = {
    0xF041:'Α',0xF042:'Β',0xF043:'Χ',0xF044:'Δ',0xF045:'Ε',0xF046:'Φ',0xF047:'Γ',0xF048:'Θ',0xF049:'Ι',0xF04A:'ϑ',0xF04B:'Κ',0xF04C:'Λ',0xF04D:'Μ',0xF04E:'Ν',0xF04F:'Ο',0xF050:'Π',0xF051:'Θ',0xF052:'Ρ',0xF053:'Σ',0xF054:'Τ',0xF055:'Υ',0xF056:'ς',0xF057:'Ω',0xF058:'Ξ',0xF059:'Ψ',0xF05A:'Ζ',
    0xF022:'∀',0xF024:'∃',0xF026:'∧',0xF027:'∨',0xF02A:'∗',0xF03C:'≤',0xF03E:'≥',0xF040:'≈',0xF05B:'[',0xF05C:'∴',0xF05D:']',0xF05E:'↑',0xF05F:'↓',0xF060:'←',
    0xF061:'α',0xF062:'β',0xF063:'χ',0xF064:'δ',0xF065:'ε',0xF066:'φ',0xF067:'γ',0xF068:'η',0xF069:'ι',0xF06A:'ϕ',0xF06B:'κ',0xF06C:'λ',0xF06D:'μ',0xF06E:'ν',0xF06F:'ο',0xF070:'π',0xF071:'θ',0xF072:'ϑ',0xF073:'σ',0xF074:'τ',0xF075:'υ',0xF076:'ϑ',0xF077:'ω',0xF078:'ξ',0xF079:'ψ',0xF07A:'ζ',0xF07B:'{',0xF07C:'|',0xF07D:'}',
    0xF0A1:'ℝ',0xF0A2:'ℤ',0xF0A3:'ℂ',0xF0A4:'ℕ',0xF0A5:'ℚ',0xF0B0:'°',0xF0B1:'∓',0xF0B3:'≥',0xF0B4:'×',0xF0B5:'∝',0xF0B6:'∇',0xF0B7:'·',0xF0B8:'÷',0xF0B9:'≤',0xF0BA:'→',0xF0BB:'↔',0xF0BC:'⇒',0xF0BD:'⇔',0xF0C7:'|',0xF0CE:'∂',0xF0D5:'∑',0xF0D6:'∏',0xF0D7:'⋅',0xF0DE:'∫',0xF0E5:'∏',
    0xF0E6:'',0xF0E7:'',0xF0E8:'',0xF0E9:'',0xF0EA:'',0xF0EB:'',0xF0EC:'',0xF0ED:'',0xF0EE:'',0xF0EF:'',0xF0F0:'',0xF0F1:'',0xF0F2:'',0xF0F6:'',0xF0F7:'',0xF0F8:'',0xF0F9:'',0xF0FA:'',0xF0FB:'',0xF0FC:'',
    0xF8E6:'|',0xF8EB:'[',0xF8F6:'[',0xF8EC:']',0xF8F7:']',0xF8ED:'(',0xF8F8:'(',0xF8EE:')',0xF8F9:')',0xF8EF:'{',0xF8FA:'{',0xF8F0:'}',0xF8FB:'}',0xF8F1:'≤',0xF8F2:'≤',0xF8F3:'≤',0xF8F4:'≤',
}
def normalize_math(text):
    if not text: return text
    def _adj(m):
        a,b=ord(m.group(1)),ord(m.group(2))
        return _DELIM_ADJ.get((a,b), PUA_MAP.get(a,'')+PUA_MAP.get(b,''))
    text=_DELIM_PAIR.sub(_adj,text); text=_FRAC_PAIR.sub('/',text)
    text=''.join(PUA_MAP.get(ord(c),c) for c in text)
    text=re.sub(r'[ \t]{2,}',' ',text); text=re.sub(r'\n[ \t]+','\n',text); text=re.sub(r'\n{3,}','\n\n',text)
    return text

def clean(text):
    out=[]
    for line in text.splitlines():
        s=line.strip()
        if re.match(r'^–\s*\d+\s*–', s): continue
        if re.match(r'^M\d\d/\d+/MATH', s): continue
        if re.match(r'^\d{4}-\d{4}$', s): continue
        if re.match(r'^\d{2}EP\d{2}$', s): continue
        if re.search(r'M\d\d/\d/MATHX', s): continue
        out.append(line)
    return "\n".join(out)

def load(path):
    d=pdfium.PdfDocument(path)
    pages=[d[i].get_textpage().get_text_range() for i in range(len(d))]
    full="\n".join(pages)
    return d,pages,full

def page_of(pos, off):
    for i in range(len(off)-1):
        if off[i]<=pos<off[i+1]: return i
    return len(off)-2

def count_questions(full):
    expected=1; n=0
    for m in numre.finditer(full):
        num=int(m.group(1) or m.group(2) or m.group(3) or m.group(4))
        if 1<=num<=60 and num==expected:
            expected+=1; n=num
            if expected>60: break
    return n

def walk_starts(full, N):
    expected=1; starts={}
    for m in numre.finditer(full):
        num=int(m.group(1) or m.group(2) or m.group(3) or m.group(4))
        if 1<=num<=60 and num==expected:
            starts[num]=m.start(); expected+=1
            if N and len(starts)>=N: break
    return starts

def extract_command(text):
    body1=text.strip().split('\n')[0]
    for c in CMDS:
        if body1.startswith(c) or text[:80].startswith(c): return c
    return None

def render_page(doc, pi, relp):
    outp=os.path.join(FIG, relp)
    if os.path.exists(outp): return relp
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    doc[pi].render(scale=SCALE).to_pil().save(outp,"JPEG",quality=85)
    return relp

LANG_SKIP=["French","Spanish","German","数学"]
def discover():
    papers=[]; seen=set()
    for ydir in sorted(os.listdir(BASE)):
        m=re.match(r'^(\d{4}) (May|Nov)$', ydir)
        if not m: continue
        year,month=m.group(1),m.group(2)
        if int(year)<2008 or int(year)>2020: continue   # 2021+ AA guide handled by existing extractor
        root=os.path.join(BASE,ydir)
        for dp,dn,fn in os.walk(root):
            for f in fn:
                if not f.lower().endswith('.pdf'): continue
                if 'paper_2' not in f or 'HL' not in f or 'markscheme' in f.lower(): continue
                if any(L in f for L in LANG_SKIP): continue
                qp=os.path.join(dp,f)
                ms=find_ms(qp)
                tz='TZ1' if '_TZ1_' in f else 'TZ2' if '_TZ2_' in f else 'TZ0'
                slug=f"{year}{month}_{tz}"
                if slug in seen: continue
                seen.add(slug)
                pretty=f"{year} {month} {tz}"
                papers.append((qp, ms if ms and os.path.exists(ms) else None, slug, pretty))
    return papers

def process(qp, ms, slug, pretty):
    qd,qpages,qfull=load(qp)
    md,mpages,mfull=load(ms) if ms else (None,[],"")
    N=count_questions(mfull) if ms else 0
    if N<1: N=count_questions(qfull)
    qstarts=walk_starts(qfull,N)
    mstarts=walk_starts(mfull,N) if ms else {}
    if not ms or N<6 or N>25 or len(qstarts)!=N or len(mstarts)!=N:
        print(f"  SKIP {slug}: ms={'Y' if ms else 'N'} N={N} q={len(qstarts)} m={len(mstarts) if ms else 'NA'} (unreliable segmentation)")
        return []
    qoff=[0]; [qoff.append(qoff[-1]+len(t)+1) for t in qpages]
    moff=[0]; [moff.append(moff[-1]+len(t)+1) for t in mpages]
    keys=sorted(qstarts); records=[]
    for idx,n in enumerate(keys):
        qst=qstarts[n]
        qend=qstarts[keys[idx+1]] if idx+1<len(keys) else len(qfull)
        qtext=normalize_math(clean(qfull[qst:qend]))
        qps=page_of(qst,qoff)
        qpe=max(qps,page_of(qend,qoff)-1) if idx+1<len(keys) else page_of(qend-1,qoff)
        mk=None; mk_m=marks_re.search(qfull[qst:qst+220])
        if mk_m: mk=int(mk_m.group(1) or mk_m.group(2))
        atext=None; a_imgs=[]
        if ms and n in mstarts:
            mst=mstarts[n]; mend=mstarts[keys[idx+1]] if idx+1<len(keys) else len(mfull)
            atext=normalize_math(clean(mfull[mst:mend]))
            mps=page_of(mst,moff)
            mpe=max(mps,page_of(mend,moff)-1) if idx+1<len(keys) else page_of(mend-1,moff)
            a_imgs=[render_page(md,pi,f"paper_aa_hl_p2/{slug}/a{n:02d}_p{pi+1}.jpg") for pi in range(mps,mpe+1)]
        q_imgs=[render_page(qd,pi,f"paper_aa_hl_p2/{slug}/q{n:02d}_p{pi+1}.jpg") for pi in range(qps,qpe+1)]
        records.append({
            "id":f"MATH_AAHL_P2_{slug}_q{n:02d}",
            "subject":"Mathematics","level":"HL","topic":"AA HL","subtopic":None,
            "paper_type":"Paper 2","command_term":extract_command(qfull[qst:qend]),
            "marks":mk,"difficulty":None,
            "question":qtext,"figure":None,"answer":atext,"explanation":None,
            "source":f"HL P2 · {pretty}","tags":[],"authored_by":"ib",
            "knowledge_point_ids":[],"answer_figure":None,
            "question_image":",".join(q_imgs),"answer_image":",".join(a_imgs),
            "figure_image":None,"book_id":None,"source_type":"paper",
            "category":"past","review_status":"new",
        })
    qd.close()
    if md: md.close()
    return records

def main():
    os.makedirs(FIG, exist_ok=True)
    all_recs=[]
    for qp,ms,slug,pretty in discover():
        recs=process(qp,ms,slug,pretty)
        all_recs.extend(recs)
        print(f"  {slug}: {len(recs)} questions")
    with open(MANIFEST,"w",encoding="utf-8") as f:
        json.dump(all_recs,f,ensure_ascii=False,indent=1)
    print(f"\nTOTAL questions (2008-2020 P2): {len(all_recs)}")
    print(f"Manifest -> {MANIFEST}")

if __name__=="__main__":
    main()
