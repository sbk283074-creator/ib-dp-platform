#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse the OCR'd HL specimen papers (Physics HL 2025) into questions.

Sections (HL only, pages 4-93 of the 158-page bundle):
  Paper 1A  MCQ  pages 5-25   (40 questions, stem + 4 options)
  Paper 1B  SAQ  pages 31-39  (structured questions)
  Paper 2   SAQ  pages 47-75  (structured questions)

Answers: the official specimen markscheme is printed in the same PDF but the
OCR of its table layout is unreliable, so answers reference the official
markscheme instead of embedding possibly-corrupt text.

Output: specimen_hl_import.json (array of question dicts for src/import.js)
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OCR = os.path.join(HERE, "specimen_ocr.jsonl")
OUT = os.path.join(HERE, "specimen_hl_import.json")

# A new MCQ starts with a noun-phrase opening (A/An/The/Two/...). Question
# words (What/Which/How...) and verbs continue the current stem and must NOT
# start a new question. OCR sometimes glues "A net" -> "Anet", so accept
# "A" followed by a lowercase letter as a new stem too.
MCQ_STEM = re.compile(
    r'^(A(?=\s|[a-z])|An\s|The\s|Two\s|Three\s|Four\s|Five\s|Six\s|Seven\s|Eight\s|Nine\s|Ten\s)', re.I)
PAGE_HDR = re.compile(r'^\d{4}[-_ ]?\d{4}$|^Ooo\d|^0{4}')

def load_pages():
    pages = {}
    for line in open(OCR, encoding="utf-8"):
        d = json.loads(line)
        pages[d["page"]] = d["text"]
    return pages

def clean(t):
    return t.strip()

def strip_header(text):
    """Remove the code header line(s) from a question page (e.g. '0000-6503')."""
    lines = text.split("\n")
    out = []
    for l in lines:
        s = l.strip()
        if not s:
            continue
        if PAGE_HDR.match(s) and len(out) == 0:
            continue  # drop code header at very top
        out.append(s)
    return "\n".join(out)

def parse_mcq_page(text):
    """Split a Paper 1A page into [(stem, [opt1..4])]."""
    t = strip_header(text)
    lines = [l.strip() for l in t.split("\n") if l.strip()]
    qs = []
    cur = None
    for l in lines:
        # drop footer-ish lines
        if re.match(r'^(Turn\s*over|Please do not write|EPO\d|$)', l, re.I):
            continue
        if MCQ_STEM.match(l) and cur is not None and len(cur["opts"]) >= 2:
            qs.append(cur)
            cur = {"stem": l, "opts": []}
        elif MCQ_STEM.match(l):
            cur = {"stem": l, "opts": []}
        elif cur is not None:
            if len(l) < 60 and not l.endswith("?"):
                cur["opts"].append(l)
            else:
                cur["stem"] += " " + l
    if cur is not None and len(cur["opts"]) >= 2:
        qs.append(cur)
    return qs

def parse_paper_page(text):
    """Split a Paper 1B/2 page into question chunks by '(a)' markers; fallback
    to the whole page as one question."""
    t = strip_header(text)
    # drop the repeated instruction line
    lines = [l.strip() for l in t.split("\n") if l.strip()]
    # remove 'Answer all questions ...' instruction
    lines = [l for l in lines if not re.match(r'^Answer all questions', l, re.I)]
    txt = "\n".join(lines)
    # chunk at (a) sub-part boundaries only if multiple (a) exist on the page
    parts = re.split(r'(?m)(?=^\s*\(a\))', txt)
    out = [p.strip() for p in parts if p.strip()]
    return out

def main():
    pages = load_pages()
    qs = []
    seq = [0]

    def emit(subject_paper, level, qtext, page):
        seq[0] += 1
        qs.append({
            "id": f"SPEC-PHY-HL-{re.sub(r'\\W', '', subject_paper)}-{seq[0]:03d}",
            "subject": "Physics",
            "level": level,
            "topic": subject_paper,
            "paper_type": subject_paper.split(" ")[-1] if "Paper" in subject_paper else None,
            "question": qtext,
            "answer": "See official specimen markscheme (Specimen Papers 2025, Physics HL).",
            "explanation": "Official IB specimen paper question (2025 syllabus).",
            "source": f"IB 样题 2025 Physics HL {subject_paper} · p{page}",
            "tags": ["specimen", "official", "paper"],
            "knowledge_point_ids": [],
            "marks": None,
            "difficulty": None,
            "authored_by": "import",
        })

    # ---- Paper 1A MCQ (p5-25) ----
    n_mcq = 0
    for p in range(5, 26):
        for q in parse_mcq_page(pages.get(p, "")):
            if len(q["stem"]) < 40:   # skip fragments (tails of previous Q)
                continue
            n_mcq += 1
            opt_text = "\n".join(f"{chr(65+i)}. {o}" for i, o in enumerate(q["opts"][:4]))
            qtext = f"{q['stem']}\n{opt_text}".strip()
            emit("Paper 1A", "HL", qtext, p)
    print(f"Paper 1A MCQ: {n_mcq}", flush=True)

    # ---- Paper 1B (p31-39) ----
    n_1b = 0
    for p in range(31, 40):
        for chunk in parse_paper_page(pages.get(p, "")):
            n_1b += 1
            emit("Paper 1B", "HL", chunk, p)
    print(f"Paper 1B chunks: {n_1b}", flush=True)

    # ---- Paper 2 (p47-75) ----
    n_2 = 0
    for p in range(47, 76):
        for chunk in parse_paper_page(pages.get(p, "")):
            n_2 += 1
            emit("Paper 2", "HL", chunk, p)
    print(f"Paper 2 chunks: {n_2}", flush=True)

    json.dump(qs, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"TOTAL {len(qs)} -> {OUT}", flush=True)

if __name__ == "__main__":
    main()
