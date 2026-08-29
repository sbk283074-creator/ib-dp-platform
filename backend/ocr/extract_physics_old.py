#!/usr/bin/env python3
"""
Sessions 15-17 extractor — Physics HL Papers 1/2/3, archive band 2000->2015.

Old (pre-2016) Physics papers use structures that differ from the 2016+ ones
already imported:
  * Paper 1 is still 40 MCQ, but 2000-2004 stems sometimes start with a digit
    (e.g. "1. 2.0 kg ...") which the modern 40-header detector cannot catch,
    so those years fail the strict 40-guard and are SKIPPED (Rule #8). The
    clean MCQ band is 2005-2015. The markscheme key uses an en-dash "–" for
    unassessed items; we accept exactly 40 entries (letters or dashes).
  * Paper 2 questions are SECTION-PREFIXED: A1., A2. ... B1. ... The markscheme
    mirrors them (subpart rows are de-duplicated by a sequential filter).
  * Paper 3 questions are OPTION-PREFIXED (old option letters D/E/F/G...), each
    option block aligned independently against its markscheme block.

Reliable band discovered: P1 2005-2015, P2/P3 2000-2015. 1999 is scanned
(text layer = 0) -> excluded. Every record keeps normalized text AND rendered
question_image/answer_image (FINAL_PLAN Rule #5). No DB writes here.
"""
import os, re, json
import pypdfium2 as pdfium
from PIL import Image

BASE = "/Users/lucas.ma/Downloads/dp learning/Physics-HL-Past Papers&Mark Schemes(1999.05~2025.11)"
ROOT = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform"
FIG = os.path.join(ROOT, "backend/public/figures")
MANIFEST = os.path.join(ROOT, "backend/data/physics_old_manifest.json")
DPI = 170
SCALE = DPI / 72.0

P1_HEAD = re.compile(r'(?m)(?:^|[\r\n\ufffe])\s*(\d{1,2})\.(?!\d)\s+(?=[A-Z(])')
SEC_Q = re.compile(r'(?m)(?:^|[\r\n\ufffe])\s*([A-Z])(\d{1,2})\.(?!\d)\s+')
MC_KEY = re.compile(r'(?<!\d)(\d{1,2})\.\s*([ABCD\u2013-])')
MARKS = re.compile(r'\[(\d+)\]')
ENDSKIP = re.compile(r'^\s*(?:Answers written on this page|Please do not write on this page)\s*$', re.I)

# Symbol/MT Extra PUA normalization (comprehensive map from the modern extractors).
_DELIM_PAIR = re.compile(
    r'([\uf8eb\uf8ec\uf8ed\uf8ee\uf8ef\uf8f0\uf8f1\uf8f3])'
    r'([\uf8f6\uf8f7\uf8f8\uf8f9\uf8fa\uf8fb\uf8f2\uf8f4])')
_DELIM_ADJ = {
    (0xF8EB, 0xF8F6): '[', (0xF8EC, 0xF8F7): ']',
    (0xF8ED, 0xF8F8): '(', (0xF8EE, 0xF8F9): ')',
    (0xF8EF, 0xF8FA): '{', (0xF8F0, 0xF8FB): '}',
}
PHYS_PUA_MAP = {
    0xF022:'\u2200', 0xF025:'\u00d7', 0xF028:'(', 0xF029:')', 0xF02B:'+', 0xF02D:'\u2212',
    0xF03B:':', 0xF03C:'<', 0xF03D:'=', 0xF03E:'\u2265', 0xF03F:'?', 0xF041:'\u0391', 0xF042:'\u0392',
    0xF044:'\u0394', 0xF046:'\u03a6', 0xF04B:'\u039a', 0xF057:'\u03a9', 0xF059:'\u03a8',
    0xF05B:'[', 0xF05D:']', 0xF061:'\u03b1', 0xF062:'\u03b2', 0xF063:'\u03b2', 0xF064:'\u03b4',
    0xF065:'\u03b5', 0xF066:'\u03c6', 0xF067:'\u03b3', 0xF068:'\u03b7',
    0xF06B:'\u03ba', 0xF06C:'\u03bb', 0xF06D:'\u03bc', 0xF06E:'\u03bd', 0xF06F:'\u03bf', 0xF070:'\u03c0',
    0xF071:'\u03b8', 0xF072:'\u03d1', 0xF073:'\u03c3', 0xF074:'\u03c4', 0xF075:'\u03c5', 0xF077:'\u03c9',
    0xF0A0:'', 0xF0A2:'\u2124', 0xF0A4:'\u2299', 0xF0A5:'\u211a', 0xF0AE:'\u2192', 0xF0B0:'\u00b0',
    0xF0B1:'\u00b1', 0xF0B2:'\u2033', 0xF0B3:'\u2265', 0xF0B4:'\u00d7', 0xF0B5:'\u221d', 0xF0B8:'\u00f7',
    0xF0BA:'\u2192', 0xF0BB:'\u2194', 0xF0CD:'\u00d7', 0xF0D7:'\u22c5', 0xF0DE:'\u222b',
    0xF030:'0', 0xF0E6:'', 0xF0E7:'', 0xF0E8:'', 0xF0F0:'\u2192', 0xF0F6:'', 0xF0F7:'', 0xF0F8:'',
    0xF0FC:'', 0xF0FE:'\u00b0', 0xF8E7:'',
    0xF8EB:'[', 0xF8F6:'[', 0xF8EC:']', 0xF8F7:']',
    0xF8ED:'(', 0xF8F8:'(', 0xF8EE:')', 0xF8F9:')',
    0xF8F1:'', 0xF8F2:'', 0xF8F3:'', 0xF8F4:'', 0xF8EF:'', 0xF8F0:'', 0xF8FA:'', 0xF8FB:'', 0xF8FC:'', 0xF8FD:'', 0xF8FE:'',
}

def normalize_physics(text):
    def adj(m):
        a, b = ord(m.group(1)), ord(m.group(2))
        return _DELIM_ADJ.get((a, b), PHYS_PUA_MAP.get(a, '') + PHYS_PUA_MAP.get(b, ''))
    text = ''.join(PHYS_PUA_MAP.get(ord(c), c) for c in _DELIM_PAIR.sub(adj, text))
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

def box_for(doc, pages, offsets, pos):
    pi = page_of(pos, offsets); local = pos - offsets[pi]
    tp = doc[pi].get_textpage()
    try:
        b = tp.get_charbox(max(0, min(local, tp.count_chars() - 1)))
    finally: tp.close()
    H = float(doc[pi].get_height())
    return pi, H - float(b[3]), H - float(b[1])

def hit_dict(doc, pages, offsets, m, group=1):
    pos = m.start(group); pi, top, bottom = box_for(doc, pages, offsets, pos)
    return {'pos': pos, 'pi': pi, 'top': top, 'bottom': bottom}

def image_segments(doc, pages, offsets, hits, folder, kind, skip_spacers=True):
    """Render coordinate-aware bands for a list of consecutive hits (next hit bounds span)."""
    refs_by_hit = []
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
            rel = f"{folder}/{kind}{idx + 1:02d}_p{pi + 1}.jpg"
            render_crop(doc[pi], top, bottom, os.path.join(FIG, rel)); refs.append(rel)
        if not refs:
            for pi in range(hit['pi'], page_end + 1):
                if not is_spacer(pages[pi]) or pi == hit['pi']:
                    H = float(doc[pi].get_height())
                    rel = f"{folder}/{kind}{idx + 1:02d}_p{pi + 1}_fb.jpg"
                    render_crop(doc[pi], 0, H, os.path.join(FIG, rel)); refs.append(rel)
                    break
        refs_by_hit.append(refs)
    return refs_by_hit

def render_span(doc, pages, offsets, start_hit, end_pos, folder, kind, n):
    """Render pages from a hit's start to an explicit end offset (used by P3 per-option)."""
    spi = start_hit['pi']
    epi = page_of(end_pos, offsets)
    refs = []
    for pi in range(spi, epi + 1):
        if is_spacer(pages[pi]): continue
        H = float(doc[pi].get_height())
        top = start_hit['top'] - 10 if pi == spi else 0
        if pi == epi and end_pos < offsets[-1]:
            _, _, ebottom = box_for(doc, pages, offsets, end_pos)
            bottom = ebottom - 8
        else:
            bottom = H
        if bottom <= top + 8: continue
        rel = f"{folder}/{kind}{n:02d}_p{pi + 1}.jpg"
        render_crop(doc[pi], top, bottom, os.path.join(FIG, rel)); refs.append(rel)
    if not refs:
        H = float(doc[spi].get_height())
        rel = f"{folder}/{kind}{n:02d}_p{spi + 1}_fb.jpg"
        render_crop(doc[spi], 0, H, os.path.join(FIG, rel)); refs.append(rel)
    return refs

def session_label(dirname):
    m = re.match(r'^(20\d\d)[ .](05|11)', dirname)
    if m: return f"{m.group(1)} {'May' if m.group(2) == '05' else 'Nov'}"
    m = re.match(r'^(20\d\d) (May|November)', dirname)
    if m: return f"{m.group(1)} {'May' if m.group(2) == 'May' else 'Nov'}"
    return dirname.replace(' Examination Session', '').replace(' \u7269\u7406HL', '')

def slug_for(dirname, filename):
    sess = session_label(dirname).replace(' ', '')
    tz = re.search(r'TZ\d+', filename)
    return f"{sess}_{tz.group(0) if tz else 'HL'}"

def find_qps(sess, paper):
    fp = os.path.join(BASE, sess)
    out = []
    for f in sorted(os.listdir(fp)):
        lf = f.lower()
        if f'paper_{paper}' not in lf: continue
        if 'markscheme' in lf or 'french' in lf or 'spanish' in lf or 'german' in lf: continue
        if not lf.endswith('.pdf'): continue
        out.append(f)
    return out

# ---------------- P1 (MCQ) ----------------
def p1_records(dirname, filename):
    qp = os.path.join(BASE, dirname, filename)
    ms = qp[:-4] + '_markscheme.pdf'
    if not os.path.exists(ms): return []
    qd, qpages, qfull, qoff = load(qp)
    md, mpages, mfull, moff = load(ms)
    qhits = [hit_dict(qd, qpages, qoff, m) for m in P1_HEAD.finditer(qfull)]
    # keep only a clean sequential 1..40 run
    seq = []
    expected = 1
    for h in qhits:
        # recover n from following context
        pass
    # simpler: require exactly 40 sequential headers
    clean_hits = []
    expected = 1
    for m in P1_HEAD.finditer(qfull):
        n = int(m.group(1))
        if n != expected: continue
        clean_hits.append(hit_dict(qd, qpages, qoff, m))
        expected += 1
        if expected > 40: break
    if len(clean_hits) != 40:
        qd.close(); md.close(); return []
    key = {}
    for m in MC_KEY.finditer(mfull):
        n = int(m.group(1))
        if n not in key: key[n] = m.group(2)
    # The markscheme body may contain solution snippets like "3. A force acts"
    # that also match N. A; accept as long as every key 1..40 is present
    # (taking the first occurrence, which is the compact answer-key table).
    if not all(n in key for n in range(1, 41)):
        qd.close(); md.close(); return []
    slug = slug_for(dirname, filename)
    folder = f"physics_hl_p1/{slug}"
    qimgs = image_segments(qd, qpages, qoff, clean_hits, folder, 'q', skip_spacers=False)
    # answer key page = page of first key entry
    first_key = next(MC_KEY.finditer(mfull))
    kpi = page_of(first_key.start(), moff)
    arel = f"{folder}/answer_key_p{kpi + 1}.jpg"
    render_crop(md[kpi], 0, float(md[kpi].get_height()), os.path.join(FIG, arel))
    tz = re.search(r'TZ\d+', filename)
    tzlab = (' ' + tz.group(0)) if tz else ''
    records = []
    for i, h in enumerate(clean_hits):
        qend = clean_hits[i + 1]['pos'] if i + 1 < 40 else len(qfull)
        qt = clean(qfull[h['pos']:qend])
        n = i + 1
        ch = key.get(n, '\u2013')
        records.append({
            'id': f"PHYS_HL_P1_{slug}_q{n:02d}",
            'subject': 'Physics', 'level': 'HL', 'topic': 'Physics HL', 'subtopic': None,
            'paper_type': 'Paper 1', 'command_term': None, 'marks': 1, 'difficulty': None,
            'question': qt, 'figure': None, 'answer': f"{n}. {ch}", 'explanation': None,
            'source': f"Physics HL P1 \u00b7 {session_label(dirname)}{tzlab}",
            'tags': [], 'authored_by': 'ib', 'knowledge_point_ids': [], 'answer_figure': None,
            'question_image': ','.join(qimgs[i]), 'answer_image': arel,
            'figure_image': None, 'book_id': None, 'source_type': 'paper',
            'category': 'past', 'review_status': 'new',
        })
    qd.close(); md.close()
    return records

# ---------------- P2 (section-prefixed) ----------------
def p2_records(dirname, filename):
    qp = os.path.join(BASE, dirname, filename)
    ms = qp[:-4] + '_markscheme.pdf'
    if not os.path.exists(ms): return []
    qd, qpages, qfull, qoff = load(qp)
    md, mpages, mfull, moff = load(ms)
    # QP: all section-prefixed question starts. Numbers RESET per section
    # (A1..A4, then B1..B4), so reset the expected counter when the letter changes.
    qhits = []
    expected = 1
    last_letter = None
    for m in SEC_Q.finditer(qfull):
        letter = m.group(1); num = int(m.group(2))
        if letter != last_letter:
            expected = 1; last_letter = letter
        if num != expected: continue
        qhits.append(hit_dict(qd, qpages, qoff, m, group=1))
        expected += 1
    if len(qhits) < 6:
        qd.close(); md.close(); return []
    # MS: walk same sequential filter (with per-section reset)
    mhits = []
    expected = 1
    last_letter = None
    for m in SEC_Q.finditer(mfull):
        letter = m.group(1); num = int(m.group(2))
        if letter != last_letter:
            expected = 1; last_letter = letter
        if num != expected: continue
        mhits.append(hit_dict(md, mpages, moff, m, group=1))
        expected += 1
    if len(mhits) != len(qhits):
        qd.close(); md.close(); return []
    slug = slug_for(dirname, filename)
    folder = f"physics_hl_p2/{slug}"
    qimgs = image_segments(qd, qpages, qoff, qhits, folder, 'q', skip_spacers=True)
    aimgs = image_segments(md, mpages, moff, mhits, folder, 'a', skip_spacers=False)
    tz = re.search(r'TZ\d+', filename)
    tzlab = (' ' + tz.group(0)) if tz else ''
    records = []
    for i, h in enumerate(qhits):
        qend = qhits[i + 1]['pos'] if i + 1 < len(qhits) else len(qfull)
        ast = mhits[i]['pos']; aend = mhits[i + 1]['pos'] if i + 1 < len(mhits) else len(mfull)
        qt = clean(qfull[h['pos']:qend]); at = clean(mfull[ast:aend])
        mk = sum(int(x) for x in MARKS.findall(qt)) or None
        records.append({
            'id': f"PHYS_HL_P2_{slug}_q{i + 1:02d}",
            'subject': 'Physics', 'level': 'HL', 'topic': 'Physics HL', 'subtopic': None,
            'paper_type': 'Paper 2', 'command_term': None, 'marks': mk, 'difficulty': None,
            'question': qt, 'figure': None, 'answer': at, 'explanation': None,
            'source': f"Physics HL P2 \u00b7 {session_label(dirname)}{tzlab}",
            'tags': [], 'authored_by': 'ib', 'knowledge_point_ids': [], 'answer_figure': None,
            'question_image': ','.join(qimgs[i]), 'answer_image': ','.join(aimgs[i]),
            'figure_image': None, 'book_id': None, 'source_type': 'paper',
            'category': 'past', 'review_status': 'new',
        })
    qd.close(); md.close()
    return records

# ---------------- P3 (option-prefixed) ----------------
def p3_records(dirname, filename):
    qp = os.path.join(BASE, dirname, filename)
    ms = qp[:-4] + '_markscheme.pdf'
    if not os.path.exists(ms): return []
    qd, qpages, qfull, qoff = load(qp)
    md, mpages, mfull, moff = load(ms)
    Qall = list(SEC_Q.finditer(qfull))
    Mall = list(SEC_Q.finditer(mfull))
    if not Qall:
        qd.close(); md.close(); return []
    # option order = first appearance of each letter in QP
    order = []
    for m in Qall:
        if m.group(1) not in order: order.append(m.group(1))
    slug = slug_for(dirname, filename)
    tz = re.search(r'TZ\d+', filename)
    tzlab = (' ' + tz.group(0)) if tz else ''
    records = []
    for L in order:
        qidx = [i for i, m in enumerate(Qall) if m.group(1) == L]
        midx = [i for i, m in enumerate(Mall) if m.group(1) == L]
        # verify sequential within option
        if len(qidx) != len(midx): continue
        ok = all(Qall[qidx[j]].group(2) == str(j + 1) and Mall[midx[j]].group(2) == str(j + 1)
                 for j in range(len(qidx)))
        if not ok: continue
        folder = f"physics_hl_p3/{slug}/OPT_{L}"
        # global next SEC_Q position bounds each question (any letter)
        for j in range(len(qidx)):
            qm = Qall[qidx[j]]; mm = Mall[midx[j]]
            qh = hit_dict(qd, qpages, qoff, qm, group=1)
            mh = hit_dict(md, mpages, moff, mm, group=1)
            qend = Qall[qidx[j] + 1].start(1) if j + 1 < len(qidx) else (Qall[qidx[j] + 1].start(1) if qidx[j] + 1 < len(Qall) else len(qfull))
            mend = Mall[midx[j] + 1].start(1) if midx[j] + 1 < len(Mall) else len(mfull)
            qt = clean(qfull[qh['pos']:qend]); at = clean(mfull[mh['pos']:mend])
            mk = sum(int(x) for x in MARKS.findall(qt)) or None
            qimgs = render_span(qd, qpages, qoff, qh, qend, folder, 'q', j + 1)
            aimgs = render_span(md, mpages, moff, mh, mend, folder, 'a', j + 1)
            records.append({
                'id': f"PHYS_HL_P3_{slug}_OPT_{L}_q{j + 1:02d}",
                'subject': 'Physics', 'level': 'HL', 'topic': 'Physics HL', 'subtopic': None,
                'paper_type': 'Paper 3', 'command_term': None, 'marks': mk, 'difficulty': None,
                'question': qt, 'figure': None, 'answer': at, 'explanation': None,
                'source': f"Physics HL P3 \u00b7 {session_label(dirname)}{tzlab} \u00b7 Option {L}",
                'tags': [], 'authored_by': 'ib', 'knowledge_point_ids': [], 'answer_figure': None,
                'question_image': ','.join(qimgs), 'answer_image': ','.join(aimgs),
                'figure_image': None, 'book_id': None, 'source_type': 'paper',
                'category': 'past', 'review_status': 'new',
            })
    qd.close(); md.close()
    return records

def main():
    all_records = []
    skipped = []
    for sess in sorted(os.listdir(BASE)):
        if not os.path.isdir(os.path.join(BASE, sess)): continue
        if not re.match(r'^20\d\d (May|November)', sess): continue
        y = int(sess[:4])
        if y < 2000 or y > 2015: continue
        for paper in ('1', '2', '3'):
            for fn in find_qps(sess, paper):
                try:
                    if paper == '1': recs = p1_records(sess, fn)
                    elif paper == '2': recs = p2_records(sess, fn)
                    else: recs = p3_records(sess, fn)
                except Exception as e:
                    skipped.append(f"{sess}/{fn}: ERROR {e}")
                    recs = []
                if not recs:
                    skipped.append(f"{sess}/{fn}: SKIP (unreliable segmentation)")
                    continue
                all_records.extend(recs)
                print(f"  {sess}/{fn}: {len(recs)} records")
    with open(MANIFEST, 'w', encoding='utf-8') as f:
        json.dump(all_records, f, ensure_ascii=False, indent=1)
    print(f"\nTOTAL records: {len(all_records)}")
    print(f"Skipped/SKIP lines: {len(skipped)}")
    for s in skipped: print("  -", s)
    print(f"Manifest -> {MANIFEST}")

if __name__ == '__main__':
    main()
