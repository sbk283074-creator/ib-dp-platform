#!/usr/bin/env python3
"""
Session 3 extractor — Math AA HL Paper 3 (past papers, 2021 May -> 2024.11).
Text-layer extraction (pypdfium2). Fork of the validated P2 extractor with the
P3-specific QP header fix: accepts both "Maximum mark" and "Maximum marks".
Produces backend/data/paper_aa_p3_manifest.json (question text + rendered
question_image, answer text + rendered answer_image) and writes JPGs to
backend/public/figures/paper_aa_hl_p3/<slug>/.

Per FINAL_PLAN Rule #5, every record keeps BOTH the screenshot (question_image /
answer_image) AND the normalized text. Idempotent: stable ids; the companion Node
importer does DELETE+INSERT per paper. No DB writes happen here — only files + manifest.
"""
import pypdfium2 as pdfium, os, re, json
from datetime import datetime, timezone

BASE = "/Users/lucas.ma/Downloads/dp learning/IB 数学 AA  HL 历年真题"
ROOT = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform"
FIG  = os.path.join(ROOT, "backend/public/figures")
MANIFEST = os.path.join(ROOT, "backend/data/paper_aa_p3_manifest.json")

DPI = 150
SCALE = DPI / 72.0
TEXT, PATH, IMAGE = 1, 2, 3

# (qp_rel, slug, pretty_source)
PAPERS = [
 ("IB 数学 HL 真题（2006-23）/2021 May/IB 数学 AA  HL  2021.05/Mathematics_analysis_and_approaches_paper_3__TZ1_HL.pdf", "2021May_TZ1", "2021 May TZ1"),
 ("IB 数学 HL 真题（2006-23）/2021 May/IB 数学 AA  HL  2021.05/Mathematics_analysis_and_approaches_paper_3__TZ2_HL.pdf", "2021May_TZ2", "2021 May TZ2"),
 ("IB 数学 HL 真题（2006-23）/2021 Nov/Mathematics_analysis_and_approaches_paper_3__HL.pdf", "2021Nov", "2021 Nov"),
 ("IB 数学 HL 真题（2006-23）/2022 May/Mathematics_analysis_and_approaches_paper_3__TZ1_HL.pdf", "2022May_TZ1", "2022 May TZ1"),
 ("IB 数学 HL 真题（2006-23）/2022 May/Mathematics_analysis_and_approaches_paper_3__TZ2_HL.pdf", "2022May_TZ2", "2022 May TZ2"),
 ("IB 数学 HL 真题（2006-23）/2022 Nov/Mathematics_analysis_and_approaches_paper_3__HL.pdf", "2022Nov", "2022 Nov"),
 ("IB 数学 HL 真题（2006-23）/2023 May/Mathematics_analysis_and_approaches_paper_3__TZ1_HL.pdf", "2023May_TZ1", "2023 May TZ1"),
 ("IB 数学 HL 真题（2006-23）/2023 May/Mathematics_analysis_and_approaches_paper_3__TZ2_HL.pdf", "2023May_TZ2", "2023 May TZ2"),
 ("IB 数学 HL 真题（2006-23）/2023 Nov/Mathematics_analysis_and_approaches_paper_3__HL.pdf", "2023Nov", "2023 Nov"),
 ("2024.5HL/Mathematics_analysis_and_approaches_paper_3__TZ1_HL.pdf", "2024_5_TZ1", "2024 May TZ1"),
 ("2024.5HL/Mathematics_analysis_and_approaches_paper_3__TZ2_HL.pdf", "2024_5_TZ2", "2024 May TZ2"),
 ("2024.11HL/Mathematics_analysis_and_approaches_paper_3__HL.pdf", "2024_11", "2024 Nov"),
]

# P3 uses both "Maximum mark" and "Maximum marks" across the corpus.
qhead_re = re.compile(r'(?m)^\s*(\d+)\.\s*\[Maximum marks?: (\d+)\]')
# MS question-boundary detector. FOUR formats (validated on P1/P2/P3):
#   1. "Question 10" / "Question 10 continued"            -> g1
#   2. "10." (dot, not a decimal)                          -> g2
#   3. "2 METHOD 1" (number + space + METHOD, NO dot)     -> g3
#   4. "6 (a) attempt ..." (no dot, space + "(a)")       -> g4
# Strict num==expected walker guards against mid-question stray N (a) subparts.
numre = re.compile(r'(?m)^\s*(?:Question\s+(\d+)|(\d+)\.(?!\d)\s|(\d+)\s+METHOD\b|(\d+)\s+\([a-z]\))')

CMDS = ["Hence or otherwise","Hence find","Hence show","Hence determine","Hence","Find the probability","Find the exact","Find the value","Find an expression",
        "Find the coordinates","Find the equation","Find","Show that","Show","Determine","Write down","Prove","Sketch","State","Calculate","Solve","Express",
        "Describe","Explain","Deduce","Verify","Using","Given that","Find the"]

def load(path):
    d = pdfium.PdfDocument(path)
    pages = [d[i].get_textpage().get_text_range() for i in range(len(d))]
    full = "\n".join(pages)
    return d, pages, full

def page_of(pos, off):
    for i in range(len(off)-1):
        if off[i] <= pos < off[i+1]:
            return i
    return len(off)-2

def clean(text):
    out = []
    for line in text.splitlines():
        s = line.strip()
        if re.match(r'^–\s*\d+\s*–', s): continue
        if 'MATHX/HP1' in s: continue
        if re.match(r'^\d{2}EP\d{2}$', s): continue
        if re.search(r'M\d\d/\d/MATHX', s): continue
        out.append(line)
    return "\n".join(out)

# --- Math text normalization (Symbol / MT Extra PUA -> Unicode) ---
_PUA_MAP_REF = None  # placeholder (see normalize_math below)
_FRAC_PAIR = re.compile(r'[\uf0e6-\uf0f2][\uf0f6-\uf0fc]')
_DELIM_PAIR = re.compile(
    r'([\uf8eb\uf8ec\uf8ed\uf8ee\uf8ef\uf8f0\uf8f1\uf8f3])'
    r'([\uf8f6\uf8f7\uf8f8\uf8f9\uf8fa\uf8fb\uf8f2\uf8f4])'
)
_DELIM_ADJ = {
    (0xF8EB, 0xF8F6): '[', (0xF8EC, 0xF8F7): ']',
    (0xF8ED, 0xF8F8): '(', (0xF8EE, 0xF8F9): ')',
    (0xF8EF, 0xF8FA): '{', (0xF8F0, 0xF8FB): '}',
    (0xF8F1, 0xF8F2): '≤', (0xF8F3, 0xF8F4): '≤',
}

PUA_MAP = {
    0xF041:'Α',0xF042:'Β',0xF043:'Χ',0xF044:'Δ',0xF045:'Ε',0xF046:'Φ',0xF047:'Γ',0xF048:'Θ',
    0xF049:'Ι',0xF04A:'ϑ',0xF04B:'Κ',0xF04C:'Λ',0xF04D:'Μ',0xF04E:'Ν',0xF04F:'Ο',0xF050:'Π',
    0xF051:'Θ',0xF052:'Ρ',0xF053:'Σ',0xF054:'Τ',0xF055:'Υ',0xF056:'ς',0xF057:'Ω',0xF058:'Ξ',
    0xF059:'Ψ',0xF05A:'Ζ',
    0xF022:'∀',0xF024:'∃',0xF026:'∧',0xF027:'∨',0xF02A:'∗',
    0xF03C:'≤',0xF03E:'≥',0xF040:'≈',0xF05B:'[',0xF05C:'∴',0xF05D:']',
    0xF05E:'↑',0xF05F:'↓',0xF060:'←',
    0xF061:'α',0xF062:'β',0xF063:'χ',0xF064:'δ',0xF065:'ε',0xF066:'φ',0xF067:'γ',0xF068:'η',
    0xF069:'ι',0xF06A:'ϕ',0xF06B:'κ',0xF06C:'λ',0xF06D:'μ',0xF06E:'ν',0xF06F:'ο',0xF070:'π',
    0xF071:'θ',0xF072:'ϑ',0xF073:'σ',0xF074:'τ',0xF075:'υ',0xF076:'ϑ',0xF077:'ω',0xF078:'ξ',
    0xF079:'ψ',0xF07A:'ζ',0xF07B:'{',0xF07C:'|',0xF07D:'}',
    0xF0A1:'ℝ',0xF0A2:'ℤ',0xF0A3:'ℂ',0xF0A4:'ℕ',0xF0A5:'ℚ',
    0xF0B0:'°',0xF0B1:'∓',0xF0B3:'≥',0xF0B4:'×',0xF0B5:'∝',0xF0B6:'∇',0xF0B7:'·',0xF0B8:'÷',
    0xF0B9:'≤',0xF0BA:'→',0xF0BB:'↔',0xF0BC:'⇒',0xF0BD:'⇔',0xF0C7:'|',
    0xF0CE:'∂',0xF0D5:'∑',0xF0D6:'∏',0xF0D7:'⋅',0xF0DE:'∫',0xF0E5:'∏',
    0xF0E6:'',0xF0E7:'',0xF0E8:'',0xF0E9:'',0xF0EA:'',0xF0EB:'',
    0xF0EC:'',0xF0ED:'',0xF0EE:'',0xF0EF:'',0xF0F0:'',0xF0F1:'',0xF0F2:'',
    0xF0F6:'',0xF0F7:'',0xF0F8:'',0xF0F9:'',0xF0FA:'',0xF0FB:'',0xF0FC:'',
    0xF8E6:'|',0xF8EB:'[',0xF8F6:'[',0xF8EC:']',0xF8F7:']',
    0xF8ED:'(',0xF8F8:'(',0xF8EE:')',0xF8F9:')',
    0xF8EF:'{',0xF8FA:'{',0xF8F0:'}',0xF8FB:'}',
    0xF8F1:'≤',0xF8F2:'≤',0xF8F3:'≤',0xF8F4:'≤',
}

def normalize_math(text):
    if not text:
        return text
    def _adj(m):
        a, b = ord(m.group(1)), ord(m.group(2))
        return _DELIM_ADJ.get((a, b), PUA_MAP.get(a, '') + PUA_MAP.get(b, ''))
    text = _DELIM_PAIR.sub(_adj, text)
    text = _FRAC_PAIR.sub('/', text)
    text = ''.join(PUA_MAP.get(ord(c), c) for c in text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\n[ \t]+', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text

def extract_command(text):
    m = re.match(r'^\s*\d+\.\s*\[Maximum marks?: \d+\]\s*\n?(.*)', text.strip(), re.S)
    body = m.group(1) if m else text
    body1 = body.strip().split('\n')[0]
    for c in CMDS:
        if body1.startswith(c) or body[:80].startswith(c):
            return c
    return None

def render_page(doc, pi, relp):
    outp = os.path.join(FIG, relp)
    if os.path.exists(outp):
        return relp  # already rendered (idempotent re-runs)
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    pil = doc[pi].render(scale=SCALE).to_pil()
    pil.save(outp, "JPEG", quality=85)
    return relp

def process(qp_rel, slug, pretty):
    qd, qpages, qfull = load(os.path.join(BASE, qp_rel))
    md, mpages, mfull = load(os.path.join(BASE, qp_rel[:-4] + "_markscheme.pdf"))
    N = len(list(qhead_re.finditer(qfull)))
    qheads = list(qhead_re.finditer(qfull))
    qstarts = {int(m.group(1)): (m.start(), int(m.group(2))) for m in qheads}
    qoff = [0]
    for t in qpages: qoff.append(qoff[-1] + len(t) + 1)
    # MS segmentation: anchor after last "Presentation of candidate work", capped at N
    anc = mfull.rfind("Presentation of candidate work")
    start = anc + len("Presentation of candidate work") if anc > 0 else 0
    expected = 1; mstarts = {}
    for m in numre.finditer(mfull, start):
        num = int(m.group(1) or m.group(2) or m.group(3) or m.group(4))
        if 1 <= num <= N and num == expected:
            mstarts[num] = m.start(); expected += 1
            if expected > N: break
    moff = [0]
    for t in mpages: moff.append(moff[-1] + len(t) + 1)
    keys = sorted(qstarts)
    records = []
    for idx, n in enumerate(keys):
        qst, marks = qstarts[n]
        qend = qstarts[keys[idx+1]][0] if idx+1 < len(keys) else len(qfull)
        qtext = normalize_math(clean(qfull[qst:qend]))
        qps = page_of(qst, qoff)
        if idx+1 < len(keys):
            qpe = max(qps, page_of(qend, qoff) - 1)
        else:
            qpe = page_of(qend - 1, qoff)
        mst = mstarts[n]; mend = mstarts[keys[idx+1]] if idx+1 < len(keys) else len(mfull)
        mps = page_of(mst, moff)
        if idx+1 < len(keys):
            mpe = max(mps, page_of(mend, moff) - 1)
        else:
            mpe = page_of(mend - 1, moff)
        q_imgs = [render_page(qd, pi, f"paper_aa_hl_p3/{slug}/q{n:02d}_p{pi+1}.jpg") for pi in range(qps, qpe+1)]
        a_imgs = [render_page(md, pi, f"paper_aa_hl_p3/{slug}/a{n:02d}_p{pi+1}.jpg") for pi in range(mps, mpe+1)]
        atext = normalize_math(clean(mfull[mst:mend]))
        records.append({
            "id": f"MATH_AAHL_P3_{slug}_q{n:02d}",
            "subject": "Mathematics", "level": "HL", "topic": "AA HL", "subtopic": None,
            "paper_type": "Paper 3", "command_term": extract_command(qfull[qst:qend]),
            "marks": int(marks), "difficulty": None,
            "question": qtext, "figure": None, "answer": atext, "explanation": None,
            "source": f"AA HL P3 · {pretty}", "tags": [], "authored_by": "ib",
            "knowledge_point_ids": [], "answer_figure": None,
            "question_image": ",".join(q_imgs), "answer_image": ",".join(a_imgs),
            "figure_image": None, "book_id": None, "source_type": "paper",
            "category": "past", "review_status": "new",
        })
    qd.close(); md.close()
    return records

def main():
    os.makedirs(FIG, exist_ok=True)
    all_recs = []
    for qp_rel, slug, pretty in PAPERS:
        recs = process(qp_rel, slug, pretty)
        all_recs.extend(recs)
        print(f"  {slug}: {len(recs)} questions")
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(all_recs, f, ensure_ascii=False, indent=1)
    print(f"\nTOTAL questions: {len(all_recs)}")
    print(f"Manifest -> {MANIFEST}")

if __name__ == "__main__":
    main()
