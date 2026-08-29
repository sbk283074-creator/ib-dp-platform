#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Merge IB past-paper sub-questions (id ...Q{n}{a/b/c/...}) back into single
questions, per user request: 同一大题的 (a)(b)(c) 小题要合并为一道题。

For each group:
  * question  = head (intro + stem) + all sub-part bodies (a)(b)(c)...
  * answer    = concat of DISTINCT per-subpart answers, prefixed (a)/(b)/(c)
  * marks     = [Maximum mark: N] parsed from the stem (fallback: max marks)
  * question_image = vertical concat of each sub-part's question crop
  * answer_image   = vertical concat of each sub-part's answer crop (if any)

Usage:
  python merge_subquestions.py --dry-run
  python merge_subquestions.py --apply
"""
import os, re, sqlite3, sys, argparse
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.abspath(os.path.join(HERE, '..'))
DB = os.path.join(BACKEND, 'data', 'app.db')
FIG_DIR = os.path.join(BACKEND, 'public', 'figures')

# id like ...Q123a  (trailing single letter after a question number)
SPLIT_RE = re.compile(r'^(.*Q\d+)([a-z])$')
MAXMARK_RE = re.compile(r'\[Maximum\s+mark:\s*(\d+)\]', re.I)
SUBPART_RE = re.compile(r'^\s*\(?([a-e]|i{1,3}|iv|v)\)?[.)]\s', re.M)


def fig_path(rel):
    if not rel:
        return None
    name = rel.split('/')[-1]
    p = os.path.join(FIG_DIR, name)
    return p if os.path.exists(p) else None


def vconcat(paths, out_path):
    """Vertically stack images (resize to max width), save JPEG."""
    imgs = []
    for p in paths:
        try:
            im = Image.open(p).convert('RGB')
            imgs.append(im)
        except Exception as e:
            print(f'    [warn] cannot open {p}: {e}', file=sys.stderr)
    if not imgs:
        return False
    w = max(im.width for im in imgs)
    total_h = sum(im.height for im in imgs)
    canvas = Image.new('RGB', (w, total_h), 'white')
    y = 0
    for im in imgs:
        x = 0
        if im.width < w:
            x = (w - im.width) // 2
        canvas.paste(im, (x, y))
        y += im.height
    canvas.save(out_path, 'JPEG', quality=88)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='apply changes (default: dry-run)')
    args = ap.parse_args()

    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = [dict(r) for r in db.execute("SELECT * FROM questions WHERE source LIKE 'IB 真题%'").fetchall()]

    groups = {}
    for r in rows:
        m = SPLIT_RE.match(r['id'])
        if m:
            groups.setdefault(m.group(1), []).append(r)
    multi = {k: sorted(v, key=lambda x: x['id']) for k, v in groups.items() if len(v) > 1}
    print(f'拆分组: {len(multi)}  子题: {sum(len(v) for v in multi.values())}', flush=True)

    merged = []       # (base_id, dict)
    delete_ids = []
    for base, subs in multi.items():
        # question: head (from first sub, up to first sub-part) + all bodies
        first_q = subs[0]['question'] or ''
        m = SUBPART_RE.search(first_q)
        head = first_q[:m.start()] if m else first_q
        bodies = []
        for s in subs:
            q = s['question'] or ''
            mm = SUBPART_RE.search(q)
            body = q[mm.start():] if mm else q[len(head):]
            bodies.append(body.strip())
        question = (head.rstrip() + '\n' + '\n'.join(bodies)).strip()

        # marks from [Maximum mark: N] in head; fallback max of marks
        mm = MAXMARK_RE.search(head)
        marks = int(mm.group(1)) if mm else max((s['marks'] for s in subs if s['marks']), default=None)

        # answer: distinct per-sub answers, prefixed with sub label
        labels = [SPLIT_RE.match(s['id']).group(2) for s in subs]
        seen = set()
        parts = []
        for lab, s in zip(labels, subs):
            a = (s['answer'] or '').strip()
            if not a or a in seen:
                continue
            seen.add(a)
            parts.append(f'({lab}) {a}' if not re.match(r'^\(?[a-e]\)', a) else a)
        answer = '\n\n'.join(parts) if parts else (subs[0]['answer'] or '')

        explanation = subs[0]['explanation'] or None

        # images: concat per sub
        new_qimg = None
        if all(s['question_image'] for s in subs):
            new_qimg = f'/figures/pmq-{base.split("/")[-1].replace(" ", "_")}-merged.jpg'
            out = os.path.join(FIG_DIR, os.path.basename(new_qimg))
            paths = [fig_path(s['question_image']) for s in subs]
            if all(paths):
                if args.apply:
                    vconcat(paths, out)
                else:
                    print(f'  would concat qimg: {os.path.basename(new_qimg)} ({len(paths)} imgs)', flush=True)
        new_ansimg = None
        if all(s.get('answer_image') for s in subs):
            new_ansimg = f'/figures/pmq-{base.split("/")[-1].replace(" ", "_")}-merged-ans.jpg'
            out = os.path.join(FIG_DIR, os.path.basename(new_ansimg))
            paths = [fig_path(s['answer_image']) for s in subs]
            if all(paths):
                if args.apply:
                    vconcat(paths, out)
                else:
                    print(f'  would concat ansimg: {os.path.basename(new_ansimg)} ({len(paths)} imgs)', flush=True)

        first = subs[0]
        merged.append((base, {
            'subject': first['subject'], 'level': first['level'], 'topic': first['topic'],
            'subtopic': first['subtopic'], 'paper_type': first['paper_type'],
            'command_term': first['command_term'], 'marks': marks,
            'difficulty': first['difficulty'], 'question': question,
            'figure': first['figure'], 'answer': answer, 'explanation': explanation,
            'source': first['source'], 'tags': first['tags'], 'authored_by': first['authored_by'],
            'created_at': first['created_at'], 'knowledge_point_ids': first['knowledge_point_ids'],
            'definition_basis': first['definition_basis'], 'question_image': new_qimg,
            'answer_image': new_ansimg, 'answer_figure': first['answer_figure'],
            'book_id': first['book_id'], 'book_section': first['book_section'],
            'book_page': first['book_page'], 'in_book_order': first['in_book_order'],
            'source_type': first['source_type'],
        }))
        delete_ids.extend(s['id'] for s in subs)

    print(f'合并后大题: {len(merged)}  删除子题: {len(delete_ids)}', flush=True)

    if not args.apply:
        print('DRY-RUN OK — 未写入。加 --apply 执行。', flush=True)
        db.close()
        return

    tx = sqlite3.connect(DB)
    try:
        cur = tx.cursor()
        # delete old sub-questions (and any stray base rows that were duplicates)
        cur.execute(
            f"DELETE FROM questions WHERE id IN ({','.join('?' * len(delete_ids))})",
            delete_ids)
        cols = ['id','subject','level','topic','subtopic','paper_type','command_term',
                'marks','difficulty','question','figure','answer','explanation','source',
                'tags','authored_by','created_at','knowledge_point_ids','definition_basis',
                'answer_figure','question_image','answer_image','book_id','book_section',
                'book_page','in_book_order','source_type']
        for base, q in merged:
            vals = [q[c] for c in cols[1:]]
            cur.execute(
                f"INSERT OR REPLACE INTO questions ({','.join(cols)}) VALUES "
                f"({','.join(['?'] * len(cols))})", [base] + vals)
        tx.commit()
        print(f'APPLIED: merged {len(merged)} questions, deleted {len(delete_ids)} sub-questions', flush=True)
    except Exception as e:
        tx.rollback()
        print(f'ERROR: {e}', file=sys.stderr)
        raise
    finally:
        tx.close()
    db.close()


if __name__ == '__main__':
    main()
