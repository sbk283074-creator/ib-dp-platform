#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v2 figure pass: crop the figure REGION that belongs to EACH question/answer
(replaces the earlier full-page screenshots).

Per question record:
  - resolve source pdf (question pdf for `figure`, markscheme pdf for `answer_figure`)
  - find the page (question-number line for raw, text windows otherwise)
  - locate the question's text top on the page
  - detect vector figure clusters (drop page furniture, full-width rules,
    column separators and full-width table grids)
  - crop the cluster(s) overlapping this question's vertical band, render JPEG,
    write `figure` / `answer_figure`

Questions whose page/band has no figure get NO image.
Resumable via crop_figures_checkpoint.json.
"""
import json, os, re, sqlite3, sys
import pdfplumber
import pypdfium2 as pdfium

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_figures as F
from extract_answer_figures import resolve_answer

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = F.DB_PATH
IMPORT_JSON = F.IMPORT_JSON
CKPT = os.path.join(HERE, "crop_figures_checkpoint.json")
PAD = 8          # padding around a cropped figure
CLUSTER_PAD = 25  # proximity used to merge vector elements
MIN_W, MIN_H = 40, 30


def figure_clusters(page):
    W, H = page.width, page.height
    els = []
    for objs in (page.lines, page.rects, page.curves, page.images):
        for o in objs:
            x0, y0, x1, y1 = o["x0"], o["top"], o["x1"], o["bottom"]
            w, h = x1 - x0, y1 - y0
            if w <= 2 and h <= 2:
                continue
            if w > 0.7 * W and h < 6:
                continue                       # full-width rules / answer lines
            if w < 4 and h > 0.5 * H:
                continue                       # table column separators
            if y0 < 40 or y1 > H - 40:
                continue                       # headers / footers
            els.append((x0, y0, x1, y1))
    def inter(a, b):
        return not (a[2] + CLUSTER_PAD < b[0] or b[2] + CLUSTER_PAD < a[0]
                    or a[3] + CLUSTER_PAD < b[1] or b[3] + CLUSTER_PAD < a[1])
    clusters = []
    for e in els:
        hit = next((c for c in clusters if any(inter(e, x) for x in c)), None)
        if hit is not None:
            hit.append(e)
        else:
            clusters.append([e])
    merged = True
    while merged:
        merged = False
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                if any(inter(a, b) for a in clusters[i] for b in clusters[j]):
                    clusters[i].extend(clusters[j])
                    clusters.pop(j)
                    merged = True
                    break
            if merged:
                break
    out = []
    for c in clusters:
        x0 = min(e[0] for e in c); y0 = min(e[1] for e in c)
        x1 = max(e[2] for e in c); y1 = max(e[3] for e in c)
        w, h = x1 - x0, y1 - y0
        if w >= MIN_W and h >= MIN_H and w <= 0.7 * W and h <= 0.85 * H:
            out.append((x0, y0, x1, y1))
    return out


def qnum_top(words, qnum):
    for w in words:
        t = (w.get("text") or "").strip()
        if re.fullmatch(rf"{qnum}\.", t):
            return w["top"]
    return None


def first_word_top(words, text):
    """Find the y-top of the first distinctive word of the (cleaned) text on this page."""
    cleaned = F.clean_qtext(text)
    m = re.search(r"[A-Za-z]{4,}", cleaned)
    if not m:
        return None
    word = m.group(0).lower()
    for w in words:
        if (w.get("text") or "").strip().lower() == word:
            return w["top"]
    for w in words:
        if (w.get("text") or "").strip().lower().startswith(word[:5]):
            return w["top"]
    return None


def render_crop(path, page_idx, bbox, out_path, scale=2.0):
    pdf = pdfium.PdfDocument(path)
    try:
        page = pdf[page_idx]
        W, H = page.get_size()
        x0 = max(0, bbox[0] - PAD); y0 = max(0, bbox[1] - PAD)
        x1 = min(W, bbox[2] + PAD); y1 = min(H, bbox[3] + PAD)
        pil = page.render(scale=scale).to_pil()
        pil.crop((int(x0 * scale), int(y0 * scale), int(x1 * scale), int(y1 * scale))) \
           .convert("RGB").save(out_path, quality=88)
    finally:
        pdf.close()


def main():
    ckpt = {"done": []}
    if os.path.exists(CKPT):
        try:
            ckpt = json.load(open(CKPT))
        except Exception:
            pass
    done = set(ckpt["done"])

    records = json.load(open(IMPORT_JSON))
    raw_phys = F.build_raw_map(F.X.phy_raw_walker, True)
    raw_math = F.build_raw_map(F.X.math_raw_walker, False)
    ans_phys, ans_math = {}, {}
    for label, disp, paper, tz, qp, msp in F.X.phy_raw_walker():
        if msp:
            ans_phys.setdefault((label, tz), {})[paper.lower().replace(" ", "")] = msp
    for label, disp, paper, tz, path, is_ms, opt in F.X.math_raw_walker():
        if is_ms:
            ans_math.setdefault((label, tz), {})[paper.lower().replace(" ", "")] = path

    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()

    # ---- build groups: (kind, source-path) -> records with (qnum, tpref)
    groups = {}
    unmapped = 0
    for rec in records:
        rid = rec["id"]
        # question figure source
        r = F.resolve(rec, raw_phys, raw_math)
        if r:
            path, key, qnum, tpref = r
            groups.setdefault(("Q", path), {"path": path, "recs": []})["recs"].append((rec, qnum, tpref))
        # answer figure source
        r2 = resolve_answer(rec, ans_phys, ans_math)
        if r2:
            path2, _k2 = r2
            groups.setdefault(("A", path2), {"path": path2, "recs": []})["recs"].append((rec, None, rec["answer"]))
    print(f"[crop] groups={len(groups)} unmapped={unmapped}", flush=True)

    stats = {"files": 0, "crops_rendered": 0, "Q_linked": 0, "A_linked": 0,
             "Q_no_figure": 0, "A_no_figure": 0, "not_found": 0}

    for (kind, path), g in sorted(groups.items()):
        gkey = f"{kind}|{os.path.relpath(path, F.ROOT)}"
        if gkey in done:
            print(f"  [skip] {gkey[:70]}", flush=True)
            continue
        rel = os.path.relpath(path, F.ROOT)
        with pdfplumber.open(path) as pdf:
            n_pages = len(pdf.pages)
            page_norms = None
            if any(tpref for (_r, _q, tpref) in g["recs"]):
                page_norms = [F.norm(pg.extract_text() or "") for pg in pdf.pages]
            # map records -> page
            by_page = {}
            for rec, qnum, tpref in g["recs"]:
                page = None
                if qnum is not None:
                    page = F.find_page_by_qnum_pdf(pdf, qnum)
                if page is None and tpref:
                    page = F.find_page_by_windows_pdf(pdf, tpref, page_norms)
                if page is None or page >= n_pages:
                    stats["not_found"] += 1
                    continue
                by_page.setdefault(page, []).append((rec, qnum, tpref))
            for page_idx, page_recs in by_page.items():
                pg = pdf.pages[page_idx]
                words = pg.extract_words()
                H = pg.height
                clusters = figure_clusters(pg)
                if not clusters:
                    stats["Q_no_figure" if kind == "Q" else "A_no_figure"] += len(page_recs)
                    continue
                tops = []
                for rec, qnum, tpref in page_recs:
                    top = qnum_top(words, qnum) if qnum is not None else None
                    if top is None and tpref:
                        top = first_word_top(words, tpref)
                    tops.append(top)
                order = sorted(range(len(page_recs)),
                               key=lambda i: tops[i] if tops[i] is not None else 1e9)
                seq = 0
                for idx in order:
                    top = tops[idx]
                    rec = page_recs[idx][0]
                    if top is None:
                        stats["not_found"] += 1
                        continue
                    band_top = top - 6
                    band_bot = H - 30
                    for j in order:
                        if tops[j] is not None and tops[j] > top + 2:
                            band_bot = tops[j] - 6
                            break
                    cands = [c for c in clusters if c[3] >= band_top and c[1] <= band_bot]
                    if not cands:
                        stats["Q_no_figure" if kind == "Q" else "A_no_figure"] += 1
                        continue
                    # choose: largest overlap; union nearby clusters
                    cands.sort(key=lambda c: min(c[3], band_bot) - max(c[1], band_top), reverse=True)
                    chosen = cands[0]
                    for c in cands[1:]:
                        if abs(c[1] - chosen[3]) < 60 or abs(chosen[1] - c[3]) < 60:
                            chosen = (min(chosen[0], c[0]), min(chosen[1], c[1]),
                                      max(chosen[2], c[2]), max(chosen[3], c[3]))
                    seq += 1
                    fkey = f"{F.file_key(rel)}-{'ans' if kind == 'A' else ''}-p{page_idx + 1}-f{seq}.jpg"
                    out_path = os.path.join(F.FIG_DIR, fkey)
                    if not os.path.exists(out_path):
                        render_crop(path, page_idx, chosen, out_path)
                        stats["crops_rendered"] += 1
                    col = "answer_figure" if kind == "A" else "figure"
                    cur.execute(f"UPDATE questions SET {col} = ? WHERE id = ?", (f"/figures/{fkey}", rec["id"]))
                    stats["Q_linked" if kind == "Q" else "A_linked"] += 1
        db.commit()
        done.add(gkey)
        ckpt["done"] = sorted(done)
        with open(CKPT, "w") as f:
            json.dump(ckpt, f)
        stats["files"] += 1
        print(f"  [{kind}] {os.path.basename(path)[:55]}: {len(g['recs'])} recs", flush=True)

    print(f"[crop] done: {stats}", flush=True)
    db.close()


if __name__ == "__main__":
    main()
