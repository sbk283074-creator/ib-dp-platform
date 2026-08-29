#!/usr/bin/env python3
"""
Crop question + answer images from Physics/Math past paper PDFs.

Strategy:
  1. Parse question ID → (subject, year, month, tz, paper, qnum, subpart)
  2. Find source PDFs (question paper + markscheme) using same walker as extract_pm.py
  3. Use pdfplumber extract_text_lines (with bboxes) to find question boundaries
  4. Crop each question's vertical band with pypdfium2 at 200 DPI
  5. Save JPEGs to backend/public/figures/
  6. Output JSON map: { question_id: { q: [paths], a: [paths] } }
"""
import json, os, re, sys, time
from pathlib import Path
import pdfplumber
import pypdfium2 as pdfium
from PIL import Image
import io

ROOT = "/Users/lucas.ma/Downloads/dp learning"
PHY_RAW = os.path.join(ROOT, "Physics-HL-Past Papers&Mark Schemes(1999.05~2025.11)")
MATH_RAW = os.path.join(ROOT, "IB 数学 AA  HL 历年真题")
PHY_CLS = os.path.join(ROOT, "Physics-HL-Topic questions")
MATH_CLS = os.path.join(ROOT, "IB数学AA  HL 分章练习", "IB数学AA-Mathmatics HL IB Question Bank")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public", "figures")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "app.db")
MAP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pm_image_map.json")
CKPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pm_crop_checkpoint.json")

MIN_YEAR = 2016
MONTHS = {"may": "05", "november": "11", "nov": "11"}
MONTH_NAME = {"05": "May", "11": "November"}
NON_EN = ("French", "Spanish", "German", "[German]")
DPI = 200
SCALE = DPI / 72.0

os.makedirs(OUT_DIR, exist_ok=True)

# ----------------------------------------------------------------- helpers

def session_year_label(s):
    m = re.search(r"(20\d\d)[ .](05|11)", s)
    if m:
        return int(m.group(1)), f"{m.group(1)}.{m.group(2)}", f"{m.group(1)} {MONTH_NAME[m.group(2)]}"
    m = re.search(r"(20\d\d)\s+(May|November|Nov)", s, re.I)
    if m:
        mm = MONTHS[m.group(2).lower()]
        name = "November" if mm == "11" else "May"
        return int(m.group(1)), f"{m.group(1)}.{mm}", f"{m.group(1)} {name}"
    m = re.search(r"(20\d\d)", s)
    if m:
        return int(m.group(1)), m.group(1), m.group(1)
    return None, None, None

def phy_raw_walker():
    items = []
    F = re.compile(r"^Physics_paper_(\d+[AB]?)_*(TZ\d)?_?HL(_markscheme)?\.pdf$")
    for d in sorted(os.listdir(PHY_RAW)):
        sdir = os.path.join(PHY_RAW, d)
        if not os.path.isdir(sdir):
            continue
        year, label, disp = session_year_label(d)
        if year is None or year < MIN_YEAR:
            continue
        files = [f for f in os.listdir(sdir) if not any(x in f for x in NON_EN)]
        parsed = []
        for f in files:
            m = F.match(f)
            if m:
                parsed.append((f, m.group(1), m.group(2), bool(m.group(3))))
        for paper_tok, tz in {(p, t) for (_, p, t, _) in parsed}:
            qfs = [f for f, p, t, isms in parsed if p == paper_tok and t == tz and not isms]
            mfs = [f for f, p, t, isms in parsed if p == paper_tok and t == tz and isms]
            for qf in qfs:
                stem = qf.replace(".pdf", "")
                mf = next((c for c in mfs if c.replace("_markscheme", "").replace(".pdf", "") == stem), None)
                items.append((label, disp, f"Paper {paper_tok}", tz, os.path.join(sdir, qf),
                              os.path.join(sdir, mf) if mf else None))
    return items

def math_raw_walker():
    items = []
    for d in sorted(os.listdir(MATH_RAW)):
        sdir = os.path.join(MATH_RAW, d)
        if not os.path.isdir(sdir):
            continue
        m = re.match(r"^(20\d\d)\.(11|5|05)HL$", d)
        if m:
            year = int(m.group(1))
            if year < MIN_YEAR:
                continue
            mon = "05" if m.group(2) == "5" else "11"
            label, disp = f"{m.group(1)}.{mon}", f"{m.group(1)} {MONTH_NAME[mon]}"
            for f in sorted(os.listdir(sdir)):
                if any(x in f for x in NON_EN) or "applications_and_interpretation" in f:
                    continue
                mm = re.match(r"Mathematics_analysis_and_approaches_paper_(\d+)__(TZ\d_)?HL(_markscheme)?\.pdf$", f)
                if not mm:
                    continue
                pn = int(mm.group(1)); tz = (mm.group(2) or "").rstrip("_") or None
                is_ms = bool(mm.group(3))
                path = os.path.join(sdir, f)
                if is_ms:
                    items.append((label, disp, f"Paper {pn}", tz, None, path, None))
                else:
                    items.append((label, disp, f"Paper {pn}", tz, path, None, None))
            continue
        for d2 in sorted(os.listdir(sdir)):
            sdir2 = os.path.join(sdir, d2)
            if not os.path.isdir(sdir2):
                continue
            year, label, disp = session_year_label(d2)
            if year is None or year < MIN_YEAR:
                continue
            for root2, dirs2, files2 in os.walk(sdir2):
                if any(x in root2 for x in NON_EN):
                    continue
                for f in sorted(files2):
                    if any(x in f for x in NON_EN) or "applications_and_interpretation" in f:
                        continue
                    mm = re.match(r"Mathematics_(analysis_and_approaches_)?paper_(\d+)(?:_([A-Za-z_]+))?__(TZ\d_)?HL(_markscheme)?\.pdf$", f)
                    if not mm:
                        continue
                    pn = int(mm.group(2)); opt = mm.group(3); tz = (mm.group(4) or "").rstrip("_") or None
                    is_ms = bool(mm.group(5))
                    paper = f"Paper {pn}" + (f" {opt.replace('_', ' ')}" if opt else "")
                    path = os.path.join(root2, f)
                    if is_ms:
                        items.append((label, disp, paper, tz, None, path, opt))
                    else:
                        items.append((label, disp, paper, tz, path, None, opt))
    return items

# ----------------------------------------------------------------- PDF text line extraction

def get_pdf_info(pdf_path):
    """Extract text lines with bboxes AND page heights from a PDF.
    Returns (lines, page_heights) where lines is list of dicts and page_heights is list of floats."""
    lines = []
    page_heights = []
    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages):
            page_heights.append(page.height)
            for tl in page.extract_text_lines():
                lines.append({
                    'text': tl['text'].strip(),
                    'page': pno,
                    'x0': tl['x0'],
                    'y0': tl['top'],
                    'x1': tl['x1'],
                    'y1': tl['bottom'],
                })
    return lines, page_heights

# ----------------------------------------------------------------- Noise filtering

def is_noise_line(text):
    s = text.strip()
    if not s:
        return True
    if re.fullmatch(r'–\s*\d+\s*–.*', s): return True
    if re.fullmatch(r'\d{4}\s*–\s*\d{4}[A-Z0-9]*', s): return True
    if re.fullmatch(r'M\d{2}/[0-9A-Z/]+', s): return True
    if re.fullmatch(r'\d+EP\d+', s): return True
    if re.fullmatch(r'©.*', s): return True
    if re.fullmatch(r'[Tt]urn\s+over.*', s): return True
    if re.fullmatch(r'[.\s·]+', s): return True
    if re.fullmatch(r'(continued|blank page).*', s, re.I): return True
    if re.fullmatch(r'(Do not|do NOT).*', s, re.I): return True
    if re.fullmatch(r'\d+\s+pages?\s*©.*', s, re.I): return True
    if re.fullmatch(r'\d+\s+pages?', s): return True
    return False

# ----------------------------------------------------------------- Question boundary detection

QNUM_RE = re.compile(r'^(\d{1,2})\.\s+')

def find_q_boundaries(lines, page_heights):
    """Find question start positions in a question paper PDF.
    Returns dict: {qnum: {page, y0, x0}}"""
    boundaries = {}
    for ln in lines:
        if is_noise_line(ln['text']):
            continue
        m = QNUM_RE.match(ln['text'])
        if m:
            qnum = int(m.group(1))
            if 1 <= qnum <= 50:
                if qnum not in boundaries:
                    boundaries[qnum] = {
                        'page': ln['page'],
                        'y0': ln['y0'],
                        'x0': ln['x0'],
                    }
    return boundaries

def find_ms_boundaries(lines, page_heights, kind='phys'):
    """Find question start positions in a markscheme PDF.
    kind: 'phys' or 'math'.
    Returns dict: {qnum: {page, y0}} for math, {(qnum, letter): {page, y0}} for phys."""
    boundaries = {}
    if kind == 'math':
        for ln in lines:
            if is_noise_line(ln['text']):
                continue
            m = re.match(r'^(\d{1,2})\.\s*(?:\(([a-z])\))?\s*(.*)$', ln['text'])
            if m:
                qnum = int(m.group(1))
                if 1 <= qnum <= 50:
                    if qnum not in boundaries:
                        boundaries[qnum] = {'page': ln['page'], 'y0': ln['y0']}
    else:
        for ln in lines:
            if is_noise_line(ln['text']):
                continue
            m = re.match(r'^(\d{1,2})\.?\s*([a-z])(?:\s+([ivxlc]+))?\s+(.*)$', ln['text'])
            if m:
                qnum = int(m.group(1))
                letter = m.group(2)
                if 1 <= qnum <= 50 and 'a' <= letter <= 'h':
                    key = (qnum, letter)
                    if key not in boundaries:
                        boundaries[key] = {'page': ln['page'], 'y0': ln['y0']}
            m2 = re.match(r'^(\d{1,2})\.\s*$', ln['text'])
            if m2:
                qnum = int(m2.group(1))
                if 1 <= qnum <= 50:
                    if qnum not in boundaries:
                        boundaries[qnum] = {'page': ln['page'], 'y0': ln['y0']}
    return boundaries

# ----------------------------------------------------------------- Cropping

def crop_region(pdf_doc, page_idx, y0, y1, out_path, page_h):
    """Crop a region from a PDF page and save as JPEG.
    Uses an already-open pypdfium2 PdfDocument."""
    page = pdf_doc[page_idx]
    w, h = page.get_size()
    
    top = max(0, y0 - 5)
    bottom = min(h, y1 + 5)
    
    bitmap = page.render(scale=SCALE)
    pil_img = bitmap.to_pil()
    
    px0 = 0
    px1 = pil_img.width
    py0 = int(top * SCALE)
    py1 = int(bottom * SCALE)
    
    px0 = max(0, min(px0, pil_img.width))
    px1 = max(px0 + 1, min(px1, pil_img.width))
    py0 = max(0, min(py0, pil_img.height))
    py1 = max(py0 + 1, min(py1, pil_img.height))
    
    cropped = pil_img.crop((px0, py0, px1, py1))
    cropped.save(out_path, 'JPEG', quality=90)

def crop_questions_for_session(qpdf_path, mspdf_path, parsed_qs, is_mcq, ms_kind):
    """Process one paper session: crop all questions.
    Returns dict {question_id: {q: [paths], a: [paths]}}"""
    result = {}
    
    # Load text lines + page heights once
    q_lines, q_page_h = get_pdf_info(qpdf_path) if qpdf_path else ([], [])
    ms_lines, ms_page_h = get_pdf_info(mspdf_path) if mspdf_path else ([], [])
    
    # Find boundaries once
    q_boundaries = find_q_boundaries(q_lines, q_page_h) if q_lines else {}
    ms_boundaries = find_ms_boundaries(ms_lines, ms_page_h, kind=ms_kind) if ms_lines else {}
    
    # Open PDF documents once for rendering
    q_pdf_doc = pdfium.PdfDocument(qpdf_path) if qpdf_path else None
    ms_pdf_doc = pdfium.PdfDocument(mspdf_path) if mspdf_path else None
    
    try:
        for qi in parsed_qs:
            qnum = qi['qnum']
            subpart = qi.get('subpart')
            qid = qi['raw_id']
            
            q_paths = []
            a_paths = []
            
            # --- Crop question ---
            if q_pdf_doc and qnum in q_boundaries:
                b = q_boundaries[qnum]
                start_page = b['page']
                start_y = b['y0']
                
                # Find end: next question's start
                next_q = qnum + 1
                end_page = len(q_page_h) - 1
                end_y = q_page_h[start_page] if start_page < len(q_page_h) else 1000
                
                if next_q in q_boundaries:
                    nb = q_boundaries[next_q]
                    if nb['page'] > start_page:
                        end_page = start_page
                        end_y = q_page_h[start_page]
                    else:
                        end_page = nb['page']
                        end_y = nb['y0']
                else:
                    end_page = start_page
                    end_y = q_page_h[start_page] if start_page < len(q_page_h) else 1000
                
                # If subpart requested, narrow to the subpart
                if subpart:
                    sub_re = re.compile(rf'^\({subpart}\)\s')
                    sub_start = None
                    sub_end = None
                    for ln in q_lines:
                        if ln['page'] < start_page:
                            continue
                        if ln['page'] == start_page and ln['y0'] < start_y:
                            continue
                        if ln['page'] > end_page:
                            break
                        if ln['page'] == end_page and ln['y0'] >= end_y:
                            break
                        if sub_start is None:
                            if sub_re.match(ln['text']):
                                sub_start = ln
                        else:
                            m = re.match(r'^\(([a-z])\)\s', ln['text'])
                            if m and m.group(1) > subpart:
                                sub_end = ln
                                break
                    if sub_start:
                        start_page = sub_start['page']
                        start_y = sub_start['y0']
                        if sub_end:
                            end_page = sub_end['page']
                            end_y = sub_end['y0']
                
                # Crop (possibly multi-page)
                if end_page > start_page:
                    for pno in range(start_page, end_page + 1):
                        y_start = start_y if pno == start_page else 0
                        y_end = end_y if pno == end_page else q_page_h[pno]
                        fname = f"pmq-{qid.replace('RAW-','').replace('-','_')}-p{pno}.jpg"
                        fpath = os.path.join(OUT_DIR, fname)
                        try:
                            crop_region(q_pdf_doc, pno, y_start, y_end, fpath, q_page_h[pno])
                            q_paths.append(f"/figures/{fname}")
                        except Exception as e:
                            print(f"    [ERR] Q crop {qid} p{pno}: {e}", flush=True)
                else:
                    fname = f"pmq-{qid.replace('RAW-','').replace('-','_')}-p{start_page}.jpg"
                    fpath = os.path.join(OUT_DIR, fname)
                    try:
                        crop_region(q_pdf_doc, start_page, start_y, end_y, fpath, q_page_h[start_page])
                        q_paths.append(f"/figures/{fname}")
                    except Exception as e:
                        print(f"    [ERR] Q crop {qid}: {e}", flush=True)
            
            # --- Crop answer (skip for MCQ — markscheme is just a letter key) ---
            if ms_pdf_doc and not is_mcq:
                # Find start in markscheme
                start = None
                if ms_kind == 'math':
                    start = ms_boundaries.get(qnum)
                else:
                    if subpart:
                        start = ms_boundaries.get((qnum, subpart))
                    if not start:
                        for key, val in sorted(ms_boundaries.items()):
                            if isinstance(key, tuple) and key[0] == qnum:
                                start = val
                                break
                    if not start:
                        start = ms_boundaries.get(qnum)
                
                if start:
                    start_page = start['page']
                    start_y = start['y0']
                    
                    # Find end
                    end_page = len(ms_page_h) - 1
                    end_y = ms_page_h[start_page] if start_page < len(ms_page_h) else 1000
                    
                    if ms_kind == 'math':
                        next_q = qnum + 1
                        if next_q in ms_boundaries:
                            nb = ms_boundaries[next_q]
                            if nb['page'] > start_page:
                                end_page = start_page
                                end_y = ms_page_h[start_page]
                            else:
                                end_page = nb['page']
                                end_y = nb['y0']
                    else:
                        # Find next boundary
                        all_keys = sorted(ms_boundaries.keys(),
                            key=lambda k: (ms_boundaries[k]['page'], ms_boundaries[k]['y0']))
                        found = False
                        for key in all_keys:
                            if found:
                                b = ms_boundaries[key]
                                if b['page'] > start_page:
                                    end_page = start_page
                                    end_y = ms_page_h[start_page]
                                else:
                                    end_page = b['page']
                                    end_y = b['y0']
                                break
                            if isinstance(key, tuple) and key[0] == qnum:
                                if subpart and key == (qnum, subpart):
                                    found = True
                                elif not subpart:
                                    found = True
                    
                    # Crop
                    if end_page > start_page:
                        for pno in range(start_page, end_page + 1):
                            y_start = start_y if pno == start_page else 0
                            y_end = end_y if pno == end_page else ms_page_h[pno]
                            fname = f"pma-{qid.replace('RAW-','').replace('-','_')}-p{pno}.jpg"
                            fpath = os.path.join(OUT_DIR, fname)
                            try:
                                crop_region(ms_pdf_doc, pno, y_start, y_end, fpath, ms_page_h[pno])
                                a_paths.append(f"/figures/{fname}")
                            except Exception as e:
                                print(f"    [ERR] A crop {qid} p{pno}: {e}", flush=True)
                    else:
                        fname = f"pma-{qid.replace('RAW-','').replace('-','_')}-p{start_page}.jpg"
                        fpath = os.path.join(OUT_DIR, fname)
                        try:
                            crop_region(ms_pdf_doc, start_page, start_y, end_y, fpath, ms_page_h[start_page])
                            a_paths.append(f"/figures/{fname}")
                        except Exception as e:
                            print(f"    [ERR] A crop {qid}: {e}", flush=True)
            
            if q_paths or a_paths:
                result[qid] = {'q': q_paths, 'a': a_paths}
    finally:
        if q_pdf_doc: q_pdf_doc.close()
        if ms_pdf_doc: ms_pdf_doc.close()
    
    return result

# ----------------------------------------------------------------- ID parsing

def parse_question_id(qid):
    parts = qid.split('-')
    subject = 'Physics' if parts[0] == 'PHY' else 'Math AA HL'
    
    if parts[1] == 'RAW':
        year = parts[2]
        month = parts[3]
        idx = 4
        if parts[idx].startswith('TZ'):
            tz = parts[idx]
            idx += 1
        else:
            tz = None
        paper_str = parts[idx]
        idx += 1
        q_str = parts[idx]
        m = re.match(r'Q(\d+)([a-f]?)', q_str)
        qnum = int(m.group(1)) if m else None
        subpart = m.group(2) if m and m.group(2) else None
        return {
            'subject': subject, 'type': 'RAW',
            'year': year, 'month': month, 'tz': tz,
            'paper': paper_str, 'qnum': qnum, 'subpart': subpart,
            'raw_id': qid,
        }
    elif parts[1] == 'CLS':
        folder = parts[2]
        paper = parts[3]
        seq = int(parts[4])
        return {
            'subject': subject, 'type': 'CLS',
            'folder': folder, 'paper': paper, 'seq': seq,
            'raw_id': qid,
        }
    return None

# ----------------------------------------------------------------- Source PDF finder

def find_source_pdfs(qinfo):
    if qinfo['type'] == 'RAW':
        label = f"{qinfo['year']}.{qinfo['month']}"
        tz = qinfo['tz']
        paper = qinfo['paper']
        # Extract "1A", "1B", or just "1" from "Paper1A", "Paper1B", "Paper1"
        pm = re.match(r'Paper(\d+[A-F]?)', paper)
        paper_num = pm.group(1) if pm else re.match(r'Paper(\d+)', paper).group(1)

        if qinfo['subject'] == 'Physics':
            for slabel, sdisp, spaper, stz, qp, msp in phy_raw_walker():
                if slabel == label and spaper == f"Paper {paper_num}" and (stz or '') == (tz or ''):
                    return qp, msp
        else:
            sessions = math_raw_walker()
            paired = {}
            for slabel, sdisp, spaper, stz, qp, msp, opt in sessions:
                key = (slabel, spaper, stz)
                paired.setdefault(key, {'q': None, 'ms': None})
                if qp: paired[key]['q'] = qp
                if msp: paired[key]['ms'] = msp
            
            paper_full = f"Paper {paper_num}"
            if 'Calculus' in paper: paper_full = "Paper 3 Calculus"
            elif 'Discrete' in paper: paper_full = "Paper 3 Discrete mathematics"
            elif 'Sets' in paper: paper_full = "Paper 3 Sets relations and groups"
            elif 'Statistics' in paper: paper_full = "Paper 3 Statistics and probability"
            
            for key, val in paired.items():
                slabel, spaper, stz = key
                if slabel == label and spaper == paper_full and (stz or '') == (tz or ''):
                    return val['q'], val['ms']
    elif qinfo['type'] == 'CLS':
        folder = qinfo['folder']
        paper = qinfo['paper']
        paper_name = f"HL-paper{paper[1]}"
        base = PHY_CLS if qinfo['subject'] == 'Physics' else MATH_CLS

        # Map ID folder names (no space) to actual folder names
        actual_folder = folder
        for f in os.listdir(base):
            if f.replace(' ', '') == folder:
                actual_folder = f
                break

        fdir = os.path.join(base, actual_folder)
        if not os.path.isdir(fdir):
            return None, None
        msf = os.path.join(fdir, f"markscheme-{paper_name}.pdf")
        if os.path.exists(msf):
            return None, msf  # Classified: only markscheme has Q+A
    return None, None

# ----------------------------------------------------------------- Classified bank cropping

def find_classified_blocks(lines, page_heights):
    """For classified banks: find blocks of (question, markscheme_start, examiners_start).
    Returns list of dicts with keys: page, y0, y1, type ('q' | 'a' | 'e').
    Block structure: [Q lines] Markscheme [A lines] Examiners report [E lines] ... next Q."""
    blocks = []
    for ln in lines:
        t = ln['text'].strip()
        if t == 'Markscheme':
            blocks.append({'page': ln['page'], 'y0': ln['y0'], 'type': 'a_start'})
        elif t == 'Examiners report':
            blocks.append({'page': ln['page'], 'y0': ln['y0'], 'type': 'e_start'})
    return blocks

def crop_classified_session(mspdf_path, parsed_qs):
    """Crop Q+A images for a classified bank session.
    Since markscheme repeats the prompt, we crop:
      - Q: from end of last block's "Examiners report" to "Markscheme"
      - A: from "Markscheme" to "Examiners report"
    Returns dict {qid: {q: [paths], a: [paths]}}"""
    result = {}
    lines, page_heights = get_pdf_info(mspdf_path)
    blocks = find_classified_blocks(lines, page_heights)
    
    if not blocks:
        print(f"    [WARN] No Markscheme markers found in classified PDF", flush=True)
        return result
    
    ms_pdf_doc = pdfium.PdfDocument(mspdf_path)
    try:
        for i, qi in enumerate(parsed_qs):
            seq = qi['seq']  # 1-based sequence number within the topic/paper
            qid = qi['raw_id']
            
            # The seq-th question corresponds to the (i)-th "Markscheme" block
            # blocks has alternating: a_start, e_start, a_start, e_start, ...
            block_idx = (seq - 1) * 2  # a_start for this question
            a_start = blocks[block_idx] if block_idx < len(blocks) else None
            e_start = blocks[block_idx + 1] if block_idx + 1 < len(blocks) else None
            
            # Q region: from end of previous block's examiners_report to this Markscheme
            prev_e = blocks[block_idx - 1] if block_idx > 0 else None
            
            q_paths = []
            a_paths = []
            
            # --- Q crop ---
            if a_start:
                # Q starts after previous Examiners report (or top of page)
                if prev_e:
                    q_start_page = prev_e['page']
                    q_start_y = prev_e['y0']
                else:
                    q_start_page = 0
                    q_start_y = 0
                
                # Q ends at this Markscheme
                q_end_page = a_start['page']
                q_end_y = a_start['y0']
                
                # Crop Q
                safe_qid = qid.replace('CLS-','').replace('-','_')
                if q_end_page > q_start_page:
                    for pno in range(q_start_page, q_end_page + 1):
                        y_start = q_start_y if pno == q_start_page else 0
                        y_end = q_end_y if pno == q_end_page else page_heights[pno]
                        fname = f"clsq-{safe_qid}-p{pno}.jpg"
                        fpath = os.path.join(OUT_DIR, fname)
                        try:
                            crop_region(ms_pdf_doc, pno, y_start, y_end, fpath, page_heights[pno])
                            q_paths.append(f"/figures/{fname}")
                        except Exception as e:
                            print(f"    [ERR] Q crop {qid} p{pno}: {e}", flush=True)
                else:
                    fname = f"clsq-{safe_qid}-p{q_start_page}.jpg"
                    fpath = os.path.join(OUT_DIR, fname)
                    try:
                        crop_region(ms_pdf_doc, q_start_page, q_start_y, q_end_y, fpath, page_heights[q_start_page])
                        q_paths.append(f"/figures/{fname}")
                    except Exception as e:
                        print(f"    [ERR] Q crop {qid}: {e}", flush=True)
            
            # --- A crop ---
            if a_start and e_start:
                a_start_page = a_start['page']
                a_start_y = a_start['y0']
                a_end_page = e_start['page']
                a_end_y = e_start['y0']
                
                safe_qid = qid.replace('CLS-','').replace('-','_')
                if a_end_page > a_start_page:
                    for pno in range(a_start_page, a_end_page + 1):
                        y_start = a_start_y if pno == a_start_page else 0
                        y_end = a_end_y if pno == a_end_page else page_heights[pno]
                        fname = f"clsa-{safe_qid}-p{pno}.jpg"
                        fpath = os.path.join(OUT_DIR, fname)
                        try:
                            crop_region(ms_pdf_doc, pno, y_start, y_end, fpath, page_heights[pno])
                            a_paths.append(f"/figures/{fname}")
                        except Exception as e:
                            print(f"    [ERR] A crop {qid} p{pno}: {e}", flush=True)
                else:
                    fname = f"clsa-{safe_qid}-p{a_start_page}.jpg"
                    fpath = os.path.join(OUT_DIR, fname)
                    try:
                        crop_region(ms_pdf_doc, a_start_page, a_start_y, a_end_y, fpath, page_heights[a_start_page])
                        a_paths.append(f"/figures/{fname}")
                    except Exception as e:
                        print(f"    [ERR] A crop {qid}: {e}", flush=True)
            
            if q_paths or a_paths:
                result[qid] = {'q': q_paths, 'a': a_paths}
    finally:
        ms_pdf_doc.close()
    
    return result

# ----------------------------------------------------------------- Main

def main():
    import sqlite3
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, subject, source FROM questions WHERE subject IN ('Physics', 'Math AA HL') ORDER BY id"
    ).fetchall()
    conn.close()
    
    print(f"Total questions to process: {len(rows)}", flush=True)
    
    # Group by source
    groups = {}
    for r in rows:
        groups.setdefault(r['source'], []).append(r['id'])
    
    print(f"Unique source groups: {len(groups)}", flush=True)
    
    # Load checkpoint
    done_sources = set()
    if os.path.exists(CKPT_PATH):
        with open(CKPT_PATH) as f:
            done_sources = set(json.load(f).get('done_sources', []))
    
    all_results = {}
    if os.path.exists(MAP_PATH):
        with open(MAP_PATH) as f:
            all_results = json.load(f)
    
    processed = 0
    for src, qids in sorted(groups.items()):
        if src in done_sources:
            continue
        
        first = parse_question_id(qids[0])
        if not first:
            print(f"  [SKIP] Can't parse: {qids[0]}", flush=True)
            done_sources.add(src)
            continue
        
        # Classified banks: only markscheme PDF
        if first['type'] == 'CLS':
            qpdf, mspdf = find_source_pdfs(first)
            if not mspdf:
                print(f"  [SKIP] No MS for classified: {src}", flush=True)
                done_sources.add(src)
                continue
            
            parsed_qs = [parse_question_id(qid) for qid in qids]
            parsed_qs = [pq for pq in parsed_qs if pq]
            
            print(f"  [CLS:{src}] {len(parsed_qs)} Qs", flush=True)
            
            try:
                result = crop_classified_session(mspdf, parsed_qs)
                all_results.update(result)
                done_sources.add(src)
                
                with open(CKPT_PATH, 'w') as f:
                    json.dump({'done_sources': list(done_sources)}, f)
                with open(MAP_PATH, 'w') as f:
                    json.dump(all_results, f, ensure_ascii=False)
                
                processed += 1
                print(f"    -> {len(result)}/{len(parsed_qs)} cropped", flush=True)
            except Exception as e:
                print(f"    [ERR] {e}", flush=True)
                import traceback
                traceback.print_exc()
            continue
        
        # Raw past papers
        qpdf, mspdf = find_source_pdfs(first)
        
        if not qpdf and not mspdf:
            print(f"  [SKIP] No PDFs: {src}", flush=True)
            done_sources.add(src)
            continue
        
        is_mcq = first['subject'] == 'Physics' and re.match(r'Paper1[AB]?$', first.get('paper') or '')
        ms_kind = 'math' if first['subject'] == 'Math AA HL' else 'phys'
        
        parsed_qs = [parse_question_id(qid) for qid in qids]
        parsed_qs = [pq for pq in parsed_qs if pq]
        
        print(f"  [{src}] {len(parsed_qs)} Qs, Q={'y' if qpdf else 'n'} MS={'y' if mspdf else 'n'} MCQ={is_mcq}", flush=True)
        
        try:
            result = crop_questions_for_session(qpdf, mspdf, parsed_qs, is_mcq, ms_kind)
            all_results.update(result)
            done_sources.add(src)
            
            with open(CKPT_PATH, 'w') as f:
                json.dump({'done_sources': list(done_sources)}, f)
            with open(MAP_PATH, 'w') as f:
                json.dump(all_results, f, ensure_ascii=False)
            
            processed += 1
            print(f"    -> {len(result)}/{len(parsed_qs)} cropped", flush=True)
        except Exception as e:
            print(f"    [ERR] {e}", flush=True)
            import traceback
            traceback.print_exc()
    
    with open(MAP_PATH, 'w') as f:
        json.dump(all_results, f, ensure_ascii=False)
    
    print(f"\nDone. Processed {processed} sources. Total: {len(all_results)} questions with images.", flush=True)

if __name__ == '__main__':
    main()
