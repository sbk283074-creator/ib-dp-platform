import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as B
import pypdfium2
BOOK_ID='PH-OX-2023'
book=next(b for b in E.BOOKS if b['id']==BOOK_ID)
pdf=pypdfium2.PdfDocument(book['path'])
for i in [706,707,708]:  # 0-indexed -> pdf 707,708,709
    page=pdf[i]
    H=float(page.get_height()); W=float(page.get_width())
    kind,gutter=B.detect_columns(page)
    print(f"=== pdf {i+1} gutter={gutter} W={W:.1f}")
    right_lines=B.column_lines(page,gutter,W,dedup_against=[])
    print(f"  right col lines ({len(right_lines)}):")
    for (top,text,x0) in right_lines[:40]:
        print(f"    top={top:7.1f} x0={x0:7.1f} {text!r}")
    print(f"  page_image_bboxes={B.page_image_bboxes(page)}")
