"""extract_v3 — practice-question extractor (production).

Design notes
------------
* Words come from pypdfium2 char boxes (fast, and independent of the often
  garbled subset fonts).  Many books insert stray spaces inside words
  ("E xerc i se 1D"), so heading regexes are matched against a space-stripped
  normalised string as well as the raw string.
* Question numbers are found structurally, NOT by trusting the text layer:
  a question number is the leftmost token of a line, an integer in range, with
  body text following it on the same line, and it sits on a *recurring left
  margin* of the page.  The recurring-margin test makes the detector work for
  single-column AND multi-column pages.
* Headings that wrap onto a second line are joined before matching.
* Running page headers/footers are excluded from the rendered crop.
"""
import os, re, sys, json, logging, shutil
logging.disable(logging.CRITICAL)

import pypdfium2 as pdfium
from PIL import Image

ROOT = "/Users/lucas.ma/Downloads/dp learning"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(HERE, "book_json2")
OUT_IMG = os.path.join(HERE, "..", "public", "figures", "book2")

HDR_BAND = 0.085   # top fraction treated as running-header zone
FTR_BAND = 0.915   # bottom fraction treated as running-footer zone

# ---------------------------------------------------------------------------
# words / lines
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


def norm(s):
    return re.sub(r"[\s\u00a0]+", "", s).lower()


KINDS = [
    (r"reviewset", "Review set"), (r"xercis", "Exercise"), (r"practicequestions", "Practice questions"),
    (r"testyourunderstanding", "Test your understanding"), (r"exam-stylequestions", "Exam-style questions"),
    (r"multiplechoice", "Multiple choice questions"), (r"mixedpractice", "Mixed practice"),
    (r"chapterreview", "Chapter review"), (r"data-?basedquestions", "Data-based questions"),
    (r"end-of-topicquestions", "End-of-topic questions"), (r"linkingquestions", "Linking questions"),
    (r"topicreview", "Topic review"), (r"guidingquestions", "Guiding questions"),
    (r"mixedquestionsset", "Mixed questions set"), (r"skillbuilder", "Skill builder questions"),
    (r"practice", "Practice"), (r"xerc", "Exercise"),
]


TOPICS = [
    ("numberandalgebra", "Number and algebra"),
    ("geometryandtrigonometry", "Geometry and trigonometry"),
    ("statisticsandprobability", "Statistics and probability"),
    ("syllabusrevision", "Syllabus revision"),
    ("functions", "Functions"),
    ("calculus", "Calculus"),
]


def degarble(raw):
    """re-join a shattered running head.

    Some PDFs letterspace running heads into single characters, so a page
    header arrives as '84 S y ll a b us rev i s i on'.  When a heading is
    mostly 1-2 character tokens, glue it back together and drop the page
    number so it can be matched against the known topic names.
    """
    toks = raw.split()
    core = [re.sub(r"[^A-Za-z0-9]", "", x) for x in toks]
    if len(core) < 3:
        return raw
    short = sum(1 for c in core if 0 < len(c) <= 2)
    if short / len(core) < 0.45:
        return raw
    joined = "".join(core)
    joined = re.sub(r"^\d{1,3}", "", joined)
    joined = re.sub(r"\d{1,3}$", "", joined)
    return joined


def clean_name(raw):
    """turn a garbled heading ('E Dxerc i se 1') into a readable section name."""
    n = norm(raw)
    kind = None
    for pat, label in KINDS:
        if re.search(pat, n):
            kind = label
            break
    if not kind:
        d = degarble(raw)
        if d is not raw:
            dn = norm(d)
            for pat, label in TOPICS:
                if pat in dn:
                    return label
    ident = re.search(r"\d{1,2}(?:\.\d{1,2})?[A-Z]?", raw)
    if kind:
        return f"{kind} {ident.group(0)}" if ident else kind
    m = re.match(r"^(\d{1,2}[A-Z])\b", raw)
    if m:
        return f"Section {m.group(1)}"
    return re.sub(r"\s+", " ", raw).strip()[:70]


def _rx(v):
    return v if hasattr(v, "search") else re.compile(v)


# --- heading quality gates --------------------------------------------------
# A heading candidate must carry its section label near the START of the text.
# Body prose that merely mentions an exercise ("such as those in Exercise 4K")
# is oversized text the size test picks up, and it used to create phantom
# sections named after the mention.  The window is generous because several
# PDFs letterspace headings so badly that the label only appears ~11 characters
# in ("E i 1 1 Di l t di t xerc se sp acemen s ance" -> "ei11diltditxercse...").
LABEL_POS_MAX = 16

# end-matter headings: answers / index / glossary are never practice content
BACK_MATTER = re.compile(
    r"^(index|glossary|bibliography|appendix|acknowledge?ments?|references|"
    r"notation|photo ?credits|credits|list of (formulae|symbols)|"
    r"answers?( to)?( exercises)?)$", re.I)

# section names that carry no usable identifier ('Exercise', 'Exercise 0',
# 'Review set 0'): the boundary is still real, so keep it but rename it
DEGENERATE = re.compile(r"^(exercise|exercises|review set)\s*(0(\.\d+)?)?$", re.I)


def _back_matter_start(pages, cfg):
    """first page of the real end-matter block (answers / index / glossary).

    The end-matter block is identified by its *running header*: 'ANSWERS' or
    'INDEX' is printed on nearly every page of it.  A lone 'Answers' heading
    mid-book, or an answers section whose pages still carry normal chapter
    headers, will not pass the density test and so will not truncate the book.
    """
    if not pages:
        return None
    maxp = max(pg["idx"] for pg in pages)
    bm = []
    for pg in pages:
        if not pg["ws"] or pg["body"] <= 0:
            continue
        for top, bot, raw in _headings(pg["lines"], pg["body"], cfg):
            if BACK_MATTER.match(norm(raw).strip()):
                bm.append(pg["idx"])
                break
    for p in bm:
        if p < maxp * 0.8:
            continue
        tail = [q for q in bm if q >= p]
        span = maxp - p + 1
        # end-matter header on at least a quarter of the remaining pages
        if len(tail) >= 3 and len(tail) >= span * 0.25:
            return p
    return None


# ---------------------------------------------------------------------------
# question-number detection (layout agnostic)
# ---------------------------------------------------------------------------
INT_RE = re.compile(r"^(\d{1,3})$")
NUMPFX_RE = re.compile(r"^(\d{1,3})[.)]$")


def is_qnum(w, line, margins, body, cfg):
    m = INT_RE.match(w["text"]) or NUMPFX_RE.match(w["text"])
    if not m:
        return False
    n = int(m.group(1))
    if not (cfg.get("qnum_min", 1) <= n <= cfg.get("qnum_max", 200)):
        return False
    if w["size"] < body * cfg.get("qnum_size_lo", 0.70):
        return False
    if w["size"] > body * cfg.get("qnum_size_hi", 1.9):
        return False
    # must be the leftmost token of its line
    if w["x0"] - line["x0"] > 3:
        return False
    # there must be real text after the number on the same line
    rest = line["text"].strip()[len(w["text"]):].strip()
    if len(rest) < cfg.get("qnum_min_rest", 6):
        return False
    # must sit on a recurring left margin (works for 1- and 2-column pages)
    gap = cfg.get("qnum_left_gap", 12)
    cnt = sum(1 for mx in margins if abs(mx - w["x0"]) <= max(gap, 8))
    if cnt < cfg.get("margin_min", 2):
        return False
    return True


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------
def _headings(lines, body, cfg):
    """yield (top, bottom, raw_text) for heading candidates, joining wrapped lines."""
    ratio = cfg.get("head_ratio", 1.10)
    big = [ln for ln in lines if ln["size"] >= body * ratio and len(ln["text"]) < 95]
    i = 0
    while i < len(big):
        ln = big[i]
        txt = ln["text"]
        top, bot = ln["top"], ln["bottom"]
        # join a wrapped continuation line (same size, immediately below, starts left)
        if i + 1 < len(big):
            nxt = big[i + 1]
            if (abs(nxt["top"] - ln["bottom"]) < ln["size"] * 2.0
                    and abs(nxt["x0"] - ln["x0"]) < 30
                    and len(nxt["text"]) < 60):
                txt = txt + " " + nxt["text"]
                bot = nxt["bottom"]
                i += 1
        yield top, bot, re.sub(r"\s+", " ", txt).strip()
        i += 1


def build_sections(pages, cfg):
    prac = _rx(cfg["practice"]); stop = _rx(cfg["stop"])
    sections, cur = [], None
    back_from = _back_matter_start(pages, cfg)
    for pg in pages:
        if not pg["ws"] or pg["body"] <= 0:
            continue
        if back_from is not None and pg["idx"] >= back_from:
            # Close the open section *at* the cutoff so section_qnums cannot
            # scan forward into the answers/index pages.
            if cur:
                cur["end"] = (back_from, 0.0); sections.append(cur); cur = None
            break
        body = pg["body"]; left = pg["left"]
        for top, bot, raw in _headings(pg["lines"], body, cfg):
            if raw:
                x0 = next((ln["x0"] for ln in pg["lines"] if ln["top"] == top), left)
                if x0 > left + cfg.get("head_indent", 45):
                    continue
            t = norm(raw)
            m = prac.search(t) or prac.search(raw)
            hit_s = stop.search(t) or stop.search(raw)
            if m:
                # A practice-looking heading always starts a new section: the
                # question numbering restarts there, and section_qnums relies on
                # that reset (merging two runs makes the monotonic filter throw
                # the second run away).  Only the *name* is cosmetic, so a
                # heading that is really body prose gets a neutral name instead
                # of being dropped.
                if m.start() <= LABEL_POS_MAX:
                    nm = clean_name(raw)
                else:
                    nm = ""
                if not nm or DEGENERATE.match(nm):
                    nm = f"Practice (p.{pg['idx'] + 1})"
                if cur and cur["name"] == nm:
                    continue                      # running head repeating — stay in section
                if cur:
                    cur["end"] = (pg["idx"], top); sections.append(cur)
                cur = {"name": nm, "start": (pg["idx"], bot), "end": None}
            elif hit_s:
                if cur:
                    cur["end"] = (pg["idx"], top); sections.append(cur); cur = None
    if cur:
        last = pages[-1]
        cur["end"] = (last["idx"], last["cbot"])
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
        for ln in pg["lines"]:
            if not ln["words"]:
                continue
            w = ln["words"][0]
            if not is_qnum(w, ln, pg["margins"], pg["body"], cfg):
                continue
            if i == sp and w["top"] < stop_ - 6:
                continue
            if i == ep and w["top"] > etop - 2:
                continue
            found.append({"page": i, "top": w["top"], "num": int(re.sub(r"\D", "", w["text"])),
                          "x0": w["x0"]})
    if not found:
        return []
    # Reading order for multi-column pages: page -> column (left to right) -> top.
    # Without this, right-column numbers interleave with the left column and get
    # discarded by the monotonic filter below.
    gap = cfg.get("col_gap", 60)
    ordered = []
    bypage = {}
    for q in found:
        bypage.setdefault(q["page"], []).append(q)
    for pi in sorted(bypage):
        items = sorted(bypage[pi], key=lambda q: q["x0"])
        cols = [[items[0]]]
        for it in items[1:]:
            if it["x0"] - cols[-1][-1]["x0"] > gap:
                cols.append([it])
            else:
                cols[-1].append(it)
        lefts = [min(x["x0"] for x in c) for c in cols]
        for ci, c in enumerate(cols):
            for q in sorted(c, key=lambda q: q["top"]):
                q["col_left"] = lefts[ci]
                q["col_right"] = (lefts[ci + 1] - 8) if ci + 1 < len(lefts) else None
                ordered.append(q)
    # keep a monotonically increasing run of numbers starting near 1
    clean, expect = [], None
    for q in ordered:
        if expect is None:
            if q["num"] > cfg.get("first_max", 3):
                continue
            expect = q["num"]
        if q["num"] == expect or (expect < q["num"] <= expect + 3):
            clean.append(q); expect = q["num"]
    return clean


# ---------------------------------------------------------------------------
# render / crop
# ---------------------------------------------------------------------------
def _col_bottom(pg, x_lo, x_hi):
    """bottom of the lowest text inside a column's x-range on this page."""
    b = 0.0
    for ln in pg["lines"]:
        if ln["x0"] >= x_lo - 20 and ln["x0"] <= x_hi + 20:
            b = max(b, ln["bottom"])
    return b or pg["cbot"]


def band_xrange(pg, top, bot, x_hint):
    """x-range of the contiguous content block (column) containing x_hint,
    measured only over the vertical band [top, bot]."""
    ws = [w for w in pg["ws"] if top - 6 <= w["top"] <= bot + 6]
    if not ws:
        return pg["x0"], pg["x1"]
    step = 5.0
    n = int(pg["pw"] / step) + 1
    cov = [False] * n
    for w in ws:
        a = int(max(0.0, w["x0"]) / step)
        b = int(min(pg["pw"], w["x1"]) / step)
        for k in range(a, min(b + 1, n)):
            cov[k] = True
    segs, k = [], 0
    while k < n:
        if cov[k]:
            j = k
            while j < n and cov[j]:
                j += 1
            segs.append([k * step, j * step]); k = j
        else:
            k += 1
    # merge runs separated by small gaps (e.g. the space after a question number)
    merged = []
    for a, b in segs:
        if merged and a - merged[-1][1] < 22:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    best = None
    for a, b in merged:
        if a - 18 <= x_hint <= b + 18:
            if best is None or (b - a) < (best[1] - best[0]):
                best = (a, b)
    return best or (pg["x0"], pg["x1"])


def crop_question(doc, pmap, q, nxt, section, cfg, scale, out_path):
    sp, st = q["page"], q["top"]
    pg0 = pmap[sp]
    col_left = max(0.0, pg0["x0"] - 14)
    col_right = min(pg0["pw"], pg0["x1"] + 14)
    if nxt is not None:
        ep, et = nxt["page"], nxt["top"]
        # A real question occupies at least ~3 lines. If the band is much shorter
        # than that the next "number" is usually a false positive inside the
        # question, so give the band room instead of cutting the question off.
        min_band = cfg.get("min_band", 58)
        if ep == sp and (et - st) < min_band:
            et = min(st + min_band, pg0["cbot"])
    else:
        ep, et = sp, pg0["cbot"]

    tiles = []
    # A question band must never span an unbounded number of pages, otherwise a
    # sparse section produces an enormous stitched image (PIL caps at 65500 px).
    max_pages = cfg.get("max_band_pages", 4)
    max_h = cfg.get("max_band_px", 30000)
    for i in range(sp, min(ep, sp + max_pages - 1) + 1):
        pg = pmap[i]
        top = max(st - 8, pg["ctop"]) if i == sp else pg["ctop"]
        if i == ep:
            bot = min(et - 5, pg["cbot"])
        else:
            bot = pg["cbot"]
        if bot - top < 4:
            continue
        img = doc[i].render(scale=scale).to_pil().convert("RGB")
        w, h = img.size
        sx = w / pg["pw"]; sy = h / pg["ph"]
        box = (int(col_left * sx), int(top * sy), int(col_right * sx), int(bot * sy))
        box = (max(0, box[0]), max(0, box[1]), min(w, box[2]), min(h, box[3]))
        if box[2] - box[0] < 8 or box[3] - box[1] < 8:
            continue
        if sum(t.height for t in tiles) + (box[3] - box[1]) > max_h:
            break                              # stop before the image gets absurd
        tiles.append(img.crop(box))
    if not tiles:
        return None
    W = max(t.width for t in tiles)
    H = sum(t.height for t in tiles)
    if W < 80 or H < 26:          # sliver — not a usable question crop
        return None
    canvas = Image.new("RGB", (W, H), "white")
    y = 0
    for t in tiles:
        canvas.paste(t, (0, y)); y += t.height
    try:
        canvas.save(out_path, quality=82, optimize=True)
    except Exception:
        return None                            # never let one crop kill the run
    finally:
        canvas.close()
    return (W, H)


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------
def page_columns(lines, pw):
    """Split a page into columns by finding vertical gutters (whitespace bands)."""
    if not lines:
        return [(0.0, pw)]
    step = 5.0
    n = int(pw / step) + 1
    cov = [False] * n
    for ln in lines:
        a = int(max(0.0, ln["x0"]) / step)
        b = int(min(pw, ln["x1"]) / step)
        for k in range(a, min(b + 1, n)):
            cov[k] = True
    cols, start, k = [], 0, 0
    while k < n:
        if not cov[k]:
            j = k
            while j < n and not cov[j]:
                j += 1
            if (j - k) * step >= 25 and k > 2 and j < n - 2:
                cols.append((start * step, k * step)); start = j
            k = j
        else:
            k += 1
    cols.append((start * step, pw))
    # drop empty columns and clamp to real content
    lo = min(ln["x0"] for ln in lines); hi = max(ln["x1"] for ln in lines)
    out = [(max(a, 0.0), min(b, pw)) for a, b in cols if b - a > 40]
    return out or [(max(0.0, lo), min(pw, hi))]


def col_of(pg, x):
    """the (x_lo, x_hi) column of this page that contains x."""
    for a, b in pg.get("cols") or []:
        if a - 20 <= x <= b + 20:
            return a, b
    return None, None


def scan_pages(doc, lo=0, hi=None):
    hi = len(doc) if hi is None else min(hi, len(doc))
    pages = []
    for i in range(lo, hi):
        page = doc[i]
        ws = fast_words(page)
        body, left = estimate_body(ws)
        pw, ph = page.get_size()
        lines = group_lines(ws) if ws else []
        ctop, cbot = 0.0, ph
        if lines:
            if lines[0]["top"] < ph * HDR_BAND and lines[0]["size"] <= body * 1.02:
                ctop = lines[0]["bottom"]
            if lines[-1]["top"] > ph * FTR_BAND and lines[-1]["size"] <= body * 1.02:
                cbot = lines[-1]["top"]
        # recurring left margins (every line's start) for the qnum test
        margins = [ln["x0"] for ln in lines]
        pages.append(dict(idx=i, ws=ws, lines=lines, margins=margins, body=body, left=left,
                          pw=pw, ph=ph, ctop=ctop, cbot=cbot,
                          cols=page_columns(lines, pw),
                          x0=min((w["x0"] for w in ws), default=0.0),
                          x1=max((w["x1"] for w in ws), default=pw)))
    return pages


def extract_book(cfg, lo=0, hi=None, scale=None, verbose=True):
    scale = scale or cfg.get("scale", 1.8)
    doc = pdfium.PdfDocument(cfg["path"])
    lo = cfg.get("start_page", lo)
    pages = scan_pages(doc, lo, hi)          # pg["idx"] = ABSOLUTE page index
    pmap = {pg["idx"]: pg for pg in pages}
    sections = build_sections(pages, cfg)
    outdir = os.path.join(OUT_IMG, cfg["id"])
    # NOTE: crops are ordinal-named, so a re-extraction rewrites every file for
    # this book.  The caller must clear the folder first (_rerun_all.sh does);
    # an in-process rmtree is blocked by the bulk-delete guard.
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(OUT_JSON, exist_ok=True)
    min_q = cfg.get("min_sec_qs", 3)
    questions, kept = [], 0
    for si, sec in enumerate(sections):
        qnums = section_qnums(sec, pages, cfg)
        if len(qnums) < min_q:
            continue
        kept += 1
        for qi, q in enumerate(qnums):
            nxt = qnums[qi + 1] if qi + 1 < len(qnums) else None
            num = q["num"]
            # The detected question number (`num`) is NOT unique: the monotonic
            # filter lets a stuck number repeat ("11, 11, 11, 11, 11" across five
            # different pages), so keying ids or filenames on it silently
            # overwrote rows on import and crops on disk.  A per-book running
            # ordinal is unique, dense and stable.
            ordn = len(questions) + 1
            fn = f"{cfg['id']}_q{ordn:04d}.jpg"
            if not crop_question(doc, pmap, q, nxt, sec, cfg, scale, os.path.join(outdir, fn)):
                continue
            questions.append(dict(
                id=f"{cfg['id']}-Q{ordn:04d}", subject=cfg["subject"], level=cfg.get("level", "HL"),
                topic=cfg.get("topic", "Exercises"), subtopic=sec["name"], paper_type=None,
                command_term=None, marks=None, difficulty=None,
                question=f"[See question image. Source: {cfg['title']}, {sec['name']}.]",
                answer="__AI_FILL__", explanation="__AI_FILL__",
                source=f"{cfg['title']} - {sec['name']} #{ordn} (p.{q['page'] + 1})",
                tags=["book", cfg.get("tag", cfg["id"].lower())],
                book_id=cfg["id"], book_section=sec["name"],
                book_page=q["page"] + 1, in_book_order=ordn,
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
        print(f"{cfg['id']:18} sections={kept:3} questions={len(questions):5} "
              f"pages={lo+1}-{lo+len(pages)}", flush=True)
    return book, questions
    return book, questions
