#!/usr/bin/env python3
"""
Session 12 extractor — Math AA questions (Pestle question-bank export, 1,590 pp).
Text-layer extraction (pypdfium2). Produces a JSON manifest of 746 question records
(question text + stitched question_image, answer text + stitched answer_image) and
writes the JPGs to backend/public/figures/pestle/<id>/.

Key facts (FINAL_PLAN.md §8):
- Two ID families: SPM.<paper>.<SL|HL>.TZ<tz>.<num> (18) and
  <YY>[MN].<paper>.<SL|HL|AHL>.TZ<tz>.<num> (728, topic tag _H/_T/_S/_HSP).
- 746 questions; mark scheme present, 746 MS entries keyed 1:1 by the SAME ID.
- Questions paginate by sheet -> 79 span >=2 pages (figure/body may cross a page turn).
  Each question's full page-span is rendered and vertically stitched into ONE JPG so a
  sliced figure is recombined continuously. Per-page cropping removes the running header
  and the next question's header so no neighbouring content leaks in.
- Idempotent: stable id = the question ID; JPGs skip-if-exists on re-run.
No DB writes here; the companion import_pestle.mjs does DELETE+INSERT.
"""
import pypdfium2 as pdfium, re, os, json
from datetime import datetime, timezone
from PIL import Image

ROOT = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform"
FIG  = os.path.join(ROOT, "backend/public/figures")
MANIFEST = os.path.join(ROOT, "backend/data/pestle_manifest.json")
PDF  = "/Users/lucas.ma/Downloads/dp learning/Math AA questions.pdf"

DPI = 150
SCALE = DPI / 72.0
PW, PH = 612, 792            # Letter, PDF points
IW, IH = int(PW * SCALE), int(PH * SCALE)
HEADER_BAND_PX = 70          # top band (running header) treated as crop-exclude

# ---------- ID grammar ----------
qid_re = re.compile(r'(SPM\.\d+\.(?:SL|HL)\.TZ\d+\.\w+|\d{2}[MN]\.\d+\.(?:SL|HL|AHL)\.TZ\d+\.\w+)')
div_ms = re.compile(r'(?m)^\s*Markschemes\s*$')

# ---------- math normalization (copied verbatim from extract_paper_aa_p1.py) ----------
_FRAC_PAIR = re.compile(r'[\uf0e6-\uf0f2][\uf0f6-\uf0fc]')
_DELIM_PAIR = re.compile(
    r'([\uf8eb\uf8ec\uf8ed\uf8ee\uf8ef\uf8f0\uf8f1\uf8f3])'
    r'([\uf8f6\uf8f7\uf8f8\uf8f9\uf8fa\uf8fb\uf8f2\uf8f4])')
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
    if not text: return text
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

def clean(text):
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("QuestionBank Test"): continue
        if "pestle.pages.dev" in s: continue
        if re.match(r'^\s*Questions\s*$', s): continue
        if re.match(r'^\s*Markschemes\s*$', s): continue
        out.append(line)
    return "\n".join(out)

CMDS = ["Hence or otherwise","Hence find","Hence show","Hence determine","Hence","Find the probability","Find the exact","Find the value","Find an expression",
        "Find the coordinates","Find the equation","Find","Show that","Show","Determine","Write down","Prove","Sketch","State","Calculate","Solve","Express",
        "Describe","Explain","Deduce","Verify","Given that","Find the"]
def extract_command(qtext):
    # first subpart line after the ID line
    lines = [l for l in qtext.splitlines() if l.strip()]
    if len(lines) < 2: return None
    body = lines[1]
    for c in CMDS:
        if body.startswith(c) or body[:80].startswith(c):
            return c
    return None

# ---------- charbox geometry helpers ----------
def char_top_img(tp, offset):
    """Upper-edge image-y of the glyph at text offset (1:1 with get_charbox)."""
    b = tp.get_charbox(offset)      # (left, bottom_y, right, top_y)  PDF y-up
    ty = b[3]
    return (PH - ty) * SCALE

def header_lower_img(tp, ptext, n):
    low = 0.0
    for i in range(n):
        b = tp.get_charbox(i)
        ti = (PH - b[3]) * SCALE     # upper edge (image)
        if ti < HEADER_BAND_PX:
            bi = (PH - b[1]) * SCALE  # lower edge (image)
            if bi > low: low = bi
    return low

def id_top_img(tp, ptext, n, qid):
    k = ptext.find(qid)
    if k < 0: return header_lower_img(tp, ptext, n)
    return char_top_img(tp, k)

def nextid_top_img(tp, ptext, n, cur_id):
    for m in qid_re.finditer(ptext):
        if m.group(0) != cur_id:
            return char_top_img(tp, m.start())
    return None

def cropped_page(doc, pi, top_mode, bottom_mode, qid):
    page = doc[pi]
    tp = page.get_textpage()
    ptext = tp.get_text_range()
    n = tp.count_chars()
    full = page.render(scale=SCALE).to_pil()
    if top_mode == 'header':
        top_img = header_lower_img(tp, ptext, n)
    else:  # 'id'
        top_img = id_top_img(tp, ptext, n, qid)
    if bottom_mode == 'full':
        bot_img = IH
    else:  # 'nextid'
        nb = nextid_top_img(tp, ptext, n, qid)
        bot_img = nb if nb is not None else IH
    top_img = max(0, int(round(top_img)))
    bot_img = min(IH, int(round(bot_img)))
    if bot_img <= top_img:
        bot_img = min(IH, top_img + 60)
    return full.crop((0, top_img, IW, bot_img))

def concat(imgs):
    h = sum(im.height for im in imgs)
    out = Image.new('RGB', (IW, h), 'white')
    y = 0
    for im in imgs:
        out.paste(im, (0, y)); y += im.height
    return out

def derive_meta(qid):
    parts = qid.split('.')
    level_tok = parts[2]                 # SL / HL / AHL
    level = 'HL' if 'HL' in level_tok else 'SL'
    topic = 'Analysis & Approaches HL' if level == 'HL' else 'Analysis & Approaches SL'
    paper = parts[1]
    paper_type = 'Paper ' + paper
    subtopic = None
    tail = parts[-1]
    if '_' in tail:
        tag = tail.split('_')[0]
        subtopic = {'H':'Topic H (HL)','T':'Trigonometry','S':'Statistics',
                    'HSP':'Stats & Probability (HL)'}.get(tag, None)
    return level, topic, paper_type, subtopic

# ---------- main ----------
def main():
    doc = pdfium.PdfDocument(PDF)
    N = len(doc)
    print("pages", N)
    pages_text = [doc[i].get_textpage().get_text_range() for i in range(N)]
    ms_page = next((i for i in range(N) if div_ms.search(pages_text[i])), None)
    print("ms_page", ms_page)

    # question spans (page ranges) by first occurrence in question region
    q_first = {}
    for i in range(N):
        if ms_page is not None and i >= ms_page: break
        for hid in qid_re.findall(pages_text[i]):
            if hid not in q_first: q_first[hid] = i
    sorted_ids = sorted(q_first, key=lambda h: q_first[h])
    q_spans = {}
    for idx, hid in enumerate(sorted_ids):
        s = q_first[hid]
        e = q_first[sorted_ids[idx+1]] if idx+1 < len(sorted_ids) else ms_page
        q_spans[hid] = (s, e)

    # MS spans (page ranges) by first occurrence in MS region
    ms_first = {}
    for i in range(N):
        if ms_page is None or i < ms_page: continue
        for hid in qid_re.findall(pages_text[i]):
            if hid not in ms_first: ms_first[hid] = i
    ms_sorted = sorted(ms_first, key=lambda h: ms_first[h])
    ms_spans = {}
    for idx, hid in enumerate(ms_sorted):
        s = ms_first[hid]
        e = ms_first[ms_sorted[idx+1]] if idx+1 < len(ms_sorted) else N
        ms_spans[hid] = (s, e)

    # precise text slicing via global text + ID positions
    global_q = clean("\n".join(pages_text[0:ms_page]))
    qmatches = list(qid_re.finditer(global_q))
    global_m = clean("\n".join(pages_text[ms_page:N]))
    mmatches = list(qid_re.finditer(global_m))
    print("q_text_matches", len(qmatches), "ms_text_matches", len(mmatches),
          "q_spans", len(q_spans), "ms_spans", len(ms_spans))

    # sanity: text-match order must equal span order
    assert [m.group(0) for m in qmatches] == sorted_ids, "question order mismatch"
    assert [m.group(0) for m in mmatches] == ms_sorted, "ms order mismatch"

    os.makedirs(FIG, exist_ok=True)
    records = []
    for idx, hid in enumerate(sorted_ids):
        s, e = q_spans[hid]
        qtext = normalize_math(global_q[qmatches[idx].start() : (qmatches[idx+1].start() if idx+1 < len(qmatches) else len(global_q))])
        level, topic, paper_type, subtopic = derive_meta(hid)
        # marks from answer "[N marks]"
        a_s, a_e = ms_spans[hid]
        atext = normalize_math(global_m[mmatches[idx].start() : (mmatches[idx+1].start() if idx+1 < len(mmatches) else len(global_m))])
        mm = re.findall(r'\[(\d+)\s*marks?\]', atext)
        if not mm:
            mm = re.findall(r'\[(\d+)\s*(?:marks?)?\]', qtext)
        marks = sum(int(x) for x in mm) if mm else None

        # render question_image (stitched span)
        folder = os.path.join(FIG, "pestle", hid)
        os.makedirs(folder, exist_ok=True)
        qpath = os.path.join(folder, "q.jpg")
        rel_q = f"pestle/{hid}/q.jpg"
        if not os.path.exists(qpath):
            crops = []
            pages = list(range(s, e)) or [s]
            for j, pi in enumerate(pages):
                top = 'id' if j == 0 else 'header'
                bot = 'nextid' if j == len(pages)-1 else 'full'
                crops.append(cropped_page(doc, pi, top, bot, hid))
            concat(crops).save(qpath, "JPEG", quality=85)

        # render answer_image (stitched MS span)
        apath = os.path.join(folder, "a.jpg")
        rel_a = f"pestle/{hid}/a.jpg"
        if not os.path.exists(apath):
            crops = []
            pages = list(range(a_s, a_e)) or [a_s]
            for j, pi in enumerate(pages):
                top = 'id' if j == 0 else 'header'
                bot = 'nextid' if j == len(pages)-1 else 'full'
                crops.append(cropped_page(doc, pi, top, bot, hid))
            concat(crops).save(apath, "JPEG", quality=85)

        records.append({
            "id": hid,
            "subject": "Mathematics",
            "level": level,
            "topic": topic,
            "subtopic": subtopic,
            "paper_type": paper_type,
            "command_term": extract_command(qtext),
            "marks": marks,
            "difficulty": None,
            "question": qtext,
            "figure": None,
            "answer": atext,
            "explanation": None,
            "source": "Pestle AA Question Bank",
            "tags": [],
            "authored_by": "ib",
            "knowledge_point_ids": [],
            "answer_figure": None,
            "question_image": rel_q,
            "answer_image": rel_a,
            "figure_image": None,
            "book_id": None,
            "book_section": None,
            "book_page": None,
            "in_book_order": 0,
            "source_type": "paper",
            "category": "past",
            "review_status": "new",
        })
        if (idx+1) % 100 == 0:
            print(f"  rendered {idx+1}/{len(sorted_ids)}")

    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=1)
    print(f"\nTOTAL questions: {len(records)}")
    print(f"Manifest -> {MANIFEST}")

if __name__ == "__main__":
    main()
