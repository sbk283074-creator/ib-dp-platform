#!/usr/bin/env python3
"""
Session 4 extractor — Physics HL Paper 1, May 2016 -> November 2025.

Two validated source formats:
  * old Paper 1 + 2025 Paper 1A: 40 MC questions, compact A/B/C/D key;
  * 2025 Paper 1B: 2 or 3 top-level structured questions, detailed subpart MS.

Per FINAL_PLAN Rule #5, each record keeps normalized text AND rendered
question_image/answer_image. Question images use coordinate-aware vertical
bands so a dense MC page does not become an ambiguous whole-page screenshot.
No DB writes happen here; import_physics_p1.mjs performs idempotent import.
"""
import os, re, json
import pypdfium2 as pdfium
from PIL import Image

BASE = "/Users/lucas.ma/Downloads/dp learning/Physics-HL-Past Papers&Mark Schemes(1999.05~2025.11)"
ROOT = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform"
FIG = os.path.join(ROOT, "backend/public/figures")
MANIFEST = os.path.join(ROOT, "backend/data/physics_hl_p1_manifest.json")
DPI = 170
SCALE = DPI / 72.0

QP_HEAD = re.compile(r'(?m)(?:^|[\r\n\ufffe])\s*(\d{1,2})\.(?!\d)\s+')
# 2025 P1B MS rows: both "1. a" and "1 a" occur. Top-level walker ignores
# repeated subpart rows with the same qnum and accepts only next qnum.
MS_TOP_ROW = re.compile(r'(?m)(?:^|[\r\n\ufffe])\s*(\d{1,2})\.?\s+(?=[a-z])')
MC_ANSWER = re.compile(r'(?<![\w])(?P<n>\d{1,2})\.\s*(?P<a>[ABCD])(?=\s|$)')
MARKS = re.compile(r'\[(\d+)\]')

# Physics PDFs use a small set of Symbol/MT Extra PUA glyphs. Most content is
# already Unicode, but the remaining glyphs below occur in physics symbols,
# delimiter fragments, and the 2025B marking tables. The rendered screenshot
# remains authoritative for any structural glyph.
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
    0xF03D:'=', 0xF03F:'?', 0xF041:'Α', 0xF042:'Β', 0xF044:'Δ', 0xF057:'Ω',
    0xF059:'Ψ', 0xF061:'α', 0xF062:'β', 0xF064:'δ', 0xF065:'ε', 0xF068:'η',
    0xF06B:'κ', 0xF06C:'λ', 0xF06D:'μ', 0xF070:'π', 0xF072:'ϑ', 0xF073:'σ',
    0xF074:'τ', 0xF0A2:'ℤ', 0xF0B0:'°', 0xF0B1:'±', 0xF0B4:'×', 0xF0D7:'⋅',
    0xF030:'0', 0xF0FC:'', 0xF8E7:'',
    0xF8EB:'[', 0xF8F6:'[', 0xF8EC:']', 0xF8F7:']',
    0xF8ED:'(', 0xF8F8:'(', 0xF8EE:')', 0xF8F9:')',
}

def normalize_physics(text):
    def adj(m):
        a, b = ord(m.group(1)), ord(m.group(2))
        return _DELIM_ADJ.get((a, b), PHYS_PUA_MAP.get(a, '') + PHYS_PUA_MAP.get(b, ''))
    text = _DELIM_PAIR.sub(adj, text)
    return ''.join(PHYS_PUA_MAP.get(ord(c), c) for c in text)

# English files only; translation duplicates are intentionally excluded.
PAPERS = [
 ("2016 May Examination Session", "Physics_paper_1__HL.pdf"),
 ("2016 November Examination Session", "Physics_paper_1__HL.pdf"),
 ("2017 May Examination Session", "Physics_paper_1__TZ1_HL.pdf"),
 ("2017 May Examination Session", "Physics_paper_1__TZ2_HL.pdf"),
 ("2017 November Examination Session", "Physics_paper_1__HL.pdf"),
 ("2018 May Examination Session", "Physics_paper_1__TZ1_HL.pdf"),
 ("2018 May Examination Session", "Physics_paper_1__TZ2_HL.pdf"),
 ("2018 November Examination Session", "Physics_paper_1__HL.pdf"),
 ("2019 May Examination Session", "Physics_paper_1__TZ1_HL.pdf"),
 ("2019 May Examination Session", "Physics_paper_1__TZ2_HL.pdf"),
 ("2019 November Examination Session", "Physics_paper_1__HL.pdf"),
 ("2020 November Examination Session", "Physics_paper_1__HL.pdf"),
 ("2021 May 物理HL", "Physics_paper_1__TZ1_HL.pdf"),
 ("2021 May 物理HL", "Physics_paper_1__TZ2_HL.pdf"),
 ("2022 May Examination Session", "Physics_paper_1__TZ1_HL.pdf"),
 ("2022 May Examination Session", "Physics_paper_1__TZ2_HL.pdf"),
 ("2022 November Examination Session", "Physics_paper_1__HL.pdf"),
 ("2023.05", "Physics_paper_1__TZ1_HL.pdf"),
 ("2023.05", "Physics_paper_1__TZ2_HL.pdf"),
 ("2023.11", "Physics_paper_1__TZ1_HL.pdf"),
 ("2023.11", "Physics_paper_1__TZ2_HL.pdf"),
 ("2024.05", "Physics_paper_1__TZ1_HL.pdf"),
 ("2024.05", "Physics_paper_1__TZ2_HL.pdf"),
 ("2024.11", "Physics_paper_1__HL.pdf"),
 ("2025.05", "Physics_paper_1A_TZ1_HL.pdf"),
 ("2025.05", "Physics_paper_1A_TZ2_HL.pdf"),
 ("2025.05", "Physics_paper_1A_TZ3_HL.pdf"),
 ("2025.05", "Physics_paper_1B_TZ1_HL.pdf"),
 ("2025.05", "Physics_paper_1B_TZ2_HL.pdf"),
 ("2025.05", "Physics_paper_1B_TZ3_HL.pdf"),
 ("2025.11", "Physics_paper_1A_TZ1_HL.pdf"),
 ("2025.11", "Physics_paper_1A_TZ3_HL.pdf"),
 ("2025.11", "Physics_paper_1B_TZ1_HL.pdf"),
 ("2025.11", "Physics_paper_1B_TZ3_HL.pdf"),
]

def session_label(dirname):
    m = re.match(r'^(20\d\d)[ .](05|11)', dirname)
    if m:
        return f"{m.group(1)} {'May' if m.group(2) == '05' else 'Nov'}"
    m = re.match(r'^(20\d\d) (May|November)', dirname)
    if m:
        return f"{m.group(1)} {'May' if m.group(2) == 'May' else 'Nov'}"
    return dirname.replace(' Examination Session', '').replace(' 物理HL', '')

def slug_for(dirname, filename):
    sess = session_label(dirname).replace(' ', '')
    stem = filename[:-4]
    if '1A_' in stem:
        fmt = re.search(r'1A_(TZ\d+)', stem).group(1)
        return f"{sess}_1A_{fmt}"
    if '1B_' in stem:
        fmt = re.search(r'1B_(TZ\d+)', stem).group(1)
        return f"{sess}_1B_{fmt}"
    tz = re.search(r'TZ\d+', stem)
    return f"{sess}_{tz.group(0) if tz else 'HL'}"

def load(path):
    doc = pdfium.PdfDocument(path)
    pages = [doc[i].get_textpage().get_text_range() for i in range(len(doc))]
    full = "\n".join(pages)
    offsets = [0]
    for t in pages:
        offsets.append(offsets[-1] + len(t) + 1)
    return doc, pages, full, offsets

def page_of(pos, offsets):
    for i in range(len(offsets) - 1):
        if offsets[i] <= pos < offsets[i + 1]:
            return i
    return len(offsets) - 2

def header_hits(doc, pages, full, offsets, regex, max_questions):
    hits = []
    expected = 1
    for m in regex.finditer(full):
        n = int(m.group(1))
        if not (1 <= n <= max_questions):
            continue
        if n != expected:
            continue
        pos = m.start(1)
        pi = page_of(pos, offsets)
        local = pos - offsets[pi]
        tp = doc[pi].get_textpage()
        try:
            box = tp.get_charbox(max(0, min(local, tp.count_chars() - 1)))
        finally:
            tp.close()
        H = float(doc[pi].get_height())
        # pypdfium boxes are bottom-up; render crops use top-down points.
        top = H - float(box[3])
        bottom = H - float(box[1])
        hits.append({'n': n, 'pos': pos, 'pi': pi, 'top': top, 'bottom': bottom, 'match': m})
        expected += 1
        if expected > max_questions:
            break
    return hits

def clean(text):
    out = []
    for line in text.replace('\ufffe', '').splitlines():
        s = line.strip()
        if not s:
            out.append('')
            continue
        if 'Please do not write on this page' in s or 'Answers written on this page' in s:
            continue
        if s == 'Turn over':
            continue
        if re.match(r'^[-–]\s*\d+\s*[-–]', s):
            continue
        if re.match(r'^\d{2}EP\d{2}$', s):
            continue
        if re.search(r'(?:M|N|O)\d{2}/4/PHYSI', s):
            continue
        out.append(line)
    text = '\n'.join(out)
    text = normalize_physics(text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()

def is_spacer(page_text):
    s = page_text.strip()
    return bool(s) and 'Please do not write on this page' in s and len(s) < 180

def render_crop(page, top, bottom, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if os.path.exists(out_path):
        return
    img = page.render(scale=SCALE).to_pil()
    y0 = max(0, min(img.height - 2, int(round(top * SCALE))))
    y1 = max(y0 + 8, min(img.height, int(round(bottom * SCALE))))
    if y1 <= y0:
        return
    img.crop((0, y0, img.width, y1)).save(out_path, 'JPEG', quality=88)

def render_full(page, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if os.path.exists(out_path):
        return
    page.render(scale=SCALE).to_pil().save(out_path, 'JPEG', quality=88)

def image_segments(doc, pages, hits, folder, kind, skip_spacers=True):
    """Return comma-separated coordinate-aware page-band images for hit spans."""
    result = []
    for idx, hit in enumerate(hits):
        end = hits[idx + 1] if idx + 1 < len(hits) else None
        page_end = end['pi'] if end else len(pages) - 1
        refs = []
        for pi in range(hit['pi'], page_end + 1):
            if skip_spacers and is_spacer(pages[pi]):
                continue
            H = float(doc[pi].get_height())
            top = hit['top'] - 10 if pi == hit['pi'] else 0
            if end and pi == end['pi']:
                bottom = end['top'] - 8
            else:
                bottom = H
            if bottom <= top + 8:
                continue
            rel = f"{folder}/{kind}{hit['n']:02d}_p{pi + 1}.jpg"
            render_crop(doc[pi], top, bottom, os.path.join(FIG, rel))
            refs.append(rel)
        result.append(refs)
    return result

def spatial_key_fallback(ms_doc, ms_pages, ms_full, ms_offsets, n):
    """Recover a key cell when PDF text order separates qnum and its letter.

    2025.05 TZ2 q33 is emitted as `33. 48. –` with its answer `C` as a
    standalone text object at the same visual y-coordinate. Use char boxes only
    for this fallback; normal keys use the simpler text parser.
    """
    token = re.compile(rf'(?<!\d){n}\.')
    for tm in token.finditer(ms_full):
        pos = tm.start(); pi = page_of(pos, ms_offsets); local = pos - ms_offsets[pi]
        tp = ms_doc[pi].get_textpage()
        try:
            qbox = tp.get_charbox(max(0, min(local, tp.count_chars() - 1)))
            qright = float(qbox[2])
            qy = (float(qbox[1]) + float(qbox[3])) / 2.0
            chars = []
            text = ms_pages[pi]
            for i, ch in enumerate(text):
                if ch not in 'ABCD':
                    continue
                try:
                    b = tp.get_charbox(i)
                except Exception:
                    continue
                cy = (float(b[1]) + float(b[3])) / 2.0
                if abs(cy - qy) <= 5.0 and qright < float(b[0]) < qright + 90.0:
                    chars.append((float(b[0]), ch))
        finally:
            tp.close()
        if chars:
            chars.sort()
            return {'n': n, 'pos': pos, 'pi': pi, 'choice': chars[0][1]}
    return None

def answer_key_hits(ms_doc, ms_pages, ms_full, ms_offsets):
    hits = []
    seen = set()
    for m in MC_ANSWER.finditer(ms_full):
        n = int(m.group('n'))
        if not (1 <= n <= 40) or n in seen:
            continue
        pos = m.start('n'); pi = page_of(pos, ms_offsets)
        seen.add(n)
        hits.append({'n': n, 'pos': pos, 'pi': pi, 'choice': m.group('a')})
    # Fill only missing cells using visual same-row geometry.
    by_n = {h['n']: h for h in hits}
    for n in range(1, 41):
        if n in by_n:
            continue
        fallback = spatial_key_fallback(ms_doc, ms_pages, ms_full, ms_offsets, n)
        if fallback:
            by_n[n] = fallback
    return [by_n[n] for n in sorted(by_n)]

def mc_records(qp_rel, dirname, filename):
    qp_path = os.path.join(BASE, dirname, filename)
    ms_path = os.path.join(BASE, dirname, filename[:-4] + '_markscheme.pdf')
    qd, qpages, qfull, qoff = load(qp_path)
    md, mpages, mfull, moff = load(ms_path)
    qhits = header_hits(qd, qpages, qfull, qoff, QP_HEAD, 40)
    if len(qhits) != 40:
        raise RuntimeError(f"{dirname}/{filename}: expected 40 QP headers, got {len(qhits)}")
    ahits = answer_key_hits(md, mpages, mfull, moff)
    if len(ahits) != 40:
        raise RuntimeError(f"{dirname}/{filename}: expected 40 answer keys, got {len(ahits)}")
    choices = {h['n']: h['choice'] for h in ahits}
    key_page = {h['n']: h['pi'] for h in ahits}
    slug = slug_for(dirname, filename)
    folder = f"physics_hl_p1/{slug}"
    qimgs = image_segments(qd, qpages, qhits, folder, 'q', skip_spacers=False)
    records = []
    for i, h in enumerate(qhits):
        end = qhits[i + 1]['pos'] if i + 1 < len(qhits) else len(qfull)
        qtext = clean(qfull[h['pos']:end])
        pi = key_page[h['n']]
        arel = f"{folder}/answer_key_p{pi + 1}.jpg"
        render_full(md[pi], os.path.join(FIG, arel))
        records.append({
            'id': f"PHYS_HL_P1_{slug}_q{h['n']:02d}",
            'subject': 'Physics', 'level': 'HL', 'topic': 'Physics HL', 'subtopic': None,
            'paper_type': 'Paper 1', 'command_term': None,
            'marks': 1, 'difficulty': None,
            'question': qtext, 'figure': None,
            'answer': f"{h['n']}. {choices[h['n']]}", 'explanation': None,
            'source': f"Physics HL P1 · {session_label(dirname)}{' ' + ('1A ' + re.search(r'TZ\d+', filename).group(0) if '1A_' in filename else '') if '1A_' in filename else (' ' + re.search(r'TZ\d+', filename).group(0) if 'TZ' in filename else '')}",
            'tags': [], 'authored_by': 'ib', 'knowledge_point_ids': [], 'answer_figure': None,
            'question_image': ','.join(qimgs[i]), 'answer_image': arel,
            'figure_image': None, 'book_id': None, 'source_type': 'paper',
            'category': 'past', 'review_status': 'new',
        })
    qd.close(); md.close()
    return records

def p1b_records(dirname, filename):
    qp_path = os.path.join(BASE, dirname, filename)
    ms_path = os.path.join(BASE, dirname, filename[:-4] + '_markscheme.pdf')
    qd, qpages, qfull, qoff = load(qp_path)
    md, mpages, mfull, moff = load(ms_path)
    qhits = header_hits(qd, qpages, qfull, qoff, QP_HEAD, 3)
    if len(qhits) not in (2, 3):
        raise RuntimeError(f"{dirname}/{filename}: expected 2 or 3 P1B QP headers, got {len(qhits)}")
    table = re.search(r'(?m)^\s*(?:Question|Q)\s+Answers\s+Notes\s+Total', mfull)
    if not table:
        raise RuntimeError(f"{dirname}/{filename}: P1B MS table header not found")
    seg_start = table.start()
    ms_seg = mfull[seg_start:]
    # Use absolute positions for the MS rows because the table begins after
    # rubric/instruction pages; the same page offsets still apply to mfull.
    rhits = []
    expected = 1
    for m in MS_TOP_ROW.finditer(ms_seg):
        n = int(m.group(1))
        if n != expected:
            continue
        pos = seg_start + m.start(1); pi = page_of(pos, moff); local = pos - moff[pi]
        tp = md[pi].get_textpage()
        try: box = tp.get_charbox(max(0, min(local, tp.count_chars() - 1)))
        finally: tp.close()
        H = float(md[pi].get_height())
        rhits.append({'n': n, 'pos': pos, 'pi': pi, 'top': H - float(box[3]), 'bottom': H - float(box[1])})
        expected += 1
        if expected > len(qhits): break
    if len(rhits) != len(qhits):
        raise RuntimeError(f"{dirname}/{filename}: QP/MS top-level mismatch {len(qhits)}/{len(rhits)}")
    qimgs = image_segments(qd, qpages, qhits, f"physics_hl_p1b/{slug_for(dirname, filename)}", 'q', skip_spacers=True)
    aimgs = image_segments(md, mpages, rhits, f"physics_hl_p1b/{slug_for(dirname, filename)}", 'a', skip_spacers=True)
    records = []
    slug = slug_for(dirname, filename)
    for i, qh in enumerate(qhits):
        qend = qhits[i + 1]['pos'] if i + 1 < len(qhits) else len(qfull)
        ast = rhits[i]['pos']; aend = rhits[i + 1]['pos'] if i + 1 < len(rhits) else len(mfull)
        qtext = clean(qfull[qh['pos']:qend])
        atext = clean(mfull[ast:aend])
        marks = sum(int(x) for x in MARKS.findall(qtext)) or None
        records.append({
            'id': f"PHYS_HL_P1B_{slug}_q{qh['n']:02d}",
            'subject': 'Physics', 'level': 'HL', 'topic': 'Physics HL', 'subtopic': None,
            'paper_type': 'Paper 1', 'command_term': None,
            'marks': marks, 'difficulty': None,
            'question': qtext, 'figure': None, 'answer': atext, 'explanation': None,
            'source': f"Physics HL P1B · {session_label(dirname)} {re.search(r'TZ\d+', filename).group(0)}",
            'tags': [], 'authored_by': 'ib', 'knowledge_point_ids': [], 'answer_figure': None,
            'question_image': ','.join(qimgs[i]), 'answer_image': ','.join(aimgs[i]),
            'figure_image': None, 'book_id': None, 'source_type': 'paper',
            'category': 'past', 'review_status': 'new',
        })
    qd.close(); md.close()
    return records

def main():
    all_records = []
    for dirname, filename in PAPERS:
        if '1B_' in filename:
            recs = p1b_records(dirname, filename)
        else:
            recs = mc_records('', dirname, filename)
        all_records.extend(recs)
        print(f"  {dirname}/{filename}: {len(recs)} records")
    with open(MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(all_records, f, ensure_ascii=False, indent=1)
    print(f"\nTOTAL records: {len(all_records)}")
    print(f"Manifest -> {MANIFEST}")

if __name__ == '__main__':
    main()
