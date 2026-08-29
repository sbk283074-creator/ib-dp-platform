#!/usr/bin/env python3
"""
Parse the OCR'd IB Computer Science classified past-paper book (ocr_all.jsonl)
into import-ready question records.

Book structure (verified):
  - Pages 1..(Markschemes header page - 1):  "Questions"  section.
      Each block starts with a code line, e.g.  18M.2.SL.TZO.4
      followed by question text + subparts (a, b.i, c ...) and [N] marks.
  - From the "Markschemes" header page onward: mark schemes, same codes,
      e.g.  Award [4 max]: ...  (verbatim, joined to the question by code).

OCR text is preserved verbatim (user rule: no adaptation of OCR artifacts).
Codes are the join key; both sections carry the same verbatim code.

Output shape matches the existing importer (src/import.js / questionRepo.js):
  id, subject, level, topic, subtopic, paper_type, command_term,
  marks, question, answer, explanation, source, knowledge_point_ids
"""
import json, re, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "ocr_all.jsonl")
OUT = os.path.join(HERE, "cs_import.json")

# Tolerant code regex: allows OCR 'O'->'0' in TZ and optional spacing.
CODE = re.compile(
    r'(?<!\d)(\d{2}[MN])\s*\.\s*(\d+)\s*\.\s*([SH]L)\s*\.\s*TZ\s*[O0]?\s*(\d*)\s*\.\s*(\d+)'
)
MARK = re.compile(r'\[(\d+)\]')
MAXMARK = re.compile(r'[Mm]aximum\s*mark[:\s]*(\d+)')

MONTH = {'M': 'May', 'N': 'November'}
COMMAND_TERMS = [
    "Describe", "Explain", "Construct", "Identify", "Outline", "State", "Compare",
    "Contrast", "Define", "Draw", "Evaluate", "Analyse", "Analyze", "Calculate",
    "Determine", "Suggest", "Show", "List", "Discuss", "Design", "Write", "Given",
    "Using", "With", "The", "A", "An",
]


def load_pages():
    pages = []
    with open(SRC) as f:
        for line in f:
            line = line.strip()
            if line:
                pages.append(json.loads(line))
    pages.sort(key=lambda p: p["page"])
    return pages


def find_marker(pages, pred):
    for p in pages:
        for ln in p["text"].splitlines():
            if pred(ln.strip().lower()):
                return p["page"]
    return None


def split_blocks(text):
    matches = list(CODE.finditer(text))
    blocks = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        code = m.group(0)
        # Normalize join key: OCR swaps '0'<->'O' in the TZ segment.
        # Bodies are kept verbatim; only the matching key is normalized.
        norm = code.replace('O', '0')
        body = text[start:end].strip()
        blocks.append((norm, code, body))
    return blocks


def make_id(code, seen):
    base = "CS-" + re.sub(r'[^A-Za-z0-9]', '-', code)
    if base not in seen:
        seen[base] = 0
        return base
    seen[base] += 1
    return f"{base}-{seen[base]}"


def detect_command_term(body):
    first = body.lstrip()
    # first token(s)
    for ct in COMMAND_TERMS:
        if re.match(rf'^{re.escape(ct)}\b', first):
            return ct
    return None


def build_record(code, groups, qbody, abody, seen):
    yy_full, paper, level, tz, qnum = groups
    yy = yy_full[:2]          # '18'
    letter = yy_full[2].upper()  # 'M' / 'N'
    year = 2000 + int(yy)
    month = MONTH.get(letter, 'May')
    topic = f"{year} {month}"
    paper_type = f"Paper {paper}"

    # marks: sum [N] in question body + Maximum mark
    marks = 0
    for mm in MARK.findall(qbody):
        marks += int(mm)
    for mm in MAXMARK.findall(qbody):
        marks += int(mm)
    marks = marks if marks > 0 else None

    rec = {
        "id": make_id(code, seen),
        "subject": "CS",
        "level": level,
        "topic": topic,
        "subtopic": None,
        "paper_type": paper_type,
        "command_term": detect_command_term(qbody),
        "marks": marks,
        "question": qbody,
        "answer": abody,
        "explanation": "(IB mark scheme provided as the answer. The source classified book contains no separate examiner report.)",
        "source": f"IB CS classified — {code}",
        "knowledge_point_ids": [],
    }
    return rec


def main():
    pages = load_pages()
    q_marker = find_marker(pages, lambda s: s == "questions")
    a_marker = find_marker(pages, lambda s: s.startswith("markscheme"))
    print(f"Questions header page: {q_marker}, Markschemes header page: {a_marker}")

    texts = {p["page"]: p["text"] for p in pages}
    qtext = "\n".join(texts[p] for p in sorted(texts) if p < a_marker)
    atext = "\n".join(texts[p] for p in sorted(texts) if p >= a_marker)

    qblocks = split_blocks(qtext)
    ablocks = split_blocks(atext)
    print(f"Q blocks: {len(qblocks)}, A blocks: {len(ablocks)}")

    qmap, amap = {}, {}
    for norm, code, body in qblocks:
        qmap.setdefault(norm, []).append((code, body))
    for norm, code, body in ablocks:
        amap.setdefault(norm, []).append((code, body))

    # report duplicate codes
    qdups = {c: len(v) for c, v in qmap.items() if len(v) > 1}
    adups = {c: len(v) for c, v in amap.items() if len(v) > 1}
    if qdups:
        print("Duplicate Q codes:", qdups)
    if adups:
        print("Duplicate A codes:", adups)

    seen = {}
    records = []
    matched = 0
    missing_a = []
    for norm, qbodies in qmap.items():
        if norm not in amap:
            missing_a.append(norm)
            continue
        # prefer the raw code from the question side for display/source
        raw_code = qbodies[0][0]
        # IMPORTANT: take the FIRST body for this code, not all bodies joined.
        # Joining would merge two different questions that happen to share a
        # code (e.g. an OCR duplicate), causing "trailing context" where the
        # next question's text leaks into the current one.
        qbody = qbodies[0][1].strip()
        abody = amap[norm][0][1].strip()
        m = CODE.search(raw_code.replace('O', '0'))
        groups = m.groups()
        records.append(build_record(raw_code, groups, qbody, abody, seen))
        matched += 1

    print(f"Matched (Q+A): {matched}")
    print(f"Q codes with NO matching A: {len(missing_a)} -> {missing_a[:20]}")
    a_only = [c for c in amap if c not in qmap]
    print(f"A codes with NO matching Q: {len(a_only)} -> {a_only[:20]}")

    # level / paper distribution
    from collections import Counter
    lvl = Counter(r["level"] for r in records)
    pap = Counter(r["paper_type"] for r in records)
    print("level dist:", dict(lvl))
    print("paper dist:", dict(pap))
    with_kp = sum(1 for r in records if r["knowledge_point_ids"])
    print(f"records with KP: {with_kp}/{len(records)}")
    tagged_cmd = sum(1 for r in records if r["command_term"])
    print(f"records with command_term: {tagged_cmd}/{len(records)}")

    if "--write" in sys.argv:
        with open(OUT, "w") as f:
            json.dump(records, f, ensure_ascii=False, indent=1)
        print(f"\nWROTE {len(records)} records -> {OUT}")

    return records


if __name__ == "__main__":
    main()
