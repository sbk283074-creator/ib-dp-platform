#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render figure pages for questions and link them via the `figure` column.

For each question in physics_math_import.json:
  - resolve the source QUESTION pdf (raw past papers via walkers; classified via HL-paperN.pdf)
  - locate the page: raw -> question-number line start; classified -> text-prefix search
  - if that page contains vector graphics / images (>= MIN_VEC elements), render it once
    (dedupe by (pdf, page)) to backend/public/figures/<key>.jpg
  - UPDATE questions SET figure = '/figures/<key>.jpg' WHERE id = ?

Resumable via figures_checkpoint.json (done source keys).
Usage: python3 extract_figures.py
"""
import json, os, re, sqlite3, sys
import pdfplumber
import pypdfium2 as pdfium

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_pm as X

ROOT = X.ROOT
HERE = os.path.dirname(os.path.abspath(__file__))
FIG_DIR = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/public/figures"
DB_PATH = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/data/app.db"
IMPORT_JSON = os.path.join(HERE, "physics_math_import.json")
CKPT = os.path.join(HERE, "figures_checkpoint.json")
MIN_VEC = 15            # vector elements to consider a page as "has a figure"
RENDER_SCALE = 1.5
JPEG_Q = 82

os.makedirs(FIG_DIR, exist_ok=True)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def page_has_figure(pg):
    return len(pg.lines) + len(pg.rects) + len(pg.curves) + len(pg.images) >= MIN_VEC


def find_page_by_qnum_pdf(pdf, qnum):
    pat = re.compile(rf"^{qnum}\.\s")
    pat2 = re.compile(rf"^{qnum}\.$")
    for i, pg in enumerate(pdf.pages):
        for ln in (pg.extract_text() or "").split("\n"):
            s = ln.strip()
            if pat.match(s) or pat2.fullmatch(s):
                return i
    return None


def find_page_by_windows_pdf(pdf, qtext, page_norms=None):
    """Search overlapping 30-char windows of the cleaned question text across pages
    (tolerates markscheme prompts being abbreviated vs the question PDF).
    page_norms: optional list of precomputed normalized page texts."""
    nq = norm(clean_qtext(qtext))
    windows = [nq[i:i + 30] for i in range(0, max(1, len(nq) - 25), 15)]
    windows = [w for w in windows if len(w) >= 24]
    if not windows:
        return None
    if page_norms is None:
        page_norms = [norm(pg.extract_text() or "") for pg in pdf.pages]
    for i, t in enumerate(page_norms):
        if not t:
            continue
        for w in windows:
            if w in t:
                return i
    return None


def clean_qtext(qtext):
    """Strip [N/A] markers and leading subpart markers (a. / e.iii.) from a classified prompt."""
    t = re.sub(r"\[N/A\]", " ", qtext or "")
    t = re.sub(r"(?m)^[a-z]+(?:\.[ivxlc]+)*\.?\s*", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def render_page(path, page_idx, out_path):
    pdf = pdfium.PdfDocument(path)
    try:
        page = pdf[page_idx]
        pil = page.render(scale=RENDER_SCALE).to_pil()
        pil.convert("RGB").save(out_path, quality=JPEG_Q)
    finally:
        pdf.close()


def file_key(rel):
    return re.sub(r"[^\w.-]+", "_", rel)


# ---------------------------------------------------------------- source resolution
def build_raw_map(walker, is_phys):
    """-> {(label, tz): {paper_norm: path}}  paper_norm = paper.lower() without spaces"""
    m = {}
    for item in walker():
        if is_phys:
            label, disp, paper, tz, qp, msp = item
            path = qp
        else:
            label, disp, paper, tz, path, is_ms, opt = item
            if is_ms:
                continue
        key = (label, tz)
        m.setdefault(key, {})[paper.lower().replace(" ", "")] = path
    return m


def resolve(rec, raw_phys, raw_math):
    """-> (pdf_path, group_key, qnum_or_None, text_prefix_or_None) or None"""
    rid = rec["id"]
    if rid.startswith(("PHY-RAW-", "MATH-RAW-")):
        parts = rid.split("-")
        label = f"{parts[2]}.{parts[3]}"
        tz = None
        pi = None
        for i, p in enumerate(parts[4:], start=4):
            if p in ("TZ1", "TZ2", "TZ3"):
                tz = p
            elif p.startswith("Paper"):
                pi = i
                break
        if pi is None:
            return None
        pm = re.match(r"Paper(\d+[AB]?)(.*)", parts[pi])
        if not pm:
            return None
        paper_norm = ("paper" + pm.group(1) + (pm.group(2) or "")).lower()
        qm = re.search(r"-Q(\d+)", rid)
        qnum = int(qm.group(1)) if qm else None
        pool = raw_phys if rid.startswith("PHY-RAW-") else raw_math
        path = pool.get((label, tz), {}).get(paper_norm)
        return (path, f"R|{label}|{tz or ''}|{paper_norm}", qnum, None) if path else None

    # classified: PHY-CLS-Topic4-P2-007 / MATH-CLS-Topic1-P2-005
    m = re.match(r"(PHY|MATH)-CLS-(.+)-P(\d+)-(\d+)$", rid)
    if not m:
        return None
    subj, folder, pnum = m.group(1), m.group(2), m.group(3)
    base = X.PHY_CLS if subj == "PHY" else X.MATH_CLS
    fm = re.match(r"Topic(\d+)", folder)
    if fm:
        folder = f"Topic {int(fm.group(1))}"
    om = re.match(r"Option([A-D])", folder)
    if om:
        folder = f"Option {om.group(1)}"
    qpdf = os.path.join(base, folder, f"HL-paper{pnum}.pdf")
    if not os.path.exists(qpdf):
        return None
    return (qpdf, f"C|{subj}|{folder}|{pnum}", None, rec["question"])


def main():
    ckpt = {"done": []}
    if os.path.exists(CKPT):
        try:
            ckpt = json.load(open(CKPT))
        except Exception:
            pass
    done = set(ckpt["done"])

    records = json.load(open(IMPORT_JSON))
    print(f"[fig] {len(records)} records", flush=True)

    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()

    raw_phys = build_raw_map(X.phy_raw_walker, True)
    raw_math = build_raw_map(X.math_raw_walker, False)
    print(f"[fig] raw phys files={sum(len(v) for v in raw_phys.values())} math files={sum(len(v) for v in raw_math.values())}", flush=True)

    groups = {}
    unmapped = 0
    for rec in records:
        r = resolve(rec, raw_phys, raw_math)
        if not r:
            unmapped += 1
            continue
        path, key, qnum, tpref = r
        groups.setdefault(key, {"path": path, "recs": []})["recs"].append((rec, qnum, tpref))
    print(f"[fig] groups={len(groups)} unmapped={unmapped}", flush=True)

    stats = {"files": 0, "pages_rendered": 0, "questions_linked": 0,
             "no_figure_on_page": 0, "page_not_found": 0}

    for key, g in sorted(groups.items()):
        if key in done:
            print(f"  [skip] {key}", flush=True)
            continue
        path = g["path"]
        rel = os.path.relpath(path, ROOT)
        # locate pages + figure detection in a single pdf open
        with pdfplumber.open(path) as pdf:
            n_pages = len(pdf.pages)
            need_text = any(tpref for (_rec, _qn, tpref) in g["recs"])
            page_norms = None
            if need_text:
                page_norms = [norm(pg.extract_text() or "") for pg in pdf.pages]
            page_cache = {}
            for rec, qnum, tpref in g["recs"]:
                page = None
                if qnum is not None:
                    page = find_page_by_qnum_pdf(pdf, qnum)
                if page is None and tpref:
                    page = find_page_by_windows_pdf(pdf, tpref, page_norms)
                page_cache[rec["id"]] = page
            fig_flags = {}
            for rid, page in page_cache.items():
                if page is None or page >= n_pages:
                    continue
                if page not in fig_flags:
                    fig_flags[page] = page_has_figure(pdf.pages[page])
        for rid, page in page_cache.items():
            if page is None or page >= n_pages:
                stats["page_not_found"] += 1
                continue
            if not fig_flags.get(page):
                stats["no_figure_on_page"] += 1
                continue
            fkey = f"{file_key(rel)}-p{page + 1}.jpg"
            out_path = os.path.join(FIG_DIR, fkey)
            if not os.path.exists(out_path):
                render_page(path, page, out_path)
                stats["pages_rendered"] += 1
            cur.execute("UPDATE questions SET figure = ? WHERE id = ?", (f"/figures/{fkey}", rid))
            stats["questions_linked"] += 1
        db.commit()
        done.add(key)
        ckpt["done"] = sorted(done)
        with open(CKPT, "w") as f:
            json.dump(ckpt, f)
        stats["files"] += 1
        print(f"  {os.path.basename(path)}: linked={sum(1 for p in page_cache.values() if p is not None)}", flush=True)

    print(f"[fig] done: {stats}", flush=True)
    db.close()


if __name__ == "__main__":
    main()
