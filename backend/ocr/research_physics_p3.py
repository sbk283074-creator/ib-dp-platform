#!/usr/bin/env python3
"""Session 6 research only: Physics HL Paper 3. No extraction/DB writes."""
import os, re, json
import pypdfium2 as pdfium

BASE = "/Users/lucas.ma/Downloads/dp learning/Physics-HL-Past Papers&Mark Schemes(1999.05~2025.11)"
YEAR_RE = re.compile(r'^20(?:1[6-9]|2[0-5])')
QP_HEAD = re.compile(r'(?m)(?:^|[\r\n\ufffe])\s*(\d{1,2})\.(?!\d)\s+(?=[A-Z(])')

def load(path):
    d = pdfium.PdfDocument(path)
    pages = [d[i].get_textpage().get_text_range() for i in range(len(d))]
    full = "\n".join(pages)
    images = []
    for i in range(len(d)):
        for o in d[i].get_objects():
            try:
                if o.type == 3: images.append((i + 1, o.get_px_size(), o.get_bounds()))
            except Exception: pass
    d.close()
    return pages, full, images

def ranges_from_first_pages(text):
    # Header table form: Option A — Relativity 3 – 7
    return [(x, int(a), int(b)) for x, a, b in re.findall(
        r'Option\s+([A-D])\s+[—–-]\s*[^\r\n]+?(\d+)\s*[–-]\s*(\d+)', text, re.I)]

def qp_hits(full):
    return [(int(m.group(1)), m.start()) for m in QP_HEAD.finditer(full)]

def main():
    rows = []
    for dirname in sorted(os.listdir(BASE)):
        dp = os.path.join(BASE, dirname)
        if not os.path.isdir(dp) or not YEAR_RE.match(dirname): continue
        for filename in sorted(os.listdir(dp)):
            lf = filename.lower()
            if 'paper_3' not in lf or 'markscheme' in lf or any(k in lf for k in ('french','spanish','german')): continue
            ms = filename[:-4] + '_markscheme.pdf'
            qp_pages, qp_full, qp_images = load(os.path.join(dp, filename))
            ms_pages, ms_full, ms_images = load(os.path.join(dp, ms))
            ranges = ranges_from_first_pages('\n'.join(qp_pages[:3]))
            total_from_ranges = (ranges[0][1] - 1) + sum(b - a + 1 for _, a, b in ranges)
            hits = qp_hits(qp_full)
            rows.append({
                'dir': dirname, 'qp': filename, 'ms': ms,
                'qp_pages': len(qp_pages), 'ms_pages': len(ms_pages),
                'ranges': ranges, 'expected_records': total_from_ranges,
                'qp_header_hits': [n for n, _ in hits],
                'qp_image_objects': len(qp_images), 'ms_image_objects': len(ms_images),
                'qp_pua': sum(0xE000 <= ord(c) <= 0xF8FF for c in qp_full),
                'ms_pua': sum(0xE000 <= ord(c) <= 0xF8FF for c in ms_full),
                'qp_spacers': sum('Please do not write on this page' in p and len(p.strip()) < 180 for p in qp_pages),
                'ms_spacers': sum('Please do not write on this page' in p and len(p.strip()) < 180 for p in ms_pages),
                'ms_has_table_header': bool(re.search(r'(?m)^\s*Question\s+Answers\s+Notes\s+Total', ms_full)),
            })
    print('INVENTORY_COUNT', len(rows))
    print('EXPECTED_ALL_OPTION_RECORDS', sum(r['expected_records'] for r in rows))
    for r in rows: print(json.dumps(r, ensure_ascii=False))
    missing_sessions = []
    for session in ('2021 May', '2021 November', '2022 May', '2022 November', '2025.05', '2025.11'):
        if not any(r['dir'] == session or r['dir'].startswith(session) for r in rows): missing_sessions.append(session)
    print('NO_P3_FILES_FOR', missing_sessions)

if __name__ == '__main__': main()
