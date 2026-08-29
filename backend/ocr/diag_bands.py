#!/usr/bin/env python3
import pypdfium2 as pdfium
import extract_physics_topic as E
import numpy as np

SRC = E.SRC_ROOT
doc = pdfium.PdfDocument(SRC + "/Topic 1/HL-paper1.pdf")
pi = 0
img = E.render_page(doc[pi])
H = img.height
runs = E.detect_separator_runs(img)
print(f"page H(px)={H}  separator runs={runs}")
bands = E.page_bands(runs, H)
print("bands (y_top,y_bot,kind):")
for b in bands:
    print("  ", b)

# For each band, count chars selected by chars_in_band and show first 120 chars
tp = doc[pi].get_textpage()
n = tp.count_chars()
H_pt = doc[pi].get_size()[1]
full = tp.get_text_range()
print(f"\nfull text len={len(full)}")
for (yt, yb, kind) in bands:
    # replicate chars_in_band selection
    y_low_pt = H_pt - yb / E.SCALE
    y_high_pt = H_pt - yt / E.SCALE
    sel = []
    for i in range(n):
        cb = tp.get_charbox(i)
        if cb is None: continue
        x0,y0,x1,y1 = cb
        if y0 <= y_high_pt and y1 >= y_low_pt:
            sel.append(i)
    # show text in index order (reading order) for selected chars
    txt_reading = "".join(full[i] for i in sel)
    print(f"\nband yt={yt} yb={yb} kind={kind} nsel={len(sel)}")
    print("  READING-ORDER text:", repr(txt_reading[:160]))
