"""extract_specimen — import the official IB *specimen* ("mock") papers.

Two source PDFs, both with clean text layers:

  * Computer Science  Specimen papers 1, 2 and 3 — first examinations 2014  (141 pp)
  * Physics           Specimen papers 1A, 1B and 2 — first examinations 2025 (158 pp)

For every question we emit the same shape the rest of the bank uses:
question text, marks, answer (from the official markscheme), plus a rendered
crop of the question band so diagrams/tables survive.

Rows are written with category='mock' so the UI can filter them on their own.
"""
import os, re, sys, json, logging
logging.disable(logging.CRITICAL)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pypdfium2 as pdfium
from PIL import Image
import extract_v3 as E

DL = "/Users/lucas.ma/Downloads"
CS_PDF = os.path.join(DL, "IB DP Preparation/Computer Science 计算机",
                      "Computer Science-HLSL-Specimen Papers#样卷",
                      "Specimen Papers 2014 - English.pdf")
PH_PDF = os.path.join(DL, "dp learning", "Physics-HLSL-Specimen Papers(First exam 2025)",
                      "Specimen Papers 2025 - English.pdf")

OUT_JSON = os.path.join(HERE, "specimen_json")
OUT_IMG = os.path.join(HERE, "..", "public", "figures", "specimen")

SCALE = 2.0

# page ranges are 0-based, end-exclusive
PAPERS = [
    # ---- Computer Science, specimen 2014 (HL) ----
    dict(id="SPEC2014-CS-HL-P1", pdf=CS_PDF, subject="Computer Science", level="HL",
         paper_type="Paper 1", q=(3, 11), ms=(11, 28), markscheme="text",
         source="Specimen 2014 · CS HL Paper 1", title="CS HL Specimen Paper 1 (2014)"),
    dict(id="SPEC2014-CS-HL-P2", pdf=CS_PDF, subject="Computer Science", level="HL",
         paper_type="Paper 2", q=(28, 46), ms=(46, 74), markscheme="text",
         source="Specimen 2014 · CS HL Paper 2", title="CS HL Specimen Paper 2 (2014)"),
    dict(id="SPEC2014-CS-HL-P3", pdf=CS_PDF, subject="Computer Science", level="HL",
         paper_type="Paper 3", q=(74, 78), ms=(78, 84), markscheme="text",
         source="Specimen 2014 · CS HL Paper 3", title="CS HL Specimen Paper 3 (2014)"),
    # ---- Physics, specimen 2025 (HL) ----
    dict(id="SPEC2025-PHY-HL-P1A", pdf=PH_PDF, subject="Physics", level="HL",
         paper_type="Paper 1", q=(3, 25), ms=(25, 29), markscheme="key",
         source="Specimen 2025 · Physics HL Paper 1A", title="Physics HL Specimen Paper 1A (2025)"),
    dict(id="SPEC2025-PHY-HL-P1B", pdf=PH_PDF, subject="Physics", level="HL",
         paper_type="Paper 1", q=(29, 39), ms=(39, 45), markscheme="text",
         source="Specimen 2025 · Physics HL Paper 1B", title="Physics HL Specimen Paper 1B (2025)"),
    dict(id="SPEC2025-PHY-HL-P2", pdf=PH_PDF, subject="Physics", level="HL",
         paper_type="Paper 2", q=(45, 75), ms=(75, 93), markscheme="text",
         source="Specimen 2025 · Physics HL Paper 2", title="Physics HL Specimen Paper 2 (2025)"),
]

# --------------------------------------------------------------------------
# noise (running headers / footers / instructions) — never part of a question
# --------------------------------------------------------------------------
NOISE = [
    re.compile(r"^[–-]\s*\d+\s*[–-]"),          # "– 3 –" and "– 3 – 0000–6501"
    re.compile(r"SPEC/4/"),
    re.compile(r"\d{4}[–-]\d{4}"),               # 0000–6501
    re.compile(r"/4/PHYSI/"),
    re.compile(r"^Turn over$", re.I),
    re.compile(r"^SECTION\s+[AB]$", re.I),
    re.compile(r"^Answer all questions\.?$", re.I),
    re.compile(r"^Answer all of the questions", re.I),
    re.compile(r"^Answers must be written", re.I),
    re.compile(r"^Candidate session number$", re.I),
    re.compile(r"^©\s*International Baccalaureate", re.I),
    re.compile(r"^Instructions to candidates$", re.I),
    re.compile(r"^\d+\s+pages?$", re.I),
    re.compile(r"^SPECIMEN PAPER", re.I),
    re.compile(r"^MARKSCHEME$", re.I),
    re.compile(r"^Do not (open|turn over) this examination paper", re.I),
    re.compile(r"^Write your session number", re.I),
    re.compile(r"^y\s"),                          # physics bullet lines
    re.compile(r"^•\s"),
    re.compile(r"^The maximum mark for this examination paper is", re.I),
    re.compile(r"^A clean copy of the", re.I),
    re.compile(r"^This examination paper consists of", re.I),
    re.compile(r"^Section [AB] ", re.I),
    re.compile(r"^Total:?\s*\[", re.I),
    re.compile(r"^\d+\s*hours?", re.I),
]


def is_noise(t):
    return any(rx.search(t) for rx in NOISE)


QSTART = re.compile(r"^(?:([A-D])(\d{1,2})|(\d{1,2}))\.\s*(\S.*)$")
SUBPART = re.compile(r"^\(([a-z]|[ivx]{1,4})\)\s*")
MARKS = re.compile(r"\[(\d+)\s*marks?\]", re.I)
BARE_MARK = re.compile(r"\[(\d{1,2})\]\s*$")
BARE_ANY = re.compile(r"\[\d{1,2}\]")


def norm_ws(s):
    s = s.replace("\u00a0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


_LINE_CACHE = {}


def page_lines(doc, i):
    """Lines of page i, in *text-layer order* (which is correct for these PDFs),
    with y positions taken from char boxes. Noise lines are dropped. Cached.

    NB: we deliberately do NOT reuse extract_v3.fast_words here — its char-box
    re-assembly scrambles these particular PDFs (e.g. "A llnswer a questions").
    """
    key = (id(doc), i)
    if key in _LINE_CACHE:
        return _LINE_CACHE[key]
    page = doc[i]
    tp = page.get_textpage()
    n = tp.count_chars()
    ph = page.get_size()[1]
    keep, cur = [], []

    def flush():
        if not cur:
            return
        t = norm_ws("".join(c[2] for c in cur))
        if t and not is_noise(t):
            keep.append({"top": min(c[0] for c in cur),
                         "bottom": max(c[1] for c in cur),
                         "text": t})

    for k in range(n):
        ch = tp.get_text_range(k, 1)
        l, b, r, t = tp.get_charbox(k)
        if ch in ("\r", "\n"):
            flush(); cur = []
            continue
        cur.append((ph - t, ph - b, ch))
    flush()
    _LINE_CACHE[key] = keep
    return keep


def collect(doc, lo, hi):
    out = []
    for i in range(lo, hi):
        for ln in page_lines(doc, i):
            out.append({"page": i, **ln})
    return out


def _qstarts(rows):
    """Yield (index, row, key) for every question-start line.

    Handles plain numbering ("1.") and option-prefixed numbering ("A1." — CS
    Paper 2). Several specimen papers restart at 1 for a second variant, so a
    restart bumps a per-prefix variant counter and the key gets a 'v2' suffix;
    this keeps ids (and file names) unique instead of silently overwriting.
    """
    counters, variants = {}, {}
    for i, r in enumerate(rows):
        m = QSTART.match(r["text"])
        if not m:
            continue
        pre = m.group(1) or ""
        n = int(m.group(2) or m.group(3))
        if n == counters.get(pre, 0) + 1:
            counters[pre] = n
        elif n == 1 and counters.get(pre, 0) >= 1:
            variants[pre] = variants.get(pre, 0) + 1
            counters[pre] = 1
        else:
            continue
        v = variants.get(pre, 0)
        key = f"{pre}{n}" + (f"v{v + 1}" if v else "")
        yield i, r, key


def split_questions(rows):
    """Split a flat line list into questions using _qstarts()."""
    starts = list(_qstarts(rows))
    if not starts:
        return []
    qs = []
    for j, (i, r, key) in enumerate(starts):
        end = starts[j + 1][0] if j + 1 < len(starts) else len(rows)
        qs.append({"key": key, "lines": rows[i:end],
                   "start": (r["page"], r["top"])})
    return qs


def q_text(q):
    parts = []
    for r in q["lines"]:
        t = r["text"]
        # join soft-wrapped lines; keep sub-parts on their own line
        parts.append(t)
    txt = " ".join(parts)
    txt = norm_ws(txt)
    txt = re.sub(r"\s+([,.;:])", r"\1", txt)
    return txt


def q_marks(q):
    """Total marks for a question.

    Two IB conventions appear: "[3 marks]" anywhere, and a bare "[3]" at the end
    of a sub-part line (CS Paper 2/3, Physics 1B/2). Bare brackets are only
    accepted at end-of-line, otherwise array subscripts like "NAMES [0] [1]"
    would be counted as marks.
    """
    tot = 0
    for r in q["lines"]:
        t = r["text"]
        hits = MARKS.findall(t)
        if hits:
            tot += sum(int(h) for h in hits)
        else:
            # a lone "[3]" at end of line is a mark; several brackets on one line
            # means an array/list (e.g. "NAMES [0] [1] [2] [3] [4]")
            if len(BARE_ANY.findall(t)) == 1:
                m = BARE_MARK.search(t)
                if m:
                    tot += int(m.group(1))
    return tot or None


# --------------------------------------------------------------------------
# markschemes
# --------------------------------------------------------------------------
def parse_key_ms(doc, lo, hi):
    """Physics Paper 1A style answer key:  '1. C   16. C   31. C'"""
    ans = {}
    for i in range(lo, hi):
        t = doc[i].get_textpage().get_text_range()
        for m in re.finditer(r"(?m)(\d{1,2})\.\s+([A-D])(?=\s|$)", t):
            ans[str(int(m.group(1)))] = m.group(2)
    return ans


# front matter that must never be mistaken for an answer
MS_JUNK = re.compile(
    r"General Marking Instructions|Subject Details|Mark Allocation|"
    r"transferred the marks|left hand margin|award the mark|"
    r"Maximum total|Total \d+ marks|Do not award|Each statement worth",
    re.I)


def answer_start_index(rows):
    """index of the first line after the markscheme front matter."""
    for i, r in enumerate(rows):
        if re.match(r"^SECTION\s+[AB]\b", r["text"]) or \
           re.match(r"^Subject Details", r["text"]):
            return i + 1
    return 0


def parse_text_ms(doc, lo, hi):
    """CS / Physics 1B-2 style: numbered answers, possibly across pages.

    Keys follow _qstarts() ('3', 'A1', '1v2' …) so option papers and restarted
    variants map onto the right question.
    """
    rows = collect(doc, lo, hi)
    rows = rows[answer_start_index(rows):]
    starts = list(_qstarts(rows))
    out = {}
    for j, (i, r, key) in enumerate(starts):
        end = starts[j + 1][0] if j + 1 < len(starts) else len(rows)
        body = [rows[k]["text"] for k in range(i, end)]
        body[0] = body[0][QSTART.match(body[0]).end():]
        out[key] = norm_ws(" ".join(body))
    return out


def ms_band(doc, rows, qkey, out_path):
    """crop the markscheme region belonging to question qkey."""
    starts = list(_qstarts(rows))
    hit = next((j for j, (_, _, k) in enumerate(starts) if k == qkey), None)
    if hit is None:
        return None
    i, r, _ = starts[hit]
    if hit + 1 < len(starts):
        _, nr, _ = starts[hit + 1]
        end = (nr["page"], nr["top"])
    else:
        end = (rows[-1]["page"], rows[-1]["bottom"] + 4)
    return render_band(doc, rows, (r["page"], r["top"]), end, out_path)


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
def render_band(doc, rows, start, end, out_path):
    """stitch the vertical band [start, end) of a question into one JPEG."""
    (sp, st) = start
    (ep, et) = end
    tiles = []
    for i in range(sp, ep + 1):
        pg = doc[i]
        img = pg.render(scale=SCALE).to_pil().convert("RGB")
        W, H = img.size
        pw, ph = pg.get_size()
        sy = H / ph
        # content bounds of this page = min/max of kept lines
        pl = page_lines(doc, i)
        if not pl:
            continue
        ctop = min(x["top"] for x in pl)
        cbot = max(x["bottom"] for x in pl)
        top = max(st, ctop) if i == sp else ctop
        bot = min(et, cbot) if i == ep else cbot
        if bot - top < 3:
            continue
        box = (0, max(0, int((top - 6) * sy)), W, min(H, int((bot + 6) * sy)))
        if box[3] - box[1] < 6:
            continue
        tiles.append(img.crop(box))
    if not tiles:
        return None
    W = max(t.width for t in tiles)
    Hh = sum(t.height for t in tiles)
    if W < 60 or Hh < 24:
        return None
    canvas = Image.new("RGB", (W, Hh), "white")
    y = 0
    for t in tiles:
        canvas.paste(t, (0, y)); y += t.height
    try:
        canvas.save(out_path, quality=82, optimize=True)
    except Exception:
        return None
    finally:
        canvas.close()
    return (W, Hh)


def main():
    os.makedirs(OUT_JSON, exist_ok=True)
    os.makedirs(OUT_IMG, exist_ok=True)
    all_rows = []
    for spec in PAPERS:
        doc = pdfium.PdfDocument(spec["pdf"])
        qlo, qhi = spec["q"]
        rows = collect(doc, qlo, qhi)
        qs = split_questions(rows)

        # markscheme
        mlo, mhi = spec["ms"]
        ms_rows = collect(doc, mlo, mhi)
        ms_rows = ms_rows[answer_start_index(ms_rows):]
        if spec["markscheme"] == "key":
            ms = parse_key_ms(doc, mlo, mhi)
        else:
            ms = parse_text_ms(doc, mlo, mhi)

        outdir = os.path.join(OUT_IMG, spec["id"])
        os.makedirs(outdir, exist_ok=True)
        # drop this paper's own stale crops from previous runs (never touches
        # anything that doesn't carry this paper's id prefix)
        for old in os.listdir(outdir):
            if old.startswith(spec["id"]):
                try:
                    os.remove(os.path.join(outdir, old))
                except OSError:
                    pass

        made = []
        for qi, q in enumerate(qs):
            nxt = qs[qi + 1]["start"] if qi + 1 < len(qs) else None
            if nxt is None:
                last = q["lines"][-1]
                nxt = (last["page"], last["bottom"] + 4)
            qkey = q["key"]
            qnum = re.sub(r"\D", "", qkey)
            fn = f"{spec['id']}_{qkey}.jpg"
            p = os.path.join(outdir, fn)
            size = render_band(doc, q["lines"], q["start"], nxt, p)
            if not size:
                continue

            txt = q_text(q)
            ans = ms.get(qkey)
            if spec["markscheme"] == "key" and ans:
                ans = f"{qnum}. {ans}"
            if ans and (len(ans) < 3 or len(ans) > 900 or MS_JUNK.search(ans)):
                ans = None                     # parsed junk — fall back to the crop
            afn = f"{spec['id']}_{qkey}_ans.jpg"
            aimg = None
            if ms_band(doc, ms_rows, qkey, os.path.join(outdir, afn)):
                aimg = f"/figures/specimen/{spec['id']}/{afn}"

            made.append(dict(
                id=f"{spec['id']}-Q{qkey}",
                subject=spec["subject"], level=spec["level"],
                topic="Specimen paper", subtopic=spec["title"],
                paper_type=spec["paper_type"], command_term=None,
                marks=q_marks(q) or (1 if spec["markscheme"] == "key" else None),
                difficulty=None,
                question=txt or f"[See question image. Source: {spec['source']} Q{qkey}.]",
                answer=ans or "See official specimen markscheme.",
                explanation=(f"Official IB specimen paper question — {spec['title']}. "
                             f"Answer from the official markscheme."),
                source=f"{spec['source']} · Q{qkey}",
                tags=["mock", "specimen", "official", spec["id"]],
                book_id=None, book_section=None, book_page=None, in_book_order=None,
                source_type="mock", category="mock",
                question_image=f"/figures/specimen/{spec['id']}/{fn}",
                figure_image=None, answer_image=aimg,
                authored_by="import",
            ))
        doc.close()
        all_rows.extend(made)
        print(f"{spec['id']:22} questions={len(made):4}  ms_entries={len(ms):4}", flush=True)

    with open(os.path.join(OUT_JSON, "specimen.json"), "w") as f:
        json.dump({"questions": all_rows}, f, ensure_ascii=False)
    print("TOTAL", len(all_rows))


if __name__ == "__main__":
    main()
