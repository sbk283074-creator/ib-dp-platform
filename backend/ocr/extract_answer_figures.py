#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Second figure pass: render the MARKSCHEME page containing each question's ANSWER
and store it in the `answer_figure` column (answers often contain diagrams,
trace tables, trees…).

Raw: answer lives in the markscheme pdf (mspath from walkers).
Classified: answer lives in the same markscheme-HL-paperN.pdf we parsed.

Resumable via answer_figures_checkpoint.json. Run after format_texts.js.
"""
import json, os, re, sqlite3, sys
import pdfplumber

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_figures as F   # reuses norm/clean_qtext/find_page_by_windows_pdf/render_page/...

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = F.DB_PATH
IMPORT_JSON = F.IMPORT_JSON
CKPT = os.path.join(HERE, "answer_figures_checkpoint.json")


def build_ms_maps():
    """-> (raw_phys{(label,tz): {paper_norm: mspath}}, raw_math{...}, cls{(folder,pnum): mspath})"""
    raw_phys, raw_math = {}, {}
    for label, disp, paper, tz, qp, msp in F.X.phy_raw_walker():
        if msp:
            raw_phys.setdefault((label, tz), {})[paper.lower().replace(" ", "")] = msp
    for label, disp, paper, tz, path, is_ms, opt in F.X.math_raw_walker():
        if is_ms:
            raw_math.setdefault((label, tz), {})[paper.lower().replace(" ", "")] = path
    return raw_phys, raw_math


def resolve_answer(rec, raw_phys, raw_math):
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
        pool = raw_phys if rid.startswith("PHY-RAW-") else raw_math
        path = pool.get((label, tz), {}).get(paper_norm)
        return (path, f"A|{label}|{tz or ''}|{paper_norm}") if path else None
    m = re.match(r"(PHY|MATH)-CLS-(.+)-P(\d+)-(\d+)$", rid)
    if not m:
        return None
    subj, folder, pnum = m.group(1), m.group(2), m.group(3)
    base = F.X.PHY_CLS if subj == "PHY" else F.X.MATH_CLS
    fm = re.match(r"Topic(\d+)", folder)
    if fm:
        folder = f"Topic {int(fm.group(1))}"
    om = re.match(r"Option([A-D])", folder)
    if om:
        folder = f"Option {om.group(1)}"
    ms = os.path.join(base, folder, f"markscheme-HL-paper{pnum}.pdf")
    if not os.path.exists(ms):
        return None
    return (ms, f"A|C|{subj}|{folder}|{pnum}")


def main():
    ckpt = {"done": []}
    if os.path.exists(CKPT):
        try:
            ckpt = json.load(open(CKPT))
        except Exception:
            pass
    done = set(ckpt["done"])

    records = json.load(open(IMPORT_JSON))
    raw_phys, raw_math = build_ms_maps()
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()

    groups = {}
    unmapped = 0
    for rec in records:
        r = resolve_answer(rec, raw_phys, raw_math)
        if not r:
            unmapped += 1
            continue
        path, key = r
        groups.setdefault(key, {"path": path, "recs": []})["recs"].append(rec)
    print(f"[ans-fig] groups={len(groups)} unmapped={unmapped}", flush=True)

    stats = {"files": 0, "pages_rendered": 0, "answers_linked": 0, "no_figure": 0, "not_found": 0}
    for key, g in sorted(groups.items()):
        if key in done:
            print(f"  [skip] {key}", flush=True)
            continue
        path = g["path"]
        rel = os.path.relpath(path, F.ROOT)
        with pdfplumber.open(path) as pdf:
            n_pages = len(pdf.pages)
            page_norms = [F.norm(pg.extract_text() or "") for pg in pdf.pages]
            page_cache = {}
            for rec in g["recs"]:
                page = F.find_page_by_windows_pdf(pdf, rec["answer"], page_norms)
                page_cache[rec["id"]] = page
            fig_flags = {}
            for rid, page in page_cache.items():
                if page is None or page >= n_pages:
                    continue
                if page not in fig_flags:
                    fig_flags[page] = F.page_has_figure(pdf.pages[page])
        for rid, page in page_cache.items():
            if page is None or page >= n_pages:
                stats["not_found"] += 1
                continue
            if not fig_flags.get(page):
                stats["no_figure"] += 1
                continue
            fkey = f"{F.file_key(rel)}-ans-p{page + 1}.jpg"
            out_path = os.path.join(F.FIG_DIR, fkey)
            if not os.path.exists(out_path):
                F.render_page(path, page, out_path)
                stats["pages_rendered"] += 1
            cur.execute("UPDATE questions SET answer_figure = ? WHERE id = ?", (f"/figures/{fkey}", rid))
            stats["answers_linked"] += 1
        db.commit()
        done.add(key)
        ckpt["done"] = sorted(done)
        with open(CKPT, "w") as f:
            json.dump(ckpt, f)
        stats["files"] += 1
        print(f"  {os.path.basename(path)}: linked={sum(1 for p in page_cache.values() if p is not None)}", flush=True)

    print(f"[ans-fig] done: {stats}", flush=True)
    db.close()


if __name__ == "__main__":
    main()
