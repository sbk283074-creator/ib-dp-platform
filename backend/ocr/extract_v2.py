"""extract_v2 — practice-question extractor (clean restart).

Pipeline per book:
  1. fast word extraction (pypdfium2 char boxes)  -> position-accurate, fast.
  2. heading detection  -> practice sections (Exercise / Review set / Practice
     questions / Test yourself / ...) and STOP headings (Example / Investigation /
     Activity / Summary / Chapter ...).
  3. question-number detection -> left-margin integers inside a practice section.
  4. band building -> one band per question (multi-page bands stitched).
  5. render + crop -> one image per question.

Only practice questions are emitted: anything above the first question of a
section, and anything after a STOP heading, is discarded.
"""
import os, re, sys, json, logging
logging.disable(logging.CRITICAL)

import pypdfium2 as pdfium
from PIL import Image

ROOT = "/Users/lucas.ma/Downloads/dp learning"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(HERE, "book_json2")
OUT_IMG = os.path.join(HERE, "..", "public", "figures", "book2")

# ---------------------------------------------------------------------------
def fast_words(page, gap_ratio=0.30):
    tp = page.get_textpage()
    n = tp.count_chars()
    ph = page.get_size()[1]
    chars = []
    for i in range(n):
        ch = tp.get_text_range(i, 1)
        if ch in ("", "\r", "\n"):
            continue
        l, b, r, t = tp.get_charbox(i)
        chars.append([l, ph - t, r, ph - b, ch, t - b])
    chars.sort(key=lambda c: (round(c[1] / 3), c[0]))
    words, cur = [], []
    def flush():
        if cur:
            txt = "".join(c[4] for c in cur).strip()
            if txt:
                words.append({"text": txt, "x0": min(c[0] for c in cur), "x1": max(c[2] for c in cur),
                              "top": min(c[1] for c in cur), "bottom": max(c[3] for c in cur),
                              "size": max(c[5] for c in cur)})
    prev = None
    for c in chars:
        if prev is not None:
            if abs(c[1] - prev[1]) > 3 or (c[0] - prev[2]) > gap_ratio * max(prev[5], 1):
                flush(); cur = []
        cur.append(c); prev = c
    flush()
    return words

def group_lines(words, tol=5.0):
    words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines, cur, cur_top = [], [], None
    for w in words:
        if cur_top is None or abs(w["top"] - cur_top) <= tol:
            cur.append(w); cur_top = w["top"] if cur_top is None else cur_top
        else:
            lines.append(cur); cur, cur_top = [w], w["top"]
    if cur:
        lines.append(cur)
    out = []
    for ws in lines:
        ws = sorted(ws, key=lambda w: w["x0"])
        out.append({"top": min(w["top"] for w in ws), "bottom": max(w["bottom"] for w in ws),
                    "x0": min(w["x0"] for w in ws), "x1": max(w["x1"] for w in ws),
                    "size": max(w["size"] for w in ws),
                    "text": " ".join(w["text"] for w in ws), "words": ws})
    return out

def estimate_body(words):
    sizes = sorted(w["size"] for w in words if w["size"] > 0)
    if not sizes:
        return 0.0, 0.0
    body = sizes[len(sizes) // 2]
    xs = sorted(w["x0"] for w in words if abs(w["size"] - body) <= 1.5)
    left = xs[len(xs) // 10] if xs else (min(w["x0"] for w in words) if words else 0)
    return body, left

INT_RE = re.compile(r"^(\d{1,3})$")
NUMPFX_RE = re.compile(r"^(\d{1,3})[.)]$")

def is_qnum(w, body, left, cfg):
    m = INT_RE.match(w["text"]) or NUMPFX_RE.match(w["text"])
    if not m:
        return False
    n = int(m.group(1))
    if not (1 <= n <= cfg.get("qnum_max", 200)):
        return False
    if w["x0"] > left - cfg.get("qnum_left_gap", 12):
        return False
    lo = body * cfg.get("qnum_size_lo", 0.70)
    hi = body * cfg.get("qnum_size_hi", 1.7)
    if not (lo <= w["size"] <= hi):
        return False
    return True

# ---------------------------------------------------------------------------
# sections & bands
# ---------------------------------------------------------------------------
def build_sections(pages, cfg):
    prac = cfg["practice"]; stop = cfg["stop"]
    sections, cur, in_prac = [], None, False
    for pg in pages:
        if not pg["ws"]:
            continue
        body, left = pg["body"], pg["left"]
        if body <= 0:
            continue
        for ln in group_lines(pg["ws"]):
            if len(ln["text"]) > 80:
                continue
            if ln["size"] < body * cfg.get("head_ratio", 1.12):
                continue
            if ln["x0"] > left + 40:
                continue
            t = ln["text"].strip()
            if prac.search(t):
                if cur:
                    cur["end"] = (pg["idx"], ln["top"]); sections.append(cur)
                cur = {"name": t[:70], "start": (pg["idx"], ln["bottom"]), "end": None}
                in_prac = True
            elif stop.search(t):
                if cur:
                    cur["end"] = (pg["idx"], ln["top"]); sections.append(cur); cur = None
                in_prac = False
    if cur:
        last = pages[-1]
        cur["end"] = (last["idx"], last["ph"])
        sections.append(cur)
    return sections

def section_qnums(section, pages, cfg):
    (sp, stop_) = section["start"]
    ep, etop = section["end"] if section["end"] else (sp, 10 ** 9)
    found = []
    for pg in pages:
        i = pg["idx"]
        if i < sp or i > ep:
            continue
        for w in pg["ws"]:
            if not is_qnum(w, pg["body"], pg["left"], cfg):
                continue
            if i == sp and w["top"] < stop_ - 6:
                continue
            if i == ep and w["top"] > etop - 2:
                continue
            found.append({"page": i, "top": w["top"], "num": int(re.sub(r"\D", "", w["text"])),
                          "x0": w["x0"]})
    found.sort(key=lambda q: (q["page"], q["top"]))
    # keep a monotonically increasing run of numbers starting near 1
    clean, expect = [], None
    for q in found:
        if expect is None:
            if q["num"] > 3:
                continue
            expect = q["num"]
        if q["num"] == expect or q["num"] == expect + 1 or (q["num"] > expect and q["num"] <= expect + 3):
            clean.append(q); expect = q["num"]
    return clean

def crop_question(doc, pmap, q, nxt, section, cfg, scale, out_path):
    sp, st = q["page"], q["top"]
    if nxt is not None:
        ep, et = nxt["page"], nxt["top"]
    else:
        ep, et = section["end"] if section["end"] else (sp, pmap[sp]["ph"])
    x_left = max(0, pmap[sp]["x0"] - 12)
    x_right = min(pmap[sp]["pw"], pmap[sp]["x1"] + 12)
    tiles = []
    for i in range(sp, ep + 1):
        pg = pmap[i]
        top = st - 6 if i == sp else 0
        bot = (et - 4) if i == ep else pg["ph"]
        if bot - top < 4:
            continue
        bmp = doc[i].render(scale=scale)
        img = bmp.to_pil().convert("RGB")
        w, h = img.size
        sx = w / pg["pw"]; sy = h / pg["ph"]
        box = (int(x_left * sx), int(top * sy), int(x_right * sx), int(bot * sy))
        box = (max(0, box[0]), max(0, box[1]), min(w, box[2]), min(h, box[3]))
        if box[2] - box[0] < 8 or box[3] - box[1] < 8:
            continue
        tiles.append(img.crop(box))
    if not tiles:
        return None
    W = max(t.width for t in tiles)
    H = sum(t.height for t in tiles)
    canvas = Image.new("RGB", (W, H), "white")
    y = 0
    for t in tiles:
        canvas.paste(t, (0, y)); y += t.height
    canvas.save(out_path, quality=82, optimize=True)
    return (W, H)

# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------
def scan_pages(doc, lo=0, hi=None):
    hi = len(doc) if hi is None else min(hi, len(doc))
    pages = []
    for i in range(lo, hi):
        page = doc[i]
        ws = fast_words(page)
        body, left = estimate_body(ws)
        pw, ph = page.get_size()
        pages.append(dict(idx=i, ws=ws, body=body, left=left, pw=pw, ph=ph,
                          x0=min((w["x0"] for w in ws), default=0.0),
                          x1=max((w["x1"] for w in ws), default=pw)))
    return pages

def extract_book(cfg, lo=0, hi=None, scale=None, verbose=True):
    scale = scale or cfg.get("scale", 2.0)
    doc = pdfium.PdfDocument(cfg["path"])
    pages = scan_pages(doc, lo, hi)          # pg["idx"] = ABSOLUTE page index
    pmap = {pg["idx"]: pg for pg in pages}
    off = lo
    sections = build_sections(pages, cfg)
    outdir = os.path.join(OUT_IMG, cfg["id"])
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(OUT_JSON, exist_ok=True)
    questions = []
    for si, sec in enumerate(sections):
        qnums = section_qnums(sec, pages, cfg)
        if not qnums:
            continue
        for qi, q in enumerate(qnums):
            nxt = qnums[qi + 1] if qi + 1 < len(qnums) else None
            num = q["num"]
            fn = f"{cfg['id']}_q_{q['page'] + 1}_{num}.jpg"
            path = os.path.join(outdir, fn)
            size = crop_question(doc, pmap, q, nxt, sec, cfg, scale, path)
            if not size:
                continue
            questions.append(dict(
                id=f"{cfg['id']}-S{si+1}-Q{num}", subject=cfg["subject"], level=cfg.get("level", "HL"),
                topic="Exercises", subtopic=sec["name"], paper_type=None, command_term=None,
                marks=None, difficulty=None,
                question=f"[See question image. Source: {cfg['title']}, {sec['name']}.]",
                answer="__AI_FILL__", explanation="__AI_FILL__",
                source=f"{cfg['title']} - {sec['name']} Q{num}",
                tags=["book", cfg.get("tag", cfg["id"].lower())],
                book_id=cfg["id"], book_section=sec["name"],
                book_page=q["page"] + 1, in_book_order=len(questions) + 1,
                source_type="book", question_image=f"/figures/book2/{cfg['id']}/{fn}",
                figure_image=None, answer_image=None, authored_by="import", _ai_fill=True))
    book = dict(id=cfg["id"], subject=cfg["subject"], title=cfg["title"],
                publisher=cfg.get("publisher"), edition=cfg.get("edition"),
                has_answers=1 if cfg.get("has_answers") else 0,
                answer_source=cfg.get("answer_source"), cover_path=None,
                total_questions=len(questions))
    with open(os.path.join(OUT_JSON, cfg["id"] + ".json"), "w") as f:
        json.dump({"book": book, "questions": questions}, f, ensure_ascii=False)
    if verbose:
        print(f"{cfg['id']:16} sections={len(sections):3} questions={len(questions):4} "
              f"(pages {off+1}-{off+len(pages)})")
    return book, questions
