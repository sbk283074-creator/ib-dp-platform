#!/usr/bin/env python3
"""Render question/answer block screenshots for the Math AA question-bank scan.

Re-detects code positions in the PDF (same logic as extract_math_aa_qb.py), renders
each question block and each mark-scheme block to JPGs under
backend/public/figures/MathAA_QB/<safe>/, and writes a sidecar JSON mapping
code -> {question_image, answer_image} (comma-separated relative paths).
The Node updater then patches the DB rows.
"""
import os, re, sys, json, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pypdfium2 as pdfium

PDF = os.environ.get("PT_PDF", os.path.join(ROOT, "..", "..", "Math AA questions.pdf"))
MANIFEST = os.environ.get("PT_MANIFEST", "/tmp/math_aa_qb_dryrun.json")
FIG_ROOT = os.path.join(ROOT, "public", "figures", "MathAA_QB")
SIDECAR = os.environ.get("PT_SIDECAR", "/tmp/math_aa_qb_images.json")
SCALE = float(os.environ.get("PT_SCALE", "1.3"))

CODE_RE = re.compile(r"^([A-Za-z0-9]{2,6})\.(\d{1,2})\.(SL|AHL|HL)\.TZ(\d)\.([A-Za-z0-9_]+)\s*$", re.M)
HEADER_RE = re.compile(r"QuestionBank Test[^\n]*\n|https?://[^\n]*\n|Page \d+ of \d+[^\n]*\n")
FOOTER_RE = re.compile(r"\n?Page \d+ of \d+\s*$")


def main():
    os.makedirs(FIG_ROOT, exist_ok=True)
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    records = manifest["records"]

    pdf = pdfium.PdfDocument(PDF)
    N = len(pdf)
    pages_text = []
    occ = []
    for i in range(N):
        t = pdf[i].get_textpage().get_text_range()
        t = HEADER_RE.sub("", t)
        t = FOOTER_RE.sub("", t)
        pages_text.append(t)
        for m in CODE_RE.finditer(t):
            occ.append({"page": i, "pos": m.start(), "code": m.group(0).strip()})
    occ.sort(key=lambda o: (o["page"], o["pos"]))

    seen = {}
    for o in occ:
        c = o["code"]
        if c not in seen:
            seen[c] = {"q": o, "ms": None}
        else:
            seen[c]["ms"] = o
    q_occ = sorted([seen[c]["q"] for c in seen], key=lambda o: (o["page"], o["pos"]))
    ms_occ = sorted([seen[c]["ms"] for c in seen if seen[c]["ms"]], key=lambda o: (o["page"], o["pos"]))
    ms_header_page = ms_occ[0]["page"] if ms_occ else N

    def q_pages(q):
        qi = q_occ.index(q)
        nxt = q_occ[qi + 1] if qi + 1 < len(q_occ) else None
        end = nxt["page"] if (nxt and nxt["page"] < ms_header_page) else ms_header_page
        return list(range(q["page"], max(q["page"] + 1, end)))

    def ms_pages(ms):
        mi = ms_occ.index(ms)
        nxt = ms_occ[mi + 1] if mi + 1 < len(ms_occ) else None
        end = nxt["page"] if nxt else N
        return list(range(ms["page"], max(ms["page"] + 1, end)))

    def render_block(pages, out_dir, prefix):
        paths = []
        for k, p in enumerate(pages):
            bmp = pdf[p].render(scale=SCALE)
            img = bmp.to_pil().convert("RGB")
            fn = f"{prefix}_{k}.jpg"
            img.save(os.path.join(out_dir, fn), "JPEG", quality=82)
            paths.append(fn)
        return paths

    sidecar = {}
    t0 = time.time()
    done = 0
    for r in records:
        code = r["code"]
        safe = re.sub(r"[^A-Za-z0-9]", "_", code)
        out_dir = os.path.join(FIG_ROOT, safe)
        os.makedirs(out_dir, exist_ok=True)
        q = seen.get(code, {}).get("q")
        ms = seen.get(code, {}).get("ms")
        q_paths = render_block(q_pages(q), out_dir, "q") if (q and r.get("question", "").strip()) else []
        a_paths = render_block(ms_pages(ms), out_dir, "a") if (ms and r.get("answer", "").strip()) else []
        rel = lambda fns: ",".join(f"MathAA_QB/{safe}/{f}" for f in fns) if fns else ""
        sidecar[code] = {"question_image": rel(q_paths), "answer_image": rel(a_paths)}
        done += 1
        if done % 100 == 0:
            print(f"  rendered {done}/{len(records)} ({time.time()-t0:.1f}s)")

    with open(SIDECAR, "w", encoding="utf-8") as f:
        json.dump(sidecar, f)
    print(f"done {done} records in {time.time()-t0:.1f}s; sidecar -> {SIDECAR}")


if __name__ == "__main__":
    main()
