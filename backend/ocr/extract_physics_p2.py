#!/usr/bin/env python3
"""
Session 5 extractor — Physics HL Paper 2, May 2016 -> November 2025.

One record per top-level structured question. QP and mark-scheme spans are
matched by (paper, qnum). Every row keeps normalized text plus rendered
question_image and answer_image per FINAL_PLAN Rule #5.
No DB writes happen here; import_physics_p2.mjs is idempotent.
"""
import os, re, json
import pypdfium2 as pdfium

BASE = "/Users/lucas.ma/Downloads/dp learning/Physics-HL-Past Papers&Mark Schemes(1999.05~2025.11)"
ROOT = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform"
FIG = os.path.join(ROOT, "backend/public/figures")
MANIFEST = os.path.join(ROOT, "backend/data/physics_hl_p2_manifest.json")
DPI = 170
SCALE = DPI / 72.0

QP_HEAD = re.compile(r'(?m)(?:^|[\r\n\ufffe])\s*(\d{1,2})\.(?!\d)\s+(?=[A-Z(])')
# Both MS row forms are present: "1. (a)" / "1. a i" and "1 a" / "1 a i".
# Require a real subpart token after a no-dot number; this avoids numeric
# formula lines such as `2` followed by `el` being mistaken for Q2.
MS_TOP_ROW = re.compile(r'(?m)(?:^|[\r\n\ufffe])\s*(\d{1,2})(?:\.(?=\s)|(?=[ \t]+(?:\([a-z]\)|[a-z](?:[ \t\r\n]|$))))\s+')
MARKS = re.compile(r'\[(\d+)\]')

# Symbol/MT Extra PUA normalization. Structural glyphs are best-effort; the
# rendered screenshots remain authoritative for exact equations and diagrams.
_DELIM_PAIR = re.compile(
    r'([\uf8eb\uf8ec\uf8ed\uf8ee\uf8ef\uf8f0\uf8f1\uf8f3])'
    r'([\uf8f6\uf8f7\uf8f8\uf8f9\uf8fa\uf8fb\uf8f2\uf8f4])'
)
_DELIM_ADJ = {
    (0xF8EB, 0xF8F6): '[', (0xF8EC, 0xF8F7): ']',
    (0xF8ED, 0xF8F8): '(', (0xF8EE, 0xF8F9): ')',
    (0xF8EF, 0xF8FA): '{', (0xF8F0, 0xF8FB): '}',
}
PHYS_PUA_MAP = {
    0xF022:'∀', 0xF025:'×', 0xF028:'(', 0xF029:')', 0xF02B:'+', 0xF02D:'−',
    0xF03B:':', 0xF03D:'=', 0xF03E:'≥', 0xF03F:'?', 0xF041:'Α', 0xF042:'Β',
    0xF044:'Δ', 0xF046:'Φ', 0xF04B:'Κ', 0xF057:'Ω', 0xF059:'Ψ',
    0xF061:'α', 0xF062:'β', 0xF064:'δ', 0xF065:'ε', 0xF066:'φ', 0xF068:'η',
    0xF06B:'κ', 0xF06C:'λ', 0xF06D:'μ', 0xF06E:'ν', 0xF06F:'ο', 0xF070:'π',
    0xF071:'θ', 0xF072:'ϑ', 0xF073:'σ', 0xF074:'τ', 0xF075:'υ', 0xF077:'ω',
    0xF0A2:'ℤ', 0xF0A5:'ℚ', 0xF0AE:'→', 0xF0B0:'°', 0xF0B1:'±', 0xF0B4:'×', 0xF0B5:'∝',
    0xF0B8:'÷', 0xF0BA:'→', 0xF0BB:'↔', 0xF0CD:'×', 0xF0D7:'⋅', 0xF0DE:'∫',
    0xF030:'0', 0xF0E6:'', 0xF0E7:'', 0xF0E8:'', 0xF0F6:'', 0xF0F7:'', 0xF0F8:'',
    0xF0FC:'', 0xF8E7:'',
    0xF8EB:'[', 0xF8F6:'[', 0xF8EC:']', 0xF8F7:']',
    0xF8ED:'(', 0xF8F8:'(', 0xF8EE:')', 0xF8F9:')',
}

def normalize_physics(text):
    def adj(m):
        a, b = ord(m.group(1)), ord(m.group(2))
        return _DELIM_ADJ.get((a, b), PHYS_PUA_MAP.get(a, '') + PHYS_PUA_MAP.get(b, ''))
    text = _DELIM_PAIR.sub(adj, text)
    return ''.join(PHYS_PUA_MAP.get(ord(c), c) for c in text)

PAPERS = [
 ("2016 May Examination Session", "Physics_paper_2__HL.pdf"),
 ("2016 November Examination Session", "Physics_paper_2__HL.pdf"),
 ("2017 May Examination Session", "Physics_paper_2__TZ1_HL.pdf"),
 ("2017 May Examination Session", "Physics_paper_2__TZ2_HL.pdf"),
 ("2017 November Examination Session", "Physics_paper_2__HL.pdf"),
 ("2018 May Examination Session", "Physics_paper_2__TZ1_HL.pdf"),
 ("2018 May Examination Session", "Physics_paper_2__TZ2_HL.pdf"),
 ("2018 November Examination Session", "Physics_paper_2__HL.pdf"),
 ("2019 May Examination Session", "Physics_paper_2__TZ1_HL.pdf"),
 ("2019 May Examination Session", "Physics_paper_2__TZ2_HL.pdf"),
 ("2019 November Examination Session", "Physics_paper_2__HL.pdf"),
 ("2020 November Examination Session", "Physics_paper_2__HL.pdf"),
 ("2021 May 物理HL", "Physics_paper_2__TZ1_HL.pdf"),
 ("2021 May 物理HL", "Physics_paper_2__TZ2_HL.pdf"),
 ("2022 May Examination Session", "Physics_paper_2__TZ1_HL.pdf"),
 ("2022 May Examination Session", "Physics_paper_2__TZ2_HL.pdf"),
 ("2022 November Examination Session", "Physics_paper_2__HL.pdf"),
 ("2023.05", "Physics_paper_2__TZ1_HL.pdf"),
 ("2023.05", "Physics_paper_2__TZ2_HL.pdf"),
 ("2023.11", "Physics_paper_2__TZ1_HL.pdf"),
 ("2023.11", "Physics_paper_2__TZ2_HL.pdf"),
 ("2024.05", "Physics_paper_2__TZ1_HL.pdf"),
 ("2024.05", "Physics_paper_2__TZ2_HL.pdf"),
 ("2024.11", "Physics_paper_2__HL.pdf"),
 ("2025.05", "Physics_paper_2_TZ1_HL.pdf"),
 ("2025.05", "Physics_paper_2_TZ2_HL.pdf"),
 ("2025.05", "Physics_paper_2_TZ3_HL.pdf"),
 ("2025.11", "Physics_paper_2_TZ1_HL.pdf"),
 ("2025.11", "Physics_paper_2_TZ3_HL.pdf"),
]

def session_label(dirname):
    m = re.match(r'^(20\d\d)[ .](05|11)', dirname)
    if m: return f"{m.group(1)} {'May' if m.group(2) == '05' else 'Nov'}"
    m = re.match(r'^(20\d\d) (May|November)', dirname)
    if m: return f"{m.group(1)} {'May' if m.group(2) == 'May' else 'Nov'}"
    return dirname.replace(' Examination Session', '').replace(' 物理HL', '')

def slug_for(dirname, filename):
    sess = session_label(dirname).replace(' ', '')
    tz = re.search(r'TZ\d+', filename)
    return f"{sess}_{tz.group(0) if tz else 'HL'}"

def load(path):
    doc = pdfium.PdfDocument(path)
    pages = [doc[i].get_textpage().get_text_range() for i in range(len(doc))]
    full = "\n".join(pages)
    offsets = [0]
    for t in pages: offsets.append(offsets[-1] + len(t) + 1)
    return doc, pages, full, offsets

def page_of(pos, offsets):
    for i in range(len(offsets) - 1):
        if offsets[i] <= pos < offsets[i + 1]: return i
    return len(offsets) - 2

def hits_with_boxes(doc, pages, full, offsets, regex, max_questions, start=0):
    hits = []; expected = 1
    for m in regex.finditer(full, start):
        n = int(m.group(1))
        if not (1 <= n <= max_questions) or n != expected: continue
        pos = m.start(1); pi = page_of(pos, offsets); local = pos - offsets[pi]
        tp = doc[pi].get_textpage()
        try: box = tp.get_charbox(max(0, min(local, tp.count_chars() - 1)))
        finally: tp.close()
        H = float(doc[pi].get_height())
        hits.append({'n': n, 'pos': pos, 'pi': pi,
                     'top': H - float(box[3]), 'bottom': H - float(box[1])})
        expected += 1
        if expected > max_questions: break
    return hits

def clean(text):
    out = []
    for line in text.replace('\ufffe', '').splitlines():
        s = line.strip()
        if 'Please do not write on this page' in s or 'Answers written on this page' in s: continue
        if s == 'Turn over': continue
        if re.match(r'^[-–]\s*\d+\s*[-–]', s): continue
        if re.match(r'^\d{2}EP\d{2}$', s): continue
        if re.search(r'(?:M|N|O)\d{2}/4/PHYSI', s): continue
        out.append(line)
    text = normalize_physics('\n'.join(out))
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()

def is_spacer(text):
    s = text.strip()
    return bool(s) and 'Please do not write on this page' in s and len(s) < 180

def render_crop(page, top, bottom, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if os.path.exists(out_path): return
    img = page.render(scale=SCALE).to_pil()
    y0 = max(0, min(img.height - 2, int(round(top * SCALE))))
    y1 = max(y0 + 8, min(img.height, int(round(bottom * SCALE))))
    if y1 > y0: img.crop((0, y0, img.width, y1)).save(out_path, 'JPEG', quality=88)

def image_segments(doc, pages, hits, folder, kind, skip_spacers=True):
    result = []
    for idx, hit in enumerate(hits):
        end = hits[idx + 1] if idx + 1 < len(hits) else None
        page_end = end['pi'] if end else len(pages) - 1
        refs = []
        for pi in range(hit['pi'], page_end + 1):
            if skip_spacers and is_spacer(pages[pi]): continue
            H = float(doc[pi].get_height())
            top = hit['top'] - 10 if pi == hit['pi'] else 0
            bottom = end['top'] - 8 if end and pi == end['pi'] else H
            if bottom <= top + 8: continue
            rel = f"{folder}/{kind}{hit['n']:02d}_p{pi + 1}.jpg"
            render_crop(doc[pi], top, bottom, os.path.join(FIG, rel)); refs.append(rel)
        result.append(refs)
    return result

def ms_top_hits(doc, pages, full, offsets, expected):
    headers = list(re.finditer(r'(?m)^\s*(?:Question|Q)\s+Answers\s+Notes\s+Total', full))
    start = headers[0].start() if headers else 0
    hits = hits_with_boxes(doc, pages, full, offsets, MS_TOP_ROW, expected, start)
    if len(hits) != expected:
        raise RuntimeError(f"mark-scheme top-level rows {len(hits)}/{expected}")
    return hits

def process(dirname, filename):
    qp_path = os.path.join(BASE, dirname, filename)
    ms_path = os.path.join(BASE, dirname, filename[:-4] + '_markscheme.pdf')
    qd, qpages, qfull, qoff = load(qp_path)
    md, mpages, mfull, moff = load(ms_path)
    qhits = hits_with_boxes(qd, qpages, qfull, qoff, QP_HEAD, 20)
    if not qhits or qhits[-1]['n'] < 8 or qhits[0]['n'] != 1:
        raise RuntimeError(f"{dirname}/{filename}: unexpected QP headers {len(qhits)}")
    expected = len(qhits)
    mhits = ms_top_hits(md, mpages, mfull, moff, expected)
    slug = slug_for(dirname, filename)
    folder = f"physics_hl_p2/{slug}"
    qimgs = image_segments(qd, qpages, qhits, folder, 'q', skip_spacers=True)
    aimgs = image_segments(md, mpages, mhits, folder, 'a', skip_spacers=False)
    records = []
    for i, qh in enumerate(qhits):
        qend = qhits[i + 1]['pos'] if i + 1 < expected else len(qfull)
        ast = mhits[i]['pos']; aend = mhits[i + 1]['pos'] if i + 1 < expected else len(mfull)
        qtext = clean(qfull[qh['pos']:qend])
        atext = clean(mfull[ast:aend])
        marks = sum(int(x) for x in MARKS.findall(qtext)) or None
        records.append({
            'id': f"PHYS_HL_P2_{slug}_q{qh['n']:02d}",
            'subject': 'Physics', 'level': 'HL', 'topic': 'Physics HL', 'subtopic': None,
            'paper_type': 'Paper 2', 'command_term': None, 'marks': marks, 'difficulty': None,
            'question': qtext, 'figure': None, 'answer': atext, 'explanation': None,
            'source': f"Physics HL P2 · {session_label(dirname)}{' ' + re.search(r'TZ\d+', filename).group(0) if 'TZ' in filename else ''}",
            'tags': [], 'authored_by': 'ib', 'knowledge_point_ids': [], 'answer_figure': None,
            'question_image': ','.join(qimgs[i]), 'answer_image': ','.join(aimgs[i]),
            'figure_image': None, 'book_id': None, 'source_type': 'paper',
            'category': 'past', 'review_status': 'new',
        })
    qd.close(); md.close(); return records

def main():
    all_records = []
    for dirname, filename in PAPERS:
        recs = process(dirname, filename); all_records.extend(recs)
        print(f"  {dirname}/{filename}: {len(recs)} records")
    with open(MANIFEST, 'w', encoding='utf-8') as f: json.dump(all_records, f, ensure_ascii=False, indent=1)
    print(f"\nTOTAL records: {len(all_records)}")
    print(f"Manifest -> {MANIFEST}")

if __name__ == '__main__': main()
