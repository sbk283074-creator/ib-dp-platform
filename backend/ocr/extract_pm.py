#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified extractor: Physics HL + Math AA HL question bank (classified) + past papers (2016+).

Source layout:
  A) Classified banks — markscheme PDFs REPEAT each prompt, then "Markscheme", then
     the answer, then "Examiners report". Self-contained Q+A+explanation.
       - Physics-HL-Topic questions/Topic N|Option X/{HL-paper1..3.pdf, markscheme-*}
       - IB数学AA  HL 分章练习/.../Topic N/{HL-paper1..3.pdf, markscheme-*}
  B) Raw past papers (>= MIN_YEAR) — question PDF (prompts) + markscheme (ANSWER-ONLY,
     keyed by question number). Pair by (question number, subpart letter).
       - Physics-HL-Past Papers&Mark Schemes(...)/<session>/
       - IB 数学 AA  HL 历年真题/{2024.5HL, 2024.11HL, IB 数学 HL 真题（2006-23）/<session>}

Rules:
  - classified: import ALL (verbatim)
  - raw: only >= 2016, clearly labelled source
  - dedup: if a classified question duplicates a raw (真题) question, keep only the raw one
Output: import-ready JSON array for `npm run import`.
"""
import json, os, re
from collections import Counter
import pdfplumber

ROOT = "/Users/lucas.ma/Downloads/dp learning"
PHY_CLS = os.path.join(ROOT, "Physics-HL-Topic questions")
MATH_CLS = os.path.join(ROOT, "IB数学AA  HL 分章练习", "IB数学AA-Mathmatics HL IB Question Bank")
PHY_RAW = os.path.join(ROOT, "Physics-HL-Past Papers&Mark Schemes(1999.05~2025.11)")
MATH_RAW = os.path.join(ROOT, "IB 数学 AA  HL 历年真题")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "physics_math_import.json")
MIN_YEAR = 2016

S_PHY = "Physics"
S_MATH = "Math AA HL"

PHY_KP = {f"Topic {i}": f"PHY-T{i}" for i in range(1, 13)}
PHY_KP.update({f"Option {c}": f"PHY-OPT{c}" for c in "ABCD"})
MATH_KP = {f"Topic {i}": f"MATH-T{i}" for i in range(1, 11)}

NON_EN = ("French", "Spanish", "German", "[German]")

# ---------------------------------------------------------------- helpers
def pdf_text(p):
    try:
        with pdfplumber.open(p) as pdf:
            return "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    except Exception as e:
        print(f"  [WARN] pdf failed {os.path.basename(p)}: {e}", flush=True)
        return ""

def clean(s):
    return re.sub(r"\n{3,}", "\n\n", (s or "")).strip()

def strip_noise(text):
    out = []
    for ln in text.split("\n"):
        s = ln.strip()
        if re.fullmatch(r"–\s*\d+\s*–.*", s): continue
        if re.fullmatch(r"\d{4}\s*–\s*\d{4}[A-Z0-9]*", s): continue
        if re.fullmatch(r"M\d{2}/[0-9A-Z/]+", s): continue
        if re.fullmatch(r"\d+EP\d+", s): continue
        if re.fullmatch(r"©.*", s): continue
        if re.fullmatch(r"Turn\s+over.*", s): continue
        if re.fullmatch(r"[.\s·]+", s): continue          # dotted answer lines
        if re.fullmatch(r"(continued|blank page).*", s, re.I): continue
        out.append(ln)
    return "\n".join(out)

def norm_tokens(s):
    return Counter(re.findall(r"[a-z0-9]+", s.lower()))

def marks_in(s):
    return sum(int(m) for m in re.findall(r"\[(\d+)(?:\s*marks?)?\]", s or ""))

COMMANDS = ["calculate", "show", "find", "state", "determine", "explain", "outline",
    "define", "describe", "suggest", "draw", "sketch", "evaluate", "solve", "deduce",
    "prove", "identify", "estimate", "distinguish", "discuss", "justify", "derive",
    "hence", "construct", "write", "complete", "use", "verify", "comment", "compare",
    "express", "simplify", "factorise", "factorize", "expand", "graph", "annotate",
    "label", "measure", "predict", "design", "plot", "tabulate", "list", "give",
    "form", "investigate", "transform", "convert", "apply", "interpret", "sketch"]

def command_term(qtext):
    first = re.search(r"[A-Za-z]+", qtext or "")
    if not first:
        return None
    w = first.group(0).lower()
    return first.group(0) if w in COMMANDS else None

# ---------------------------------------------------------------- Format A: prompt-repeat markscheme (classified)
EXPL_STOP = ("very few", "most candidates", "some candidates", "in a few", "large numbers",
    "part (a)", "part (b)", "part (c)", "do not", "many candidates", "few candidates",
    "the majority", "almost all", "candidates", "this was", "this question", "good discriminator",
    "well answered", "award", "note:", "the response", "responses", "it is", "when calculating",
    "a distinction", "the calculated", "this is", "both", "there were", "there was", "others",
    "candidates who", "a common", "the most common", "common error", "follow through")

def split_expl_prompt(lines):
    """In the tail after 'Examiners report', find where the NEXT block's prompt starts.
    Returns index into lines (prompt begins there); explanation = lines[:index]."""
    n = len(lines)
    # 1) [N/A] at the start -> explanation is exactly those lines
    k = 0
    while k < n and lines[k].strip() in ("[N/A]", ""):
        k += 1
    if k > 0 and lines[k - 1].strip() == "[N/A]":
        return k
    # 2) anchor-based scan
    anchor = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            continue
        if ("?" in s
                or re.search(r"\[\d+(\s*marks?)?\]", s)
                or re.match(r"^[A-D]\.", s)
                or re.match(r"^\([a-z]\)", s)
                or (re.match(r"^[a-z]\.", s) and "[" in s)
                or re.match(r"^This question is about", s)
                or re.match(r"^The diagram|The graph|The figure|The circuit", s)):
            anchor = i
            break
    if anchor is not None:
        start = anchor
        # include preceding short intro lines (question statement split across lines)
        j = anchor - 1
        while j >= 0:
            prev = lines[j].strip()
            if not prev:
                j -= 1
                continue
            low = prev.lower()
            if len(prev) <= 60 or not prev.endswith("."):
                if not any(low.startswith(w) for w in EXPL_STOP):
                    start = j
                    j -= 1
                    continue
            break
        return start
    # 3) no anchor: math-style report ("a. ..." / "b. ..." prose) then prompt
    last_sub = -1
    for i, ln in enumerate(lines):
        if re.match(r"^[a-z]\.\s", ln.strip()):
            last_sub = i
    if last_sub >= 0:
        for i in range(last_sub + 1, n):
            if lines[i].strip() and lines[i].strip()[0].isupper():
                return i
        return n
    # 4) fallback: whole tail is prompt (question kept, possibly with report prose)
    return 0

def split_question_bleed(qlines):
    """Mirror of the parse_qpdf mid-line stem-bleed fix, at the block level.

    If a non-first question line contains a NEXT question's numbered start
    mid-line (a digit number preceded by a sentence terminator, then a marks
    bracket / '(' / capital — i.e. "N. [18 marks]" or "N. The ..."), split
    there: everything before stays with this question, the remainder (plus all
    later lines) is returned as `spill` to be prepended to the NEXT block's
    question. This keeps a big question's stem from being swallowed by the
    previous big question's last sub-part.

    Returns (kept_lines, spill_lines_or_None).
    """
    kept = []
    for idx, ln in enumerate(qlines):
        s = ln.strip()
        if idx > 0 and s:
            mm = Q_MID.search(s)
            if mm:
                pre = s[:mm.start()].rstrip()
                if _mid_bleed_ok(pre):
                    spill = [s[mm.start():]]
                    spill.extend(qlines[idx + 1:])
                    if pre.strip():
                        kept.append(ln[:mm.start()].rstrip())
                    return kept, spill
        kept.append(ln)
    return kept, None


# Prompt-anchor phrases that, when they appear MID-question-text (not at the
# very start), signal the beginning of the NEXT big question's stem that bled
# onto the previous question's tail (e.g. examiner-report spill from a prior
# page with no separator rule between them).
_PROMPT_ANCHOR_LINE = re.compile(
    r"^\s*(This question is about|The diagram|The graph|The figure|"
    r"The circuit|The sketch|The picture|The following diagram)\b"
)

def split_prompt_anchor(qlines):
    """Split question lines at a mid-text prompt anchor.

    Returns (kept_lines, spill_lines_or_None). If a line past the first matches
    _PROMPT_ANCHOR_LINE, everything from that line on is the next question's
    spill (prepended to the following block by the caller).
    """
    for idx in range(1, len(qlines)):
        if _PROMPT_ANCHOR_LINE.match(qlines[idx].strip()):
            return qlines[:idx], qlines[idx:]
    return qlines, None


def parse_prompt_repeat(text):
    """Return list of {question, answer, explanation}."""
    blocks = []
    cur = {"question": [], "answer": [], "explanation": []}
    state = "question"
    for ln in text.split("\n"):
        s = ln.strip()
        if s == "Markscheme":
            if state in ("answer", "explanation"):
                blocks.append(cur)
                cur = {"question": [], "answer": [], "explanation": []}
            state = "answer"
        elif s == "Examiners report":
            state = "explanation"
        else:
            cur[state].append(ln)
    if cur["question"] or cur["answer"]:
        blocks.append(cur)
    # post-process: move (explanation tail + next prompt) -> split, push prompt head into next block
    BARE = re.compile(r"^[a-z]{1,4}(?:\.{1,2}[ivxlc]{1,4}){0,4}\.?\s*$")
    out = []
    for i, b in enumerate(blocks):
        qlines = [ln for ln in b["question"]
                  if ln.strip() != "[N/A]" and not (ln.strip() and BARE.match(ln.strip()))]
        q_kept, q_spill = split_question_bleed(qlines)
        if q_spill is None:
            q_kept, q_spill = split_prompt_anchor(qlines)
        if q_spill is not None and i + 1 < len(blocks):
            blocks[i + 1]["question"] = q_spill + blocks[i + 1]["question"]
        q = clean("\n".join(q_kept))
        a = clean("\n".join(b["answer"]))
        e_lines = b["explanation"]
        split = split_expl_prompt(e_lines)
        e = clean("\n".join(e_lines[:split]))
        if i + 1 < len(blocks):
            head = [ln for ln in e_lines[split:]
                    if ln.strip() != "[N/A]" and not (ln.strip() and BARE.match(ln.strip()))]
            blocks[i + 1]["question"] = head + blocks[i + 1]["question"]
        if len(q) >= 15:
            out.append({"question": q, "answer": a, "explanation": e})
    return out

# ---------------------------------------------------------------- separator lines
# The classified markscheme PDFs draw a thin horizontal rule between consecutive
# big questions (verified: 96% of P1 pages, 78% of P3 pages, 59% of P2 pages).
# That rule is the ground-truth question boundary and is far more reliable than
# text heuristics — it cleanly separates Q(n)'s "Examiners report" tail from
# Q(n+1)'s prompt even when both land on the same page. We use it as a HARD
# question break wherever it is present, and fall back to the text heuristic
# (parse_prompt_repeat) only on pages that lack the rule.
def _sep_lines_pdfium(page, merge_tol=3.0, min_frac=0.7, max_h=2.5):
    """Return separator-line y-centres (PDF coords, bottom-up) for a pypdfium page."""
    W = float(page.get_width())
    raw = []
    for o in page.get_objects():
        if o.type != 2:  # path only
            continue
        b = o.get_bounds()  # l,t,r,b (bottom-up)
        w = b[2] - b[0]
        h = b[3] - b[1]
        if w >= min_frac * W and 0 <= h < max_h:
            raw.append((b[1] + b[3]) / 2)
    raw.sort()
    merged = []
    for y in raw:
        if merged and abs(y - merged[-1]) <= merge_tol:
            merged[-1] = (merged[-1] + y) / 2
        else:
            merged.append(y)
    return merged


def _page_region_texts(pdfium_page, plumber_page):
    """Split a markscheme page's text into region texts at separator lines.

    Returns list of text strings, one per region (a region = the text between two
    consecutive separator rules, or between a rule and the page edge). Each region
    is then fed to parse_prompt_repeat so that the existing Markscheme/Examiners
    report state machine still works inside a single question.

    The page header rule (top < ~12% of page height) is ignored — it is the
    running "HL Paper N" banner, not a question boundary.
    """
    H = float(pdfium_page.get_height())
    ys_pdf = _sep_lines_pdfium(pdfium_page)
    # screen (top-down) y of separators, ignoring the header rule near the top
    ys_screen = sorted([H - y for y in ys_pdf if (H - y) >= 0.12 * H])
    if not ys_screen:
        # No separator rule on this page: fall back to whole-page heuristic.
        return [plumber_page.extract_text() or ""]

    # Build text lines with their top coordinate from pdfplumber words.
    words = plumber_page.extract_words()
    line_map = {}  # rounded top -> list of word texts
    for w in words:
        key = round(w["top"])
        line_map.setdefault(key, []).append(w["text"])
    if not line_map:
        return [plumber_page.extract_text() or ""]

    # Assign each text line to a region (0 = above first rule, 1 = between 1st&2nd, ...)
    def region_of(top):
        r = 0
        for y in ys_screen:
            if top >= y:
                r += 1
        return r

    regions = {}
    for top in sorted(line_map):
        r = region_of(top)
        regions.setdefault(r, []).append(" ".join(line_map[top]))
    # preserve region order
    return ["\n".join(regions[r]) for r in sorted(regions)]


# A region (text between two separator rules) starts a NEW question only if its
# text contains a question-prompt anchor. Otherwise it is a continuation of the
# current open question (e.g. the previous question's "Examiners report" tail that
# spilled above the rule, or a markscheme that landed on the next region).
_PROMPT_ANCHOR = re.compile(
    r"(This question is about|The diagram|The graph|The figure|The circuit|"
    r"The sketch|The picture|The following diagram|Define |State |Calculate |"
    r"Show that |Determine |Derive |Explain |Outline |Describe |Discuss |"
    r"Estimate |Measure |Sketch |Plot |Draw |Deduce |Suggest |Compare |"
    r"Construct |Find |Which\b|What\b|How\b|Why\b|An |A |The )"
)
# Markscheme / report continuations that must NEVER start a new question.
_CONTINUATION = re.compile(
    r"^\s*(Markscheme|Examiners report|\[N/A\]|\(\s*N/A\s*\)|"
    r"[a-e]\.\s|\([a-e]\)|a\.i\.|b\.|c\.|d\.|e\.)"
)

def _is_prompt_start(text):
    """True if `text` opens a brand-new question (vs. being a continuation)."""
    t = text.strip()
    if not t:
        return False
    # Explicit continuation markers -> never a new question.
    if _CONTINUATION.match(t):
        return False
    # A clear prompt anchor must appear within the first ~3 lines.
    head = "\n".join(t.split("\n")[:3])
    return bool(_PROMPT_ANCHOR.search(head))


def _physics_line_split(pypdf, plumber_pdf, clean_header):
    """Physics-only: split markscheme pages at separator rules, accumulate
    questions across pages/regions, merging continuations (report tails or
    markschemes spilled across a rule) into the open question.
    """
    blocks = []          # finalized question dicts
    cur = None           # current open question being accumulated
    for pn in range(len(pypdf)):
        ppage = pypdf[pn]
        plpage = plumber_pdf.pages[pn]
        region_texts = _page_region_texts(ppage, plpage)
        for rt in region_texts:
            rt = clean_header(rt)
            if not rt.strip():
                continue
            sub = parse_prompt_repeat(rt)
            for b in sub:
                if _is_prompt_start(b["question"]):
                    if cur is not None:
                        blocks.append(cur)
                    cur = dict(b)
                else:
                    if cur is None:
                        cur = dict(b)
                    else:
                        if b["question"].strip():
                            cur["question"] = (cur["question"] + "\n" + b["question"]).strip()
                        if b["answer"].strip() and "see source markscheme" not in b["answer"]:
                            cur["answer"] = b["answer"]
                        if b["explanation"].strip() and "no examiner report" not in b["explanation"]:
                            cur["explanation"] = (cur["explanation"] + "\n" + b["explanation"]).strip()
    if cur is not None:
        blocks.append(cur)
    return blocks


def classified_blocks(subject, folder, paper, kp_map):
    base = PHY_CLS if subject == S_PHY else MATH_CLS
    fdir = os.path.join(base, folder)
    if not os.path.isdir(fdir):
        return []
    msf = os.path.join(fdir, f"markscheme-{paper}.pdf")
    if not os.path.exists(msf):
        return []
    # Strip the "HL Paper N" header line that pdfplumber sometimes repeats.
    def clean_header(t):
        lines = t.split("\n")
        if lines and re.match(r"^HL\s+Paper\s*\d+", lines[0].strip()):
            return "\n".join(lines[1:])
        return t

    import pypdfium2 as pdfium
    pypdf = pdfium.PdfDocument(msf)

    # Physics classified banks reliably draw a thin separator rule between
    # consecutive big questions (verified 96%/78%/59% of P1/P3/P2 pages). That
    # rule is the ground-truth boundary and fixes the within-page stem-bleed
    # (Q(n)'s "Examiners report" tail spilling into Q(n+1)'s prompt). We use it
    # as a HARD question break.
    #
    # Math classified questions frequently span multiple pages and their rules
    # are less consistent, so the per-region split over-fragments them. For math
    # we keep the original whole-document text heuristic, which already handles
    # its layout correctly.
    if subject == S_PHY:
        with pdfplumber.open(msf) as pl:
            blocks = _physics_line_split(pypdf, pl, clean_header)
    else:
        with pdfplumber.open(msf) as pl:
            full = "\n".join((pg.extract_text() or "") for pg in pl.pages)
        blocks = parse_prompt_repeat(full)
    pypdf.close()
    out = []
    kpid = kp_map.get(folder)
    paper_id = re.sub(r"\D", "", paper)  # "1"
    seq = 0
    for b in blocks:
        seq += 1
        q = b["question"]
        out.append({
            "id": f"{'PHY' if subject==S_PHY else 'MATH'}-CLS-{re.sub(r'\W','',folder)}-P{paper_id}-{seq:03d}",
            "subject": subject,
            "level": "HL",
            "topic": folder,
            "subtopic": f"Paper {paper_id}",
            "paper_type": f"Paper {paper_id}",
            "question": q,
            "answer": b["answer"] or "(see source markscheme)",
            "explanation": b["explanation"] or "(no examiner report in source)",
            "source": f"{subject} HL classified bank — {folder} / {paper}",
            "marks": marks_in(q + " " + b["answer"]) or None,
            "command_term": command_term(q),
            "knowledge_point_ids": [kpid] if kpid else [],
            "_cls": True,
        })
    return out

# ---------------------------------------------------------------- raw: Q-PDF parse
Q_START = re.compile(r"^(\d{1,2})\.(?:\s+(.*)|$)")
# A next-question number appearing MID-LINE (pdfplumber merged it onto the
# previous line). Not preceded/followed by a digit (excludes decimals "16.0"),
# and not preceded by "digit-dot" (excludes decimals like "1.34"). A sentence
# period ("follows. 2.") is allowed — that IS a real bleed. The anchor after
# "N. " allows a capital letter, "(", or "[" (IB stems usually open with a
# marks bracket, e.g. "2. [18 marks] The function...").
Q_MID = re.compile(r"(?<!\d)(?<!\d\.)(\d{1,2})\.(?!\d)\s+(?=[A-Z(\[])")
# Reference words that, when immediately before the number, mean it is NOT a
# new question (e.g. "See Figure 3."). Checked only in the tail before the no.
_MID_REF = ("figure", "fig.", "equation", "section", "step", "diagram",
            "table", "graph", "refer", "see ", "as in", "shown in", "(", "[",
            "e.g.", "i.e.", "eq.")
_MID_TERM = ".!?):]"

def _mid_bleed_ok(pre):
    """Guard for a mid-line next-question number: the char before it must be a
    sentence terminator (not a digit/colon), it must not be a reference phrase,
    and it must not be a digit-colon time context ('09:00. Estimate')."""
    if not pre:
        return False
    if pre[-1:] not in _MID_TERM:
        return False
    if re.search(r"\d:$", pre):
        return False
    if any(w in pre[-14:].lower() for w in _MID_REF):
        return False
    return True

def parse_qpdf(text):
    """Return {qnum: {'intro': [..], 'parts': {letter: [lines..]}}}."""
    qs = {}
    cur = None
    cur_part = None
    cur_qnum = 0
    for ln in text.split("\n"):
        s = ln.strip()
        m = Q_START.match(s)
        if m:
            qnum = int(m.group(1))
            if qnum == 0 or qnum > 99:
                if cur is not None:
                    cur["intro"].append(s)
                continue
            cur = qs.setdefault(qnum, {"intro": [], "parts": {}})
            cur_part = None
            cur_qnum = qnum
            rest = (m.group(2) or "").strip()
            sm = re.match(r"^\(([a-f])\)\s*(.*)$", rest)
            if sm:
                cur_part = sm.group(1)
                cur["parts"].setdefault(cur_part, [])
                if sm.group(2).strip():
                    cur["parts"][cur_part].append(sm.group(2).strip())
            elif rest:
                cur["intro"].append(rest)
            continue
        # STEM-BLEED FIX: the next question's "N." got merged onto this line
        # (end of the previous sub-part/intro). Split it off so N starts a
        # fresh question instead of being swallowed by the previous one.
        if cur is not None and s:
            mm = Q_MID.search(s)
            if mm:
                nn = int(mm.group(1))
                pre = s[:mm.start()].rstrip()
                if (nn == cur_qnum + 1 or nn == cur_qnum + 2) and \
                   _mid_bleed_ok(pre):
                    prefix = pre.strip()
                    suffix = s[mm.start():].strip()
                    if prefix:
                        if cur_part is not None:
                            cur["parts"][cur_part].append(prefix)
                        else:
                            cur["intro"].append(prefix)
                    # reprocess the suffix as a fresh question start
                    s = suffix
                    m2 = Q_START.match(s)
                    if m2:
                        qnum = int(m2.group(1))
                        cur = qs.setdefault(qnum, {"intro": [], "parts": {}})
                        cur_part = None
                        cur_qnum = qnum
                        rest = (m2.group(2) or "").strip()
                        sm = re.match(r"^\(([a-f])\)\s*(.*)$", rest)
                        if sm:
                            cur_part = sm.group(1)
                            cur["parts"].setdefault(cur_part, [])
                            if sm.group(2).strip():
                                cur["parts"][cur_part].append(sm.group(2).strip())
                        elif rest:
                            cur["intro"].append(rest)
                        continue
        if cur is None:
            continue
        sm = re.match(r"^\(([a-f])\)\s*(.*)$", s)
        if sm:
            cur_part = sm.group(1)
            cur["parts"].setdefault(cur_part, [])
            if sm.group(2).strip():
                cur["parts"][cur_part].append(sm.group(2).strip())
        elif cur_part is not None:
            cur["parts"][cur_part].append(s)
        else:
            cur["intro"].append(s)
    return qs

# ---------------------------------------------------------------- raw: markscheme parsers (answer-only)
def body_after_instructions(text):
    lines = text.split("\n")
    idx = 0
    for i, ln in enumerate(lines):
        if re.match(r"^(Instructions to Examiners|Subject Details|Mark Allocation)", ln.strip()):
            idx = i
    return "\n".join(lines[idx:])

M_ROW_NUM = re.compile(r"^(\d{1,2})\.\s*$")                              # "1."
M_ROW = re.compile(r"^(\d{1,2})\.\s*\(([a-z])\)\s*(.*)$")                # "1. (a) ..."
M_ROW_SUB = re.compile(r"^\(([a-z])\)\s*(.*)$")                          # "(a) ..." (continuation)
P_ROW_NUM = re.compile(r"^(\d{1,2})\.?\s*([a-z])(?:\s+([ivxlc]+))?\s+(.*)$")  # "1. a ..." / "1 a i ..."
P_ROW_CONT = re.compile(r"^([a-z])\s+([ivxlc]+)(?:\s+(\d+))?\s*(.*)$")        # "a ii 1 ..." (roman required)

def parse_ms_answers(text, kind):
    """kind: 'math' -> rows keyed by qnum (subparts inline)
             'phys' -> rows keyed by (qnum, letter) (table rows)
    Returns rows: math -> {qnum: [content..]} ; phys -> {(qnum,letter): [(roman, content)]}"""
    body = strip_noise(body_after_instructions(text))
    rows = {}
    cur_key = None
    for ln in body.split("\n"):
        s = ln.strip()
        if not s or re.fullmatch(r"Section\s+[AB]", s) or re.fullmatch(r"Total.*", s):
            continue
        if kind == "math":
            m = M_ROW_NUM.match(s)
            if m:
                cur_key = int(m.group(1))
                rows.setdefault(cur_key, []).append("")
                continue
            m = M_ROW.match(s)
            if m:
                cur_key = int(m.group(1))
                rows.setdefault(cur_key, []).append(m.group(3).strip())
                continue
            m = M_ROW_SUB.match(s)
            if m and cur_key is not None:
                rows.setdefault(cur_key, []).append(m.group(2).strip())
                continue
        else:
            m = P_ROW_NUM.match(s)
            if m:
                qnum, letter, roman, rest = int(m.group(1)), m.group(2), m.group(3), m.group(4)
                cur_key = (qnum, letter)
                rows.setdefault(cur_key, []).append((roman, rest.strip()))
                continue
            m = P_ROW_CONT.match(s)
            if m and cur_key is not None and m.group(1) <= "h":
                rows[cur_key].append((m.group(2), m.group(4).strip()))
                continue
        if cur_key is not None and s:
            if kind == "math":
                rows[cur_key][-1] = (rows[cur_key][-1] + " " + s).strip()
            else:
                rows[cur_key][-1] = (rows[cur_key][-1][0], (rows[cur_key][-1][1] + " " + s).strip())
    return rows

def parse_answer_key(text):
    """MCQ key: {qnum: letter}."""
    d = {}
    for m in re.finditer(r"(?:^|[\s(])(\d{1,2})\s*\.\s*([A-D])\b", text):
        d[int(m.group(1))] = m.group(2)
    if len(d) < 5:
        for m in re.finditer(r"(?:^|[\s(])(\d{1,2})\s+([A-D])\b", text):
            d[int(m.group(1))] = m.group(2)
    return d

# ---------------------------------------------------------------- raw assembly
def raw_questions(subject, session_label, display, paper, tz, qpdf_text, ms_rows, ms_kind, is_mcq=False):
    qs = parse_qpdf(strip_noise(qpdf_text))
    out = []
    subj_code = "PHY" if subject == S_PHY else "MATH"
    subj_short = "Physics" if subject == S_PHY else "Math"
    id_base = f"{subj_code}-RAW-{session_label.replace('.','-')}{'-' + tz if tz else ''}-{paper.replace(' ', '')}"
    src = f"IB 真题 {display}{(' ' + tz) if tz else ''} {subj_short} HL {paper}"
    for qnum in sorted(qs.keys()):
        q = qs[qnum]
        intro = clean("\n".join(q["intro"]))
        parts = q["parts"]
        if is_mcq:
            letter = (ms_rows or {}).get(qnum)
            if not intro:
                continue
            out.append({
                "id": f"{id_base}-Q{qnum}",
                "subject": subject, "level": "HL",
                "topic": display, "subtopic": f"{paper}" + (f" {tz}" if tz else ""),
                "paper_type": paper,
                "question": intro,
                "answer": (letter or "?") + " (markscheme answer key)",
                "explanation": f"Original markscheme answer key: {letter}." if letter else "Answer not found in markscheme.",
                "source": src, "marks": None,
                "command_term": None,
                "knowledge_point_ids": [],
                "_raw": True,
            })
            continue
        # answer lookup
        def answer_for(letter=None):
            if ms_kind == "math":
                rows_ = ms_rows.get(qnum)
                return "\n".join(rows_) if rows_ else ""
            if letter:
                rows_ = ms_rows.get((qnum, letter))
                if rows_:
                    return "\n".join((f"({r}) " + c if r else c) for r, c in rows_)
            # fall back to first letter row of this qnum (physics)
            for (qn, lt), rows_ in ms_rows.items():
                if qn == qnum:
                    return "\n".join((f"({r}) " + c if r else c) for r, c in rows_)
            return ""
        if not parts:
            ans = answer_for()
            if not intro:
                continue
            out.append({
                "id": f"{id_base}-Q{qnum}",
                "subject": subject, "level": "HL",
                "topic": display, "subtopic": f"{paper}" + (f" {tz}" if tz else ""),
                "paper_type": paper,
                "question": intro,
                "answer": ans or "(answer in source markscheme)",
                "explanation": "(No examiner report in the original markscheme.)",
                "source": src, "marks": marks_in(ans) or None,
                "command_term": command_term(intro),
                "knowledge_point_ids": [],
                "_raw": True,
            })
            continue
        for letter in sorted(parts.keys()):
            ptext = " ".join(parts[letter])
            question_text = (intro + "\n\n" if intro else "") + f"({letter}) " + ptext
            ans = answer_for(letter)
            out.append({
                "id": f"{id_base}-Q{qnum}{letter}",
                "subject": subject, "level": "HL",
                "topic": display, "subtopic": f"{paper}" + (f" {tz}" if tz else ""),
                "paper_type": paper,
                "question": question_text,
                "answer": ans or "(answer in source markscheme)",
                "explanation": "(No examiner report in the original markscheme.)",
                "source": src, "marks": marks_in(ans) or None,
                "command_term": command_term(ptext),
                "knowledge_point_ids": [],
                "_raw": True,
            })
    return out

# ---------------------------------------------------------------- session walkers
MONTHS = {"may": "05", "november": "11", "nov": "11"}
MONTH_NAME = {"05": "May", "11": "November"}

def session_year_label(s):
    m = re.search(r"(20\d\d)[ .](05|11)", s)
    if m:
        return int(m.group(1)), f"{m.group(1)}.{m.group(2)}", f"{m.group(1)} {MONTH_NAME[m.group(2)]}"
    m = re.search(r"(20\d\d)\s+(May|November|Nov)", s, re.I)
    if m:
        mm = MONTHS[m.group(2).lower()]
        name = "November" if mm == "11" else "May"
        return int(m.group(1)), f"{m.group(1)}.{mm}", f"{m.group(1)} {name}"
    m = re.search(r"(20\d\d)", s)
    if m:
        return int(m.group(1)), m.group(1), m.group(1)
    return None, None, None

def phy_raw_walker():
    """Yield (session_label, display, paper, tz, qpath, mspath).
    Handles both old naming (Physics_paper_1__TZ1_HL.pdf) and 2025 naming
    (Physics_paper_1A_TZ1_HL.pdf, Physics_paper_2_TZ1_HL.pdf, no P3)."""
    items = []
    F = re.compile(r"^Physics_paper_(\d+[AB]?)_*(TZ\d)?_?HL(_markscheme)?\.pdf$")
    for d in sorted(os.listdir(PHY_RAW)):
        sdir = os.path.join(PHY_RAW, d)
        if not os.path.isdir(sdir):
            continue
        year, label, disp = session_year_label(d)
        if year is None or year < MIN_YEAR:
            continue
        files = [f for f in os.listdir(sdir) if not any(x in f for x in NON_EN)]
        parsed = []
        for f in files:
            m = F.match(f)
            if m:
                parsed.append((f, m.group(1), m.group(2), bool(m.group(3))))
        for paper_tok, tz in {(p, t) for (_, p, t, _) in parsed}:
            qfs = [f for f, p, t, isms in parsed if p == paper_tok and t == tz and not isms]
            mfs = [f for f, p, t, isms in parsed if p == paper_tok and t == tz and isms]
            for qf in qfs:
                stem = qf.replace(".pdf", "")
                mf = next((c for c in mfs if c.replace("_markscheme", "").replace(".pdf", "") == stem), None)
                items.append((label, disp, f"Paper {paper_tok}", tz, os.path.join(sdir, qf),
                              os.path.join(sdir, mf) if mf else None))
    return items

def math_raw_walker():
    """Yield (session_label, display, paper, tz, path, is_ms, opt)."""
    items = []
    for d in sorted(os.listdir(MATH_RAW)):
        sdir = os.path.join(MATH_RAW, d)
        if not os.path.isdir(sdir):
            continue
        m = re.match(r"^(20\d\d)\.(11|5|05)HL$", d)
        if m:
            year = int(m.group(1))
            if year < MIN_YEAR:
                continue
            mon = "05" if m.group(2) == "5" else "11"
            label, disp = f"{m.group(1)}.{mon}", f"{m.group(1)} {MONTH_NAME[mon]}"
            for f in sorted(os.listdir(sdir)):
                if any(x in f for x in NON_EN) or "applications_and_interpretation" in f:
                    continue
                mm = re.match(r"Mathematics_analysis_and_approaches_paper_(\d+)__(TZ\d_)?HL(_markscheme)?\.pdf$", f)
                if not mm:
                    continue
                pn = int(mm.group(1)); tz = (mm.group(2) or "").rstrip("_") or None
                is_ms = bool(mm.group(3))
                items.append((label, disp, f"Paper {pn}", tz, os.path.join(sdir, f), is_ms, None))
            continue
        # archive
        for d2 in sorted(os.listdir(sdir)):
            sdir2 = os.path.join(sdir, d2)
            if not os.path.isdir(sdir2):
                continue
            year, label, disp = session_year_label(d2)
            if year is None or year < MIN_YEAR:
                continue
            for root2, dirs2, files2 in os.walk(sdir2):
                if any(x in root2 for x in NON_EN):
                    continue
                for f in sorted(files2):
                    if any(x in f for x in NON_EN) or "applications_and_interpretation" in f:
                        continue
                    mm = re.match(r"Mathematics_(analysis_and_approaches_)?paper_(\d+)(?:_([A-Za-z_]+))?__(TZ\d_)?HL(_markscheme)?\.pdf$", f)
                    if not mm:
                        continue
                    pn = int(mm.group(2)); opt = mm.group(3); tz = (mm.group(4) or "").rstrip("_") or None
                    is_ms = bool(mm.group(5))
                    paper = f"Paper {pn}" + (f" {opt.replace('_', ' ')}" if opt else "")
                    items.append((label, disp, paper, tz, os.path.join(root2, f), is_ms, opt))
    return items

# ---------------------------------------------------------------- main
CKPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extract_checkpoint.json")

def load_ckpt():
    if os.path.exists(CKPT):
        try:
            with open(CKPT, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"done": [], "raw": [], "cls": []}

def save_ckpt(ckpt):
    tmp = CKPT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ckpt, f)
    os.replace(tmp, CKPT)

def main():
    ckpt = load_ckpt()
    done = set(ckpt.get("done", []))
    all_q = list(ckpt.get("raw", [])) + list(ckpt.get("cls", []))

    raw_phy = {}
    for label, disp, paper, tz, qp, msp in phy_raw_walker():
        key = (label, paper, tz)
        raw_phy.setdefault(key, {"q": None, "ms": None, "disp": disp})
        if msp:
            raw_phy[key]["ms"] = msp
        if qp:
            raw_phy[key]["q"] = qp
    print(f"[raw] physics: {len(raw_phy)} paper sessions (done {len([k for k in raw_phy if ('P|' + k[0] + '|' + k[1] + '|' + (k[2] or '')) in done])})", flush=True)
    for (label, paper, tz), v in sorted(raw_phy.items()):
        key = f"P|{label}|{paper}|{tz or ''}"
        if key in done:
            print(f"  [skip] {label} {paper} {tz or '—'}", flush=True)
            continue
        if not v["ms"]:
            print(f"  [WARN] {label} {paper} {tz or ''} missing markscheme", flush=True)
            continue
        qtext = pdf_text(v["q"])
        mtext = pdf_text(v["ms"])
        if not qtext:
            continue
        if paper.startswith("Paper 1"):
            keymap = parse_answer_key(mtext)
            if len(keymap) >= 5:
                recs = raw_questions(S_PHY, label, v["disp"], paper, tz, qtext, keymap, "mcq", is_mcq=True)
            else:
                rows = parse_ms_answers(mtext, "phys")
                recs = raw_questions(S_PHY, label, v["disp"], paper, tz, qtext, rows, "phys")
        else:
            rows = parse_ms_answers(mtext, "phys")
            recs = raw_questions(S_PHY, label, v["disp"], paper, tz, qtext, rows, "phys")
        print(f"  {label} {paper} {tz or '—'}: {len(recs)} questions", flush=True)
        ckpt["raw"].extend(recs)
        ckpt["done"].append(key)
        save_ckpt(ckpt)
        all_q.extend(recs)

    raw_math = {}
    for label, disp, paper, tz, path, is_ms, opt in math_raw_walker():
        key = (label, paper, tz)
        raw_math.setdefault(key, {"q": None, "ms": None, "disp": disp})
        if is_ms:
            raw_math[key]["ms"] = path
        else:
            raw_math[key]["q"] = path
    print(f"[raw] math: {len(raw_math)} paper sessions (done {len([k for k in raw_math if ('M|' + k[0] + '|' + k[1] + '|' + (k[2] or '')) in done])})", flush=True)
    for (label, paper, tz), v in sorted(raw_math.items()):
        key = f"M|{label}|{paper}|{tz or ''}"
        if key in done:
            print(f"  [skip] {label} {paper} {tz or '—'}", flush=True)
            continue
        if not v["ms"] or not v["q"]:
            print(f"  [WARN] {label} {paper} {tz or ''}: q={'y' if v['q'] else 'n'} ms={'y' if v['ms'] else 'n'}", flush=True)
            continue
        qtext = pdf_text(v["q"])
        mtext = pdf_text(v["ms"])
        if not qtext or not mtext:
            continue
        rows = parse_ms_answers(mtext, "math")
        recs = raw_questions(S_MATH, label, v["disp"], paper, tz, qtext, rows, "math")
        print(f"  {label} {paper} {tz or '—'}: {len(recs)} questions", flush=True)
        ckpt["raw"].extend(recs)
        ckpt["done"].append(key)
        save_ckpt(ckpt)
        all_q.extend(recs)

    raw_qs = [q for q in all_q if q.get("_raw")]
    cls_qs = [q for q in all_q if q.get("_cls")]

    print("[cls] physics topics + options...", flush=True)
    for folder in sorted(os.listdir(PHY_CLS), key=lambda x: (0, int(re.sub(r"\D", "", x) or 0)) if x.startswith("Topic") else (1, x)):
        if not os.path.isdir(os.path.join(PHY_CLS, folder)):
            continue
        for paper in ("HL-paper1", "HL-paper2", "HL-paper3"):
            key = f"C|{S_PHY}|{folder}|{paper}"
            if key in done:
                print(f"  [skip] {folder} {paper}", flush=True)
                continue
            recs = classified_blocks(S_PHY, folder, paper, PHY_KP)
            if recs:
                print(f"  {folder} {paper}: {len(recs)}", flush=True)
            ckpt["cls"].extend(recs)
            ckpt["done"].append(key)
            save_ckpt(ckpt)
            cls_qs.extend(recs)

    print("[cls] math topics...", flush=True)
    for folder in sorted(os.listdir(MATH_CLS), key=lambda x: (0, int(re.sub(r"\D", "", x) or 0)) if x.startswith("Topic") else (1, x)):
        if not os.path.isdir(os.path.join(MATH_CLS, folder)):
            continue
        for paper in ("HL-paper1", "HL-paper2", "HL-paper3"):
            key = f"C|{S_MATH}|{folder}|{paper}"
            if key in done:
                print(f"  [skip] {folder} {paper}", flush=True)
                continue
            recs = classified_blocks(S_MATH, folder, paper, MATH_KP)
            if recs:
                print(f"  {folder} {paper}: {len(recs)}", flush=True)
            ckpt["cls"].extend(recs)
            ckpt["done"].append(key)
            save_ckpt(ckpt)
            cls_qs.extend(recs)

    # ---- dedup: classified dupes of raw are dropped (keep 真题) ----
    raw_tok = [(norm_tokens(q["question"]), q["subject"]) for q in raw_qs]
    print(f"[dedup] classified={len(cls_qs)} raw={len(raw_qs)}", flush=True)
    kept = []
    dropped = 0
    for q in cls_qs:
        ct = norm_tokens(q["question"])
        head = set(list(ct.elements())[:10])
        dup = False
        for rt, rsub in raw_tok:
            if rsub != q["subject"]:
                continue
            if len(head & set(rt.elements())) < 4:
                continue
            inter = sum((ct & rt).values())
            union = sum((ct | rt).values())
            if union and inter / union >= 0.45:
                dup = True
                break
        if dup:
            dropped += 1
        else:
            kept.append(q)
    print(f"[dedup] classified kept={len(kept)} dropped={dropped}", flush=True)

    final = []
    seen = set()
    for q in raw_qs + kept:
        if q["id"] in seen:
            continue
        seen.add(q["id"])
        final.append({k: v for k, v in q.items() if not k.startswith("_")})
    final.sort(key=lambda q: (q["subject"], q.get("source") or "", q["id"]))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=1)
    by_subj = {}
    for q in final:
        by_subj[q["subject"]] = by_subj.get(q["subject"], 0) + 1
    print(f"[done] total={len(final)} -> {OUT}")
    for s, n in sorted(by_subj.items()):
        print(f"  {s}: {n}")
    if os.path.exists(CKPT):
        os.remove(CKPT)
        print("[done] checkpoint removed")

if __name__ == "__main__":
    main()
