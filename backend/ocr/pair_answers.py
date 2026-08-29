#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pair questions in a book JSON with answers from a companion answer PDF.

Haese WORKED SOLUTIONS layout (the only books with answer_path):
  * every page carries a running header like
      '66 Chapter 2 (Sets and Venn diagrams) Review set 2A'
    or 'Chapter 2 (Sets and Venn diagrams) Review set 2B 67'
    → the trailing label names the exercise ('Review set 2A', 'Exercise 1B').
  * answers within a review set start with a BARE question number at line
    start ('11 Let R represent the meals which contain rice and'), sometimes
    followed by a sub-part letter ('2 a SandT are disjoint, ...').
  * numeric results also start lines ('72 students missed school...'), so a
    naive 'any number at line start' split is unsafe. We therefore locate
    each EXPECTED question number sequentially (search for Qk only after
    Q(k-1) was found), which reliably skips result-number false positives.

Matching key: (normalized review-set label from the textbook question's
topic, question number). No page-number fallback — the old fallback silently
paired answers from other questions.

Run: python pair_answers.py <book_json_path>
"""
import sys, os, re, json, logging, warnings
warnings.filterwarnings('ignore')
logging.getLogger('pdfminer').setLevel(logging.CRITICAL)
import pypdfium2 as pdfium

from booklib import pdfium_lines
from booklib import _review_label

PLACEHOLDER = ('[answer pending', '__ai_fill__')


def norm_label(s):
    """'Review set 2A' / 'REVIEW SET 2 A' -> 'reviewset2a'."""
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def parse_solution_pages(answer_pdf):
    """Return ordered [(page_no, label_norm, label_raw, body_lines), ...].

    label comes from the running header; pages whose header can't be parsed
    inherit the previous page's label (continuation pages).
    """
    pdf = pdfium.PdfDocument(answer_pdf)
    out = []
    prev_label = None
    hdr_chapter = re.compile(r'Chapter\s+\d+\s*\([^)]*\)', re.I)
    hdr_line = re.compile(r'^(?:\d{1,4}\s+)?Chapter\s+\d+\s*\(', re.I)
    for i in range(len(pdf)):
        page = pdf[i]
        lines = [t.strip() for _, t, _ in pdfium_lines(page)]
        lines = [l for l in lines if l]
        if not lines:
            out.append((i + 1, prev_label, prev_label, []))
            continue
        label = None
        # chapter TITLE page ('Chapter 8' as its own line): content belongs to
        # a new chapter, so never inherit the previous page's label — use a
        # sentinel that will not match any review-set label.
        m_ch = re.match(r'^Chapter\s+(\d+)\s*$', lines[0].strip(), re.I)
        if m_ch:
            label = f'chapter{m_ch.group(1)}'
        # header lives in the first ~2 lines
        head_txt = ' '.join(lines[:2])
        m = hdr_chapter.search(head_txt)
        if m:
            rest = head_txt[m.end():].strip()
            rest = re.sub(r'\b\d{1,4}\b', ' ', rest)      # strip page numbers
            rest = re.sub(r'[^A-Za-z0-9\s]', ' ', rest)
            words = rest.split()
            if words:
                # label = up to first 3 words (e.g. 'Review set 2A',
                # 'Exercise 1B', 'Activity 2')
                label = ' '.join(words[:3])
        if label is None:
            label = prev_label
        # body: drop running-header lines and standalone page numbers
        body = [l for l in lines
                if not hdr_line.match(l)
                and not re.match(r'^\d{1,4}$', l)]
        out.append((i + 1, norm_label(label), label, body))
        prev_label = label
    pdf.close()
    return out


def split_answers_by_qnums(lines, qnums):
    """Sequentially locate each expected qnum at line start.

    lines: list of str. qnums: list of int (question numbers expected in this
    exercise). Returns {qnum: answer_text}.
    """
    qnums = sorted(set(int(q) for q in qnums))
    res = {}
    # precompute line-start number for every line
    starts = []
    for l in lines:
        m = re.match(r'^(\d{1,3})[.):]?\s+\S', l)
        starts.append(int(m.group(1)) if m else None)
    start_idx = 0
    for k, qn in enumerate(qnums):
        found = None
        for j in range(start_idx, len(lines)):
            if starts[j] == qn:
                found = j
                break
        if found is None:
            continue
        # answer ends where any LATER expected qnum starts
        end = len(lines)
        for qn2 in qnums[k + 1:]:
            for j in range(found + 1, len(lines)):
                if starts[j] == qn2:
                    end = min(end, j)
                    break
        res[qn] = '\n'.join(lines[found:end]).strip()
        start_idx = found + 1
    return res


def pair_book_json(json_path):
    data = json.load(open(json_path, encoding='utf-8'))
    book = data['book']
    answer_pdf = None
    # the answer_source is the original path to the companion answer file
    # search the BOOKS registry for the matching id
    import extract_books
    reg = next((b for b in extract_books.BOOKS if b['id'] == book['id']), None)
    if reg and reg.get('answer_path'):
        answer_pdf = reg['answer_path']
    if not answer_pdf or not os.path.exists(answer_pdf):
        print(f"  no answer file for {book['id']}, skipping pairing")
        return False
    print(f"  pairing with: {answer_pdf}")

    pages = parse_solution_pages(answer_pdf)

    # ---- group solution lines by normalized label -------------------------
    by_label = {}   # label_norm -> ordered list of (page_no, label_raw, lines)
    for pno, ln, lraw, body in pages:
        if ln:
            by_label.setdefault(ln, []).append((pno, lraw, body))

    # ---- collect expected questions per label ----------------------------
    qs_by_label = {}
    for q in data['questions']:
        m = re.search(r'review\s+set\s+(\d+\s*[A-B0-9]?)\b', q.get('topic', '') or '',
                      re.I)
        if not m:
            continue
        label = norm_label(_review_label(m.group(1)))
        qs_by_label.setdefault(label, []).append(q)

    # ---- split answers and assign ----------------------------------------
    matched = 0
    for label, qs in qs_by_label.items():
        if label not in by_label:
            continue
        qnums = []
        for q in qs:
            m = re.search(r'p(\d+)\s+Q(\d+)', q.get('source', ''))
            if m:
                qnums.append(int(m.group(2)))
        if not qnums:
            continue
        lines = []
        label_raw = label
        for pno, lraw, body in by_label[label]:
            lines.extend(body)
            if lraw:
                label_raw = lraw
        ans = split_answers_by_qnums(lines, qnums)
        # Fallback for questions the line-based split missed: solutions pages
        # are sometimes two-column and fragmented, burying the question number
        # mid-line. Search the raw text stream sequentially — ONLY questions
        # still pending, and ONLY matches followed by an uppercase letter or
        # '(' (avoids '12 km'-style numeric results).
        pend = [q for q in qs
                if not q.get('answer') or
                str(q.get('answer', '')).lower().startswith(PLACEHOLDER)]
        if pend:
            stream = '\n'.join(lines)

            def find_qnum(qn, start):
                pat = re.compile(rf'(?<![A-Za-z0-9./]){qn}[.):]?\s+(?=[A-Z(])')
                m = pat.search(stream, start)
                return m

            all_qnums = sorted(set(qnums))
            pend_qnums = sorted(set(int(re.search(r'p(\d+)\s+Q(\d+)',
                                                  q['source']).group(2))
                                    for q in pend
                                    if re.search(r'p(\d+)\s+Q(\d+)', q.get('source', ''))))
            pos = 0
            for qn in pend_qnums:
                m = find_qnum(qn, pos)
                if not m:
                    continue
                # extent: first match of any LATER question number
                end = len(stream)
                for qn2 in (x for x in all_qnums if x > qn):
                    m2 = find_qnum(qn2, m.end())
                    if m2:
                        end = min(end, m.end() + m2.start())
                        break
                text = stream[m.start():end].strip()
                if len(text) > 10:
                    ans[qn] = text
                pos = m.end()
        for q in qs:
            m = re.search(r'p(\d+)\s+Q(\d+)', q.get('source', ''))
            if not m:
                continue
            qn = int(m.group(2))
            if qn in ans and len(ans[qn]) > 10:
                q['answer'] = ans[qn]
                q['explanation'] = (
                    f'Worked solution from {os.path.basename(answer_pdf)}, '
                    f'{label_raw}.')
                matched += 1

    json.dump(data, open(json_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    paired = sum(1 for q in data['questions']
                 if q.get('answer') and
                 not str(q['answer']).lower().startswith(PLACEHOLDER))
    print(f"  paired {paired}/{len(data['questions'])} questions "
          f"({matched} this run)")
    return paired > 0


def main():
    if not sys.argv[1:]:
        print('Usage: pair_answers.py <book_json_path>')
        return
    pair_book_json(sys.argv[1])


if __name__ == '__main__':
    main()
