#!/usr/bin/env python3
"""Dry-run extractor for Math AA questions.pdf (pestle.pages.dev export).

Splits the PDF into questions (first occurrence of each code) and mark schemes
(second occurrence of the same code), pairs them by code, parses the IB code
into structured fields, and de-duplicates against the existing Math past rows.

Outputs a manifest JSON (records with text + parsed fields). No DB write, no
image rendering in dry-run mode (PT_IMAGES=1 to also render figures).
"""
import os, re, sys, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pypdfium2 as pdfium

PDF = os.environ.get("PT_PDF", os.path.join(ROOT, "..", "..", "Math AA questions.pdf"))
OUT = os.environ.get("PT_OUT", "/tmp/math_aa_qb_dryrun.json")
DO_IMAGES = os.environ.get("PT_IMAGES", "0") == "1"
FIG_ROOT = os.path.join(ROOT, "public", "figures", "MathAA_QB")

CODE_RE = re.compile(
    r"^([A-Za-z0-9]{2,6})\.(\d{1,2})\.(SL|AHL|HL)\.TZ(\d)\.([A-Za-z0-9_]+)\s*$",
    re.M,
)

HEADER_RE = re.compile(r"QuestionBank Test[^\n]*\n|https?://[^\n]*\n|Page \d+ of \d+[^\n]*\n")
FOOTER_RE = re.compile(r"\n?Page \d+ of \d+\s*$")

SESSION = {"M": "May", "N": "Nov"}


def parse_code(code):
    m = CODE_RE.match(code + "\n")
    if not m:
        return None
    series, topic, level, tz, last = m.groups()
    rec = {
        "series": series,
        "topic_digit": int(topic),
        "level": level,
        "tz": int(tz),
        "variant": last,
        "qnum": int(re.search(r"\d+", last).group(0)) if re.search(r"\d+", last) else None,
    }
    # year/month
    sm = re.match(r"^(\d{2})([MN])$", series)
    if sm:
        rec["year"] = 2000 + int(sm.group(1))
        rec["month"] = SESSION[sm.group(2)]
    else:
        rec["year"] = None
        rec["month"] = None
    rec["paper"] = f"Paper {int(topic)}" if int(topic) in (1, 2, 3) else None
    return rec


def build_skip_set(db_path):
    """Dedup is performed in the Node importer (better-sqlite3). Kept for
    reference; returns empty here so the dry-run reports the full candidate set."""
    return set()


def identity(rec):
    if rec.get("year") is None:
        return None
    lvl = "HL" if rec["level"] in ("AHL", "HL") else "SL"
    return (rec["year"], rec["month"], rec["tz"], rec["paper"], lvl, rec["qnum"])


def main():
    pdf = pdfium.PdfDocument(PDF)
    N = len(pdf)
    pages_text = []
    for i in range(N):
        t = pdf[i].get_textpage().get_text_range()
        t = HEADER_RE.sub("", t)
        t = FOOTER_RE.sub("", t)
        pages_text.append(t)

    # collect code occurrences: (page, charpos, code)
    occ = []  # list of dicts
    for i in range(N):
        for m in CODE_RE.finditer(pages_text[i]):
            occ.append({"page": i, "pos": m.start(), "code": m.group(0).strip(), "linestart": m.start()})
    occ.sort(key=lambda o: (o["page"], o["pos"]))

    # first vs second occurrence per code
    seen = {}
    for o in occ:
        c = o["code"]
        if c not in seen:
            seen[c] = {"q": o, "ms": None}
        else:
            seen[c]["ms"] = o

    # ordered first occurrences (questions) and second occurrences (mark schemes)
    q_occ = sorted([seen[c]["q"] for c in seen], key=lambda o: (o["page"], o["pos"]))
    ms_occ = sorted([seen[c]["ms"] for c in seen if seen[c]["ms"]], key=lambda o: (o["page"], o["pos"]))

    # One concatenated text + page offsets for clean slicing.
    full = "\n".join(pages_text)
    page_start = [0]
    for t in pages_text:
        page_start.append(page_start[-1] + len(t) + 1)

    def abspos(o):
        return page_start[o["page"]] + o["pos"]

    # Hard boundary: the "Markschemes" section header. Question blocks must not
    # cross into it (otherwise the last question swallows all mark schemes).
    ms_header = None
    m = re.search(r"(?im)^\s*Markschemes?\s*$", full)
    if m:
        ms_header = m.start()
    elif ms_occ:
        ms_header = abspos(ms_occ[0])

    def slice_text(start_occ, next_occ, hard_stop=None):
        s = abspos(start_occ)
        nl = full.find("\n", s)
        s = nl + 1 if nl != -1 else len(full)  # skip the code line itself
        e = abspos(next_occ) if next_occ is not None else len(full)
        if hard_stop is not None and e > hard_stop:
            e = hard_stop
        return full[s:e].strip()

    # page ranges for image rendering (Phase B)
    def page_range(start_occ, occ_list):
        idx = occ_list.index(start_occ)
        end = occ_list[idx + 1] if idx + 1 < len(occ_list) else None
        return (start_occ["page"], (end["page"] if end else N - 1))

    skip = build_skip_set(os.path.join(ROOT, "data", "app.db"))

    records = []
    skipped = 0
    no_ms = 0
    for c, occs in seen.items():
        q = occs["q"]
        ms = occs["ms"]
        rec = parse_code(c)
        if not rec:
            continue
        qi = q_occ.index(q)
        next_q = q_occ[qi + 1] if qi + 1 < len(q_occ) else None
        qtext = slice_text(q, next_q, hard_stop=ms_header)
        if ms:
            mi = ms_occ.index(ms)
            next_ms = ms_occ[mi + 1] if mi + 1 < len(ms_occ) else None
            atext = slice_text(ms, next_ms)
        else:
            atext = ""
            no_ms += 1
        ident = identity(rec)
        if ident and ident in skip:
            skipped += 1
            continue
        # marks total
        mt = re.search(r"\[(\d+)\s*marks?\]", atext, re.I)
        marks = int(mt.group(1)) if mt else None
        if marks is None:
            # sum part marks in question
            parts = re.findall(r"\[(\d+)\]", qtext)
            marks = sum(int(x) for x in parts) if parts else None
        level_disp = "SL" if rec["level"] == "SL" else "AHL"
        topic = f"Topic {rec['topic_digit']}" if rec["series"] in ("SPM", "EXN", "EXM") else "AA HL"
        safe = re.sub(r"[^A-Za-z0-9]", "_", c)
        records.append({
            "id": f"MAAQB_{safe}",
            "code": c,
            "subject": "Math AA",
            "level": level_disp,
            "topic": topic,
            "subtopic": rec["variant"] if rec["series"] in ("SPM", "EXN", "EXM") else None,
            "paper_type": rec["paper"],
            "marks": marks,
            "question": qtext,
            "answer": atext,
            "question_image": None,
            "answer_image": None,
            "source": c,
            "category": "questionbank",
            "review_status": "new",
            "year": rec["year"],
            "month": rec["month"],
            "tz": rec["tz"],
            "series": rec["series"],
        })

    out = {
        "source_pdf": os.path.basename(PDF),
        "total_codes": len(seen),
        "with_markscheme": len(seen) - no_ms,
        "skipped_existing": skipped,
        "imported": len(records),
        "records": records,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"codes={len(seen)} with_ms={len(seen)-no_ms} skipped_existing={skipped} imported={len(records)}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
