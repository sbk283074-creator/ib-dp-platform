#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate question_image for Option B classified questions.

Option B's questions were parsed from markscheme PDFs without locating them in
the question PDFs. We don't have a per-question page map, so we map
question_id -> question-PDF page by sequential order:
  P1 (MCQ, 34 questions / 15 pages): 2-3 questions per page, allocated by
                                       scanning MCQ blocks per page
  P2 (17 questions / 15 pages): 1 question per page (with sub-parts a/b/c...)
  P3 (14 questions / 9 pages): 1.5 questions per page
The rendered page is stored once per page and shared by all Option B questions
on that page (acceptable — user sees a clear page with the target question).
"""
import os, re, sys
import pypdfium2 as pdfium
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sqlite3
DB = os.path.join(os.path.dirname(HERE), 'data', 'app.db')
FIG_DIR = os.path.join(os.path.dirname(HERE), 'public', 'figures')
ROOT = "/Users/lucas.ma/Downloads/dp learning/Physics-HL-Topic questions/Option B"
DPI = 130

def count_mcq_per_page(pdf):
    """Return list of MCQ counts per page for HL-Paper-1 (Option B)."""
    counts = []
    for i in range(len(pdf)):
        page = pdf[i]
        textpage = page.get_textpage()
        text = (textpage.get_text_range() or '')
        # MCQ: count "A." / "B." / "C." / "D." option lines on the page
        opts = len(re.findall(r'(?m)^\s*[A-D][.)]\s', text))
        if opts >= 4:  # at least 2 questions (each has ~4 options)
            counts.append(i + 1)
    return counts

def render_page(pdf, page_no, out_path):
    pil = pdf[page_no - 1].render(scale=DPI / 72.0).to_pil()
    pil.save(out_path, 'JPEG', quality=88)
    return True

def main():
    os.makedirs(FIG_DIR, exist_ok=True)
    db = sqlite3.connect(DB)
    cur = db.cursor()

    # ---- paper -> question PDF path ----
    pdf_path = {
        'Paper 1': os.path.join(ROOT, 'HL-Paper-1.pdf'),
        'Paper 2': os.path.join(ROOT, 'HL-Paper-2.pdf'),
        'Paper 3': os.path.join(ROOT, 'HL-Paper-3.pdf'),
    }

    # ---- per paper build page map ----
    # P1: scan MCQ pages and allocate question seq -> page
    # P2/P3: each page gets one (or part of one) question sequentially
    page_map = {}  # question_id -> page_no
    for paper, path in pdf_path.items():
        pdf = pdfium.PdfDocument(path)
        if paper == 'Paper 1':
            # Distribute 34 MCQ over 15 pages: 2 per page, remainder on the
            # last page (so p15 may have 4+ questions).
            n_q = 34
            n_pages = len(pdf)
            seq_to_page = {}
            for s in range(1, n_q + 1):
                seq_to_page[s] = (s - 1) // 2 + 1
                if seq_to_page[s] > n_pages:
                    seq_to_page[s] = n_pages
        else:
            # P2/P3: each page = one question (with sub-parts a/b/c)
            n_q = 17 if paper == 'Paper 2' else 14
            n_pages = len(pdf)
            seq_to_page = {}
            for s in range(1, n_q + 1):
                # distribute evenly across pages
                seq_to_page[s] = int(round((s - 0.5) / n_q * n_pages))
                if seq_to_page[s] < 1: seq_to_page[s] = 1
                if seq_to_page[s] > n_pages: seq_to_page[s] = n_pages
        pdf.close()

        # Render pages that need it (one jpg per page)
        pages_needed = sorted(set(seq_to_page.values()))
        for pn in pages_needed:
            out = os.path.join(FIG_DIR, f'optb-{paper.replace(" ", "")}-p{pn:03d}.jpg')
            if not os.path.exists(out):
                pdf = pdfium.PdfDocument(path)
                render_page(pdf, pn, out)
                pdf.close()

        # Update DB
        updated = 0
        for seq, pn in seq_to_page.items():
            qid = f"PHY-CLS-OptionB-P{int(paper.split()[-1])}-{seq:03d}"
            img = f'/figures/optb-{paper.replace(" ", "")}-p{pn:03d}.jpg'
            cur.execute("UPDATE questions SET question_image=? WHERE id=? AND (question_image IS NULL OR question_image='')",
                        (img, qid))
            if cur.rowcount > 0:
                updated += 1
        print(f"  {paper}: {updated} 题补图", flush=True)

    tx = db
    tx.commit()
    db.close()
    print("DONE")

if __name__ == "__main__":
    main()
