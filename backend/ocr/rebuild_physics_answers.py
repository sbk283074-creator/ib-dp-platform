#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rebuild RAW-PHYSICS P2/P3 answers from the original IB markscheme TABLES so that
each marking step, its "Award …" note and the marks are horizontally aligned
(the earlier flat-text extraction scrambled the Notes column after the Answers).

Uses pdfplumber table extraction (per-cell geometry) -> per (qnum, letter):
    (a) [2 marks]
    • step1 ✓   [Award [1 max] for 1.28 m/s (mass of pellet neglected)]
    • step2 ✓   [Award [2] for BCA]
Only updates questions whose source is a raw Physics Paper 2/3 markscheme.
"""
import json, os, re, sqlite3, sys
import pdfplumber

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_figures as F

DB_PATH = F.DB_PATH
TICK = re.compile(r"[✓✔\uf0bc\uf0d8\uf0fc\uf0b7]|\(cid:\d+\)")
AWARD = re.compile(r"(?=Award\s)")

def _norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def cell_text(page, bbox):
    if not bbox:
        return ""
    t = (page.crop(bbox).extract_text() or "").strip()
    # strip table header words that sometimes merge into the first data row
    for hw in ("Question", "Answers", "Notes", "Total"):
        if t.lower().startswith(hw.lower()):
            t = t[len(hw):].strip()
            break
    return t


def parse_qcell(text):
    t = text.strip()
    # numbered row: "1 a i" / "1. a" / header-overlap "Que 17 estio a on"
    m = re.search(r"(\d{1,2})[.\s]+(?:[a-z]*\s+)*?([a-f])(?![a-z])", t)
    if m:
        return int(m.group(1)), m.group(2), None
    m = re.fullmatch(r"(\d{1,2})\s*\.?", t)
    if m:
        return int(m.group(1)), None, None
    # continuation row: "a ii"
    m = re.search(r"^([a-f])(?![a-z])", t)
    if m:
        return None, m.group(1), None
    return None


def extract_answers_from_file(path):
    """-> {(qnum, letter): [(answers_text, notes_text, total), ...]}  (rows in order)"""
    out = {}
    cur_qnum = None
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            for t in pg.find_tables():
                for row in t.rows:
                    if not row.cells:
                        continue
                    cells = []
                    for c in row.cells:
                        cells.append(tuple(round(v) for v in c) if c else None)
                    widths = [(i, (c[2] - c[0])) for i, c in enumerate(cells) if c]
                    if not widths:
                        continue
                    ai = max(widths, key=lambda x: x[1])[0]
                    qcells = [c for c in cells[:ai] if c]
                    qtext = " ".join(cell_text(pg, c).replace("\n", " ") for c in qcells)
                    parsed = parse_qcell(qtext)
                    if not parsed:
                        continue
                    qnum, letter, roman = parsed
                    if qnum is not None:
                        cur_qnum = qnum
                    if qnum is None and letter is None:
                        continue
                    key = (cur_qnum, letter)
                    if key[0] is None:
                        continue
                    atext = cell_text(pg, cells[ai])
                    if not atext:
                        continue
                    ncell = cells[ai + 1] if ai + 1 < len(cells) else None
                    ntext = cell_text(pg, ncell)
                    tcell = cells[-1]
                    total = cell_text(pg, tcell)
                    out.setdefault(key, []).append((atext, ntext, total))
    return out


def rebuild_answer(rows):
    """Build aligned answer text: steps split by ticks, notes matched 1:1 when counts agree."""
    out = []
    total_sum = 0
    for atext, ntext, total in rows:
        steps = [_norm(s) for s in TICK.split(atext) if _norm(s)]
        if not steps:
            steps = [_norm(atext)]
        # notes: prefer splitting on consecutive "Award ", else newlines
        notes = []
        if "Award" in ntext:
            notes = [_norm(n) for n in AWARD.split(ntext) if _norm(n)]
        if len(notes) < 2:
            notes = [_norm(n) for n in ntext.split("\n") if _norm(n)]
        if len(notes) != len(steps):
            notes = [_norm(ntext)] if _norm(ntext) else []
        for i, s in enumerate(steps):
            note = notes[i] if i < len(notes) else ""
            if note.lower() == "notes":
                note = ""
            if note:
                out.append(f"• {s}   [{note}]")
            else:
                out.append(f"• {s}")
        if total:
            try:
                total_sum += int(re.sub(r"\D", "", total) or 0)
            except ValueError:
                pass
    if total_sum:
        out.append(f"[Total: {total_sum} marks]")
    return "\n".join(out)


def main():
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    recs = db.execute(
        "SELECT id FROM questions WHERE subject='Physics' AND paper_type IN ('Paper 2','Paper 3') AND id LIKE 'PHY-RAW-%'"
    ).fetchall()
    print(f"[rebuild] {len(recs)} raw physics P2/P3 records", flush=True)

    # markscheme file per (label, tz, paper_norm)
    ans_phys = {}
    for label, disp, paper, tz, qp, msp in F.X.phy_raw_walker():
        if msp:
            ans_phys.setdefault((label, tz), {})[paper.lower().replace(" ", "")] = msp

    cache = {}
    updated = 0
    skipped = 0
    for (rid,) in recs:
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
            skipped += 1
            continue
        pm = re.match(r"Paper(\d+[AB]?)(.*)", parts[pi])
        if not pm:
            skipped += 1
            continue
        paper_norm = ("paper" + pm.group(1) + (pm.group(2) or "")).lower()
        m = re.search(r"-Q(\d+)([a-f])?$", rid)
        if not m:
            skipped += 1
            continue
        qnum = int(m.group(1))
        letter = m.group(2)
        mspath = ans_phys.get((label, tz), {}).get(paper_norm)
        if not mspath:
            skipped += 1
            continue
        if mspath not in cache:
            cache[mspath] = extract_answers_from_file(mspath)
        data = cache[mspath].get((qnum, letter))
        if not data:
            skipped += 1
            continue
        new_answer = rebuild_answer(data)
        if not new_answer:
            skipped += 1
            continue
        cur.execute("UPDATE questions SET answer = ? WHERE id = ?", (new_answer, rid))
        updated += 1

    db.commit()
    print(f"[rebuild] updated={updated} skipped={skipped} files_parsed={len(cache)}", flush=True)
    s = db.execute("SELECT answer FROM questions WHERE id='PHY-RAW-2024-05-TZ1-Paper2-Q1a'").fetchone()
    if s:
        print("[rebuild] sample Q1a:\n" + s[0][:300])
    db.close()


if __name__ == "__main__":
    main()
