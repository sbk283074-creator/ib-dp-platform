#!/usr/bin/env python3
"""
Session 6 extractor — Physics HL Paper 3 (all available English options).

Each PDF contains Section A plus four option blocks. We keep every option as a
separate searchable record, keyed by (source, block, top-level qnum). QP/MS
spans are matched inside the declared block ranges, not by qnum globally.
No DB writes happen here; import_physics_p3.mjs is idempotent.
"""
import os, re, json
import pypdfium2 as pdfium

BASE = "/Users/lucas.ma/Downloads/dp learning/Physics-HL-Past Papers&Mark Schemes(1999.05~2025.11)"
ROOT = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform"
FIG = os.path.join(ROOT, "backend/public/figures")
MANIFEST = os.path.join(ROOT, "backend/data/physics_hl_p3_manifest.json")
DPI = 170
SCALE = DPI / 72.0

QP_HEAD = re.compile(r'(?m)(?:^|[\r\n\ufffe])\s*(\d{1,2})\.(?!\d)\s+(?=[A-Z(])')
# Most MS rows start with a/b/i subparts, but some older top-level questions
# have no letter (e.g. `4 Y measures electrostatic repulsion only`).
MS_ROW = re.compile(r'(?m)(?:^|[\r\n\ufffe])\s*(\d{1,2})(?:\.(?=[ \t\r\n])|(?=[ \t]+(?:\([a-z]\)|[a-z](?:[ \t\r\n]|$)|[A-Z])))[ \t]*')
MARKS = re.compile(r'\[(\d+)\]')
OPTION_LINE = re.compile(r'(?m)^\s*Option\s+([A-D])\s+[—–-]')

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
    0xF03B:':', 0xF03C:'<', 0xF03D:'=', 0xF03E:'≥', 0xF03F:'?', 0xF041:'Α', 0xF042:'Β',
    0xF044:'Δ', 0xF046:'Φ', 0xF04B:'Κ', 0xF057:'Ω', 0xF059:'Ψ',
    0xF05B:'[', 0xF05D:']', 0xF061:'α', 0xF062:'β', 0xF063:'β', 0xF064:'δ', 0xF065:'ε', 0xF066:'φ', 0xF067:'γ', 0xF068:'η',
    0xF06B:'κ', 0xF06C:'λ', 0xF06D:'μ', 0xF06E:'ν', 0xF06F:'ο', 0xF070:'π',
    0xF071:'θ', 0xF072:'ϑ', 0xF073:'σ', 0xF074:'τ', 0xF075:'υ', 0xF077:'ω',
    0xF0A0:'', 0xF0A2:'ℤ', 0xF0A4:'⊙', 0xF0A5:'ℚ', 0xF0AE:'→', 0xF0B0:'°', 0xF0B1:'±', 0xF0B4:'×',
    0xF0B2:'″', 0xF0B3:'≥', 0xF0B5:'∝', 0xF0B8:'÷', 0xF0BA:'→', 0xF0BB:'↔', 0xF0CD:'×', 0xF0D7:'⋅',
    0xF0DE:'∫', 0xF030:'0', 0xF0E6:'', 0xF0E7:'', 0xF0E8:'', 0xF0F6:'',
    0xF0F0:'→', 0xF0F7:'', 0xF0F8:'', 0xF0FC:'', 0xF0FE:'°', 0xF8E7:'',
    0xF8EB:'[', 0xF8F6:'[', 0xF8EC:']', 0xF8F7:']',
    0xF8ED:'(', 0xF8F8:'(', 0xF8EE:')', 0xF8F9:')',
    0xF8F1:'', 0xF8F2:'', 0xF8F3:'', 0xF8F4:'',
    0xF8EF:'', 0xF8F0:'', 0xF8FA:'', 0xF8FB:'', 0xF8FC:'', 0xF8FD:'', 0xF8FE:'',
}

def normalize_physics(text):
    def adj(m):
        a, b = ord(m.group(1)), ord(m.group(2))
        return _DELIM_ADJ.get((a, b), PHYS_PUA_MAP.get(a, '') + PHYS_PUA_MAP.get(b, ''))
    text = ''.join(PHYS_PUA_MAP.get(ord(c), c) for c in _DELIM_PAIR.sub(adj, text))
    # Unknown structural PUA glyphs are intentionally dropped after mapping;
    # the rendered image preserves their exact visual form.
    return re.sub(r'[\ue000-\uf8ff]', '', text)

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

def session_label(dirname):
    m = re.match(r'^(20\d\d)[ .](05|11)', dirname)
    if m: return f"{m.group(1)} {'May' if m.group(2) == '05' else 'Nov'}"
    m = re.match(r'^(20\d\d) (May|November)', dirname)
    if m: return f"{m.group(1)} {'May' if m.group(2) == 'May' else 'Nov'}"
    return dirname.replace(' Examination Session', '').replace(' 物理HL', '')

def slug_for(dirname, filename):
    tz = re.search(r'TZ\d+', filename)
    return f"{session_label(dirname).replace(' ', '')}_{tz.group(0) if tz else 'HL'}"

def option_ranges(text):
    return [(letter, int(a), int(b)) for letter, a, b in re.findall(
        r'Option\s+([A-D])\s+[—–-]\s*[^\r\n]+?(\d+)\s*[–-]\s*(\d+)', text, re.I)]

def markers_after(full, start):
    out = []
    for m in OPTION_LINE.finditer(full, start):
        if m.group(1) not in [x[0] for x in out]:
            out.append((m.group(1), m.start()))
        if len(out) == 4: break
    if len(out) != 4: raise RuntimeError(f"expected four option markers after {start}, got {out}")
    return out

def actual_blocks(full, ranges, section_label):
    sec = re.search(r'(?m)^\s*Section A\s*$', full)
    secb = re.search(r'(?m)^\s*Section B\s*$', full)
    if not sec or not secb: raise RuntimeError('Section A/B marker missing')
    opts = markers_after(full, secb.start())
    blocks = [{'block': 'SEC_A', 'option': None, 'start': sec.end(), 'end': opts[0][1],
               'lo': 1, 'hi': ranges[0][1] - 1}]
    for i, (letter, pos) in enumerate(opts):
        rr = next((x for x in ranges if x[0] == letter), None)
        if rr is None: raise RuntimeError(f'missing range for option {letter}')
        end = opts[i + 1][1] if i + 1 < len(opts) else len(full)
        blocks.append({'block': f'OPT_{letter}', 'option': letter, 'start': pos, 'end': end,
                       'lo': rr[1], 'hi': rr[2]})
    return blocks

def answer_blocks_fallback(full, ranges):
    """Some mark schemes omit Section/Option headings entirely (2024 Nov).
    Split from the first answer-table row for each declared numeric range."""
    headers = list(re.finditer(r'(?m)^\s*Question\s+Answers\s+Notes\s+Total', full))
    cursor = headers[0].end() if headers else 0
    specs = [('SEC_A', None, 1, ranges[0][1] - 1)] + [(f'OPT_{x}', x, a, b) for x, a, b in ranges]
    starts = []
    for block, option, lo, hi in specs:
        found = None
        for m in MS_ROW.finditer(full, cursor):
            if int(m.group(1)) == lo:
                found = m.start(); break
        if found is None: raise RuntimeError(f'answer fallback cannot find q{lo}')
        starts.append((block, option, found, lo, hi)); cursor = found + 1
    out = []
    for i, (block, option, start, lo, hi) in enumerate(starts):
        end = starts[i + 1][2] if i + 1 < len(starts) else len(full)
        out.append({'block': block, 'option': option, 'start': start, 'end': end, 'lo': lo, 'hi': hi})
    return out

def hits_in_block(doc, pages, full, offsets, regex, start, end, lo, hi):
    hits = []
    expected = lo
    for m in regex.finditer(full, start, end):
        n = int(m.group(1))
        if n != expected or n > hi: continue
        pos = m.start(1); pi = page_of(pos, offsets); local = pos - offsets[pi]
        tp = doc[pi].get_textpage()
        try: box = tp.get_charbox(max(0, min(local, tp.count_chars() - 1)))
        finally: tp.close()
        H = float(doc[pi].get_height())
        hits.append({'n': n, 'pos': pos, 'pi': pi, 'top': H - float(box[3]), 'bottom': H - float(box[1])})
        expected += 1
        if expected > hi: break
    if expected != hi + 1:
        raise RuntimeError(f'block {lo}-{hi} resolved {len(hits)} headers; last expected {expected}')
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

def image_segments(doc, pages, offsets, hits, block_end, folder, kind):
    refs_by_hit = []
    boundary_page = page_of(block_end, offsets) if block_end < offsets[-1] else len(pages) - 1
    boundary_top = None
    if block_end < offsets[-1]:
        local = max(0, block_end - offsets[boundary_page])
        tp = doc[boundary_page].get_textpage()
        try:
            box = tp.get_charbox(max(0, min(local, tp.count_chars() - 1)))
            boundary_top = float(doc[boundary_page].get_height()) - float(box[3])
        finally:
            tp.close()
    for idx, hit in enumerate(hits):
        end = hits[idx + 1] if idx + 1 < len(hits) else None
        page_end = end['pi'] if end else boundary_page
        refs = []
        for pi in range(hit['pi'], page_end + 1):
            if is_spacer(pages[pi]): continue
            H = float(doc[pi].get_height())
            top = hit['top'] - 10 if pi == hit['pi'] else 0
            if end and pi == end['pi']:
                bottom = end['top'] - 8
            elif end is None and pi == boundary_page and boundary_top is not None:
                bottom = boundary_top - 8
            else:
                bottom = H
            if bottom <= top + 8: continue
            rel = f"{folder}/{kind}{hit['n']:02d}_p{pi + 1}.jpg"
            render_crop(doc[pi], top, bottom, os.path.join(FIG, rel)); refs.append(rel)
        # A few legacy PDFs put a question/answer row on a page whose text is
        # classified as a spacer. Never leave Rule #5 image fields empty: use
        # the first non-spacer page in the span as a full-page fallback.
        if not refs:
            for pi in range(hit['pi'], page_end + 1):
                if not is_spacer(pages[pi]) or pi == hit['pi']:
                    H = float(doc[pi].get_height())
                    rel = f"{folder}/{kind}{hit['n']:02d}_p{pi + 1}_fallback.jpg"
                    render_crop(doc[pi], 0, H, os.path.join(FIG, rel)); refs.append(rel)
                    break
        refs_by_hit.append(refs)
    return refs_by_hit

def first_answer_pos(block, hits):
    return hits[0]['pos']

def process(dirname, filename):
    qp_path = os.path.join(BASE, dirname, filename)
    ms_path = os.path.join(BASE, dirname, filename[:-4] + '_markscheme.pdf')
    qd, qpages, qfull, qoff = load(qp_path)
    md, mpages, mfull, moff = load(ms_path)
    ranges = option_ranges('\n'.join(qpages[:3]))
    if len(ranges) != 4: raise RuntimeError(f'{dirname}/{filename}: option table missing')
    qblocks = actual_blocks(qfull, ranges, 'QP')
    try:
        mblocks = actual_blocks(mfull, ranges, 'MS')
    except RuntimeError:
        mblocks = answer_blocks_fallback(mfull, ranges)
    slug = slug_for(dirname, filename)
    records = []
    for qb, mb in zip(qblocks, mblocks):
        qhits = hits_in_block(qd, qpages, qfull, qoff, QP_HEAD, qb['start'], qb['end'], qb['lo'], qb['hi'])
        mhits = hits_in_block(md, mpages, mfull, moff, MS_ROW, mb['start'], mb['end'], mb['lo'], mb['hi'])
        qimgs = image_segments(qd, qpages, qoff, qhits, qb['end'], f"physics_hl_p3/{slug}/{qb['block']}", 'q')
        aimgs = image_segments(md, mpages, moff, mhits, mb['end'], f"physics_hl_p3/{slug}/{qb['block']}", 'a')
        label = 'Section A' if qb['block'] == 'SEC_A' else f"Option {qb['option']}"
        for i, qh in enumerate(qhits):
            qend = qhits[i + 1]['pos'] if i + 1 < len(qhits) else qb['end']
            ast = mhits[i]['pos']; aend = mhits[i + 1]['pos'] if i + 1 < len(mhits) else mb['end']
            qtext = clean(qfull[qh['pos']:qend])
            atext = clean(mfull[ast:aend])
            marks = sum(int(x) for x in MARKS.findall(qtext)) or None
            records.append({
                'id': f"PHYS_HL_P3_{slug}_{qb['block']}_q{qh['n']:02d}",
                'subject': 'Physics', 'level': 'HL', 'topic': 'Physics HL', 'subtopic': None,
                'paper_type': 'Paper 3', 'command_term': None, 'marks': marks, 'difficulty': None,
                'question': qtext, 'figure': None, 'answer': atext, 'explanation': None,
                'source': f"Physics HL P3 · {session_label(dirname)}{' ' + re.search(r'TZ\d+', filename).group(0) if 'TZ' in filename else ''} · {label}",
                'tags': [], 'authored_by': 'ib', 'knowledge_point_ids': [], 'answer_figure': None,
                'question_image': ','.join(qimgs[i]), 'answer_image': ','.join(aimgs[i]),
                'figure_image': None, 'book_id': None, 'source_type': 'paper',
                'category': 'past', 'review_status': 'new',
            })
    qd.close(); md.close(); return records

def main():
    papers = []
    for dirname in sorted(os.listdir(BASE)):
        dp = os.path.join(BASE, dirname)
        if not os.path.isdir(dp) or not re.match(r'^20(?:1[6-9]|2[0-5])', dirname): continue
        for filename in sorted(os.listdir(dp)):
            lf = filename.lower()
            if 'paper_3' in lf and 'markscheme' not in lf and not any(k in lf for k in ('french','spanish','german')):
                papers.append((dirname, filename))
    all_records = []
    for dirname, filename in papers:
        recs = process(dirname, filename); all_records.extend(recs)
        print(f"  {dirname}/{filename}: {len(recs)} records")
    with open(MANIFEST, 'w', encoding='utf-8') as f: json.dump(all_records, f, ensure_ascii=False, indent=1)
    print(f"\nTOTAL records: {len(all_records)}")
    print(f"Manifest -> {MANIFEST}")

if __name__ == '__main__': main()
