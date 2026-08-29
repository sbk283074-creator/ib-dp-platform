#!/usr/bin/env python3
# run_corpus.py — plan + (optionally) run the full screenshot extraction
# across all three subjects: topic exercises AND past papers (last ~10 years).
#
# Hard rules (Lucas's instructions), enforced here:
#   * A question is number-led (1. 2. 3.); a letter-led line is a SUBPART, never
#     a separate question. The engine (screenshot_questions.py) already enforces
#     this; we just feed it the right --profile per file family.
#   * Different files use different detection methods -> PROFILES:
#       math_past      : Math AA HL past papers (1 col, number-led Qs)
#       physics_past   : Physics HL past papers (1 col, number-led Qs)
#       cs_past        : CS HL past papers (1 col, number-led Qs)
#       line_pref      : line-separated banks — Physics HL Topic sets AND Math
#                        AA HL 分章练习 question banks (no leading numbers)
#   * One DB question per question area (1:1) -> handled by import_shots.mjs
#     using the stable manifest id; this script only builds the job list.
#
# Usage:
#   python3 run_corpus.py --plan            # print scope, do NOT extract
#   python3 run_corpus.py --run [--limit N] [--subject MATH|PHY|CS|ALL]
#   python3 run_corpus.py --run --resume    # skip prefixes already in manifest
#
# All paths are relative to the workspace root passed via --root (default: cwd).

import os, re, sys, json, argparse, subprocess

ROOT = os.getcwd()  # workspace root: holds the source PDFs
PLAT = 'ib-dp-platform'  # platform code lives here
OUT_DIR = os.path.join(ROOT, PLAT, 'backend', 'public', 'figures', 'shots')
MANIFEST = os.path.join(ROOT, PLAT, 'backend', 'ocr', 'screenshot_manifest.jsonl')
ENGINE = os.path.join(ROOT, PLAT, 'backend', 'ocr', 'screenshot_questions.py')
FAILED_LOG = os.path.join(ROOT, PLAT, 'backend', 'ocr', 'corpus_failed.log')

SUBJ_CODE = {'Math AA HL': 'MATH', 'Physics': 'PHY', 'Computer Science': 'CS'}

# year window for "last 10 years" of past papers (current: 2026) -> keep 2015..2025
PAST_MIN_YEAR = 2015

def find_pdfs(folder):
    out = []
    for dp, _, fnames in os.walk(folder):
        for f in fnames:
            if f.lower().endswith('.pdf'):
                out.append(os.path.join(dp, f))
    return out

YEAR_RE = re.compile(r'(19|20)(\d{2})')
MONTH_TXT = {'may': '5', 'm': '5', 'november': '11', 'nov': '11', 'n': '11'}

def extract_year_month(text):
    """Return (year:int, month:'5'|'11'|None) from a path/filename chunk."""
    ym = None
    m = re.search(r'(19|20)(\d{2})', text)
    year = int(m.group(0)) if m else None
    month = None
    # explicit .5 / .11 / .05 style
    mm = re.search(r'\.(\d{1,2})(?:\.|\b|HL|$)', text)
    if mm and mm.group(1) in ('5', '05', '11', '11'):
        month = '11' if mm.group(1) in ('11',) else '5'
    if month is None:
        low = text.lower()
        if 'nov' in low: month = '11'
        elif 'may' in low: month = '5'
    return year, month

PAPER_RE = re.compile(r'paper[_\s-]*([123])([ab])?', re.I)
TZ_RE = re.compile(r'TZ\s*([12])', re.I)

def extract_paper_tz(fname):
    paper = None
    p = PAPER_RE.search(fname)
    if p:
        paper = 'P' + p.group(1).upper() + (p.group(2).upper() if p.group(2) else '')
    tz = None
    t = TZ_RE.search(fname)
    if t: tz = 'TZ' + t.group(1)
    return paper, tz

MS_TOKENS = ['markscheme', 'mark scheme', 'ms', '_ms', 'answer']

def is_markscheme(fname):
    low = fname.lower()
    return any(tok in low for tok in MS_TOKENS)

def _norm_key(stem):
    """Normalize a filename stem to a comparable key (strip paper token + markscheme token)."""
    k = re.sub(r'paper[_\s]*[123][ab]?', '', stem, flags=re.I)
    k = re.sub(r'_markscheme', '', k, flags=re.I).strip(' _-')
    return k

def pair_markscheme(paper_pdf, all_pdfs):
    """Find the markscheme companion for a paper pdf (by same dir + overlapping stem)."""
    d = os.path.dirname(paper_pdf)
    stem = os.path.splitext(os.path.basename(paper_pdf))[0]
    base = _norm_key(stem)
    best = None
    for f in all_pdfs:
        if os.path.dirname(f) != d: continue
        if not is_markscheme(os.path.basename(f)): continue
        fb = _norm_key(os.path.splitext(os.path.basename(f))[0])
        if fb == base or base in fb or fb in base:
            best = f; break
    return best

def build_prefix(code, year, month, paper, tz, disamb=None):
    y = str(year) if year else 'XXXX'
    mo = month or 'x'
    pf = paper or 'P?'
    base = f"{code}-{y}.{mo}-{pf}{('-'+tz) if tz else ''}"
    # Topic PDFs (no leading year) all share the same base prefix; without
    # disambiguation 30+ real topic papers would collide on disk and
    # overwrite each other. The source subfolder (e.g. "Topic 3", "Option A")
    # -- or the file stem when the topic folder is flat -- keeps each paper's
    # crops and manifest ids unique.
    if year is None and disamb:
        return f"{base}-{disamb}"
    return base

# ---- source registry -------------------------------------------------------
# Each entry: (root_rel, subject, base_profile, kind)
# kind: 'past' (apply year filter) | 'topic' (include all)
# root_rel may be a folder (walked) or a single .pdf file.
SOURCES = [
    ("Computer Science-HL-Past Papers&Mark Schemes(1999.05~2025.05)", 'Computer Science', 'cs_past', 'past'),
    ("IB 数学 AA  HL 历年真题", 'Math AA HL', 'math_past', 'past'),
    ("Physics-HL-Past Papers&Mark Schemes(1999.05~2025.11)", 'Physics', 'physics_past', 'past'),
    ("Physics-HL-Topic questions", 'Physics', 'line_pref', 'topic'),
    ("IB数学AA  HL 分章练习", 'Math AA HL', 'line_pref', 'topic'),
]

def plan_jobs():
    jobs = []
    for root_rel, subject, profile, kind in SOURCES:
        base = os.path.join(ROOT, root_rel)
        if os.path.isfile(base):
            pdfs = [base]
        elif os.path.isdir(base):
            pdfs = find_pdfs(base)
        else:
            print(f"[warn] missing source: {root_rel}", file=sys.stderr); continue
        # path relative to the SOURCE ROOT (so the date-range label in the
        # top folder name, e.g. "...1999.05~2025.05", is NOT mistaken for a year)
        rel_src_all = [os.path.relpath(p, base) for p in pdfs]
        # split markschemes out
        papers = [(p, r) for p, r in zip(pdfs, rel_src_all) if not is_markscheme(os.path.basename(p))]
        for p, rel_src in papers:
            rel = os.path.relpath(p, ROOT)
            year, month = extract_year_month(rel_src)
            paper, tz = extract_paper_tz(os.path.basename(p))
            if kind == 'past':
                if year is None or year < PAST_MIN_YEAR:
                    continue
            # Topic PDFs without a year all collapse to the same base prefix
            # (e.g. PHY-XXXX.x-P1); disambiguate with the source subfolder
            # (Topic 3, Option A, ...) or the file stem when the topic folder
            # is flat, so each real topic paper keeps its own crops.
            disamb = None
            if kind == 'topic' and year is None:
                sub = os.path.dirname(rel_src)
                token = os.path.basename(sub) if sub else os.path.splitext(os.path.basename(p))[0]
                disamb = re.sub(r'[^A-Za-z0-9_-]+', '-', token).strip('-') or None
            ms = pair_markscheme(p, pdfs)
            code = SUBJ_CODE[subject]
            prefix = build_prefix(code, year, month, paper, tz, disamb=disamb)
            jobs.append({
                'subject': subject, 'profile': profile, 'kind': kind,
                'pdf': rel, 'markscheme': os.path.relpath(ms, ROOT) if ms else None,
                'prefix': prefix, 'year': year, 'month': month,
                'paper': paper, 'tz': tz
            })
    return jobs

def print_plan(jobs):
    by_subj = {}
    for j in jobs:
        by_subj.setdefault(j['subject'], {'past': 0, 'topic': 0})
        by_subj[j['subject']][j['kind']] += 1
    print(f"\n=== CORPUS PLAN ({len(jobs)} papers to screenshot) ===")
    for s, c in by_subj.items():
        print(f"  {s:16s} past={c['past']:4d}  topic={c['topic']:4d}")
    # profile tally
    prof = {}
    for j in jobs: prof[j['profile']] = prof.get(j['profile'], 0) + 1
    print("  by profile:", prof)
    ms = sum(1 for j in jobs if j['markscheme'])
    print(f"  with markscheme pairing: {ms}")
    # year distribution (past only)
    yrs = {}
    for j in jobs:
        if j['kind'] == 'past' and j['year']:
            yrs[j['year']] = yrs.get(j['year'], 0) + 1
    if yrs:
        print("  past-paper years:", dict(sorted(yrs.items())))

def run_jobs(jobs, limit=None, resume=False):
    done = set()
    if resume and os.path.exists(MANIFEST):
        with open(MANIFEST) as fh:
            for line in fh:
                try: rec = json.loads(line)
                except: continue
                done.add(rec.get('prefix'))
    os.makedirs(OUT_DIR, exist_ok=True)
    failed = FAILED_LOG
    ran = 0
    fails = 0
    for j in jobs:
        if limit and ran >= limit: break
        if resume and j['prefix'] in done:
            continue
        cmd = [sys.executable, os.path.join(ROOT, ENGINE),
               j['pdf'], '--profile', j['profile'],
               '--prefix', j['prefix'],
               '--out', OUT_DIR, '--dpi', '200']
        if j['markscheme']:
            cmd += ['--markscheme', j['markscheme']]
        print(f"[run] {j['prefix']}  <- {os.path.basename(j['pdf'])}"
              + (f"  +ms" if j['markscheme'] else ""), flush=True)
        try:
            r = subprocess.run(cmd, cwd=ROOT, check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                               timeout=600)
            if r.returncode != 0:
                msg = (r.stderr or b'').decode('utf-8', 'replace').strip().splitlines()[-3:]
                with open(failed, 'a') as lf:
                    lf.write(f"{j['prefix']}\t{j['pdf']}\t{'; '.join(msg)}\n")
                print(f"  ! failed (rc={r.returncode}): {'; '.join(msg)}", file=sys.stderr)
                fails += 1
        except subprocess.TimeoutExpired:
            with open(failed, 'a') as lf:
                lf.write(f"{j['prefix']}\t{j['pdf']}\tTIMEOUT (240s)\n")
            print(f"  ! timeout: {j['prefix']}", file=sys.stderr)
            fails += 1
        except Exception as e:
            print(f"  ! error: {e}", file=sys.stderr)
            fails += 1
        done.add(j['prefix'])
        ran += 1
    print(f"\n[done] ran {ran} papers ({fails} failed) -> see {failed} if any")
    print(f"[done] manifest: {MANIFEST}")

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--plan', action='store_true')
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--resume', action='store_true')
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--subject', default='ALL', choices=['ALL','MATH','PHY','CS'])
    args = ap.parse_args()
    ROOT = os.path.abspath(args.root)
    jobs = plan_jobs()
    if args.subject != 'ALL':
        code = {'MATH':'MATH','PHY':'PHY','CS':'CS'}[args.subject]
        jobs = [j for j in jobs if SUBJ_CODE[j['subject']] == code]
    if args.plan or not args.run:
        print_plan(jobs)
    if args.run:
        run_jobs(jobs, limit=args.limit, resume=args.resume)
