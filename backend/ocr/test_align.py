#!/usr/bin/env python3
import pypdfium2 as pdfium
SRC = "/Users/lucas.ma/Downloads/dp learning/Physics-HL-Topic questions"
doc = pdfium.PdfDocument(SRC + "/Topic 1/HL-paper1.pdf")
tp = doc[0].get_textpage()
n = tp.count_chars()
full = tp.get_text_range()
print("count_chars =", n, " len(get_text_range) =", len(full))
print("\n--- first 60 chars of get_text_range() ---")
print(repr(full[:300]))
print("\n--- charbox vs text[i] for i in 0..40 ---")
for i in range(min(40, n)):
    cb = tp.get_charbox(i)
    ch = full[i] if i < len(full) else '?'
    print(f"i={i:2d} charbox={cb}  text[{i}]={ch!r}")
print("\n--- get_text_range() char positions of spaces ---")
spaces = [i for i,c in enumerate(full) if c == ' ']
print("num spaces in full:", len(spaces), "first few idx:", spaces[:10])
print("num spaces in first", n, "chars:", sum(1 for i in spaces if i < n))
