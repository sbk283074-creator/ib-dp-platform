import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import booklib as B
import pypdfium2 as pdfium
path = '/Users/lucas.ma/Downloads/dp learning/Physics-HLSL-Oxford Textbook(First exam 2025)/Physics - Course Companion - Homer, Piętka and Heathcote - Fifth Edition - Oxford 2023.pdf'
pdf = pdfium.PdfDocument(path)
for idx in (707, 708):  # 0-indexed -> PDF 708, 709
    page = pdf[idx]
    print(f"\n===== PDF page {idx+1} (printed {idx-7}) =====")
    H = float(page.get_height())
    for top, text, x0 in B.pdfium_lines(page):
        rel = top / H
        mark = ''
        if 0 <= rel < 0.05 or rel > 0.94:
            mark = ' [HF]'
        num = B._line_start_number(text, True)
        if num is not None:
            mark += f' <NUM={num}>'
        if B._bare_dot(text):
            mark += ' <DOT>'
        print(f"  y={rel:5.2f} x0={x0:6.1f}{mark}  {text[:70]!r}")
