#!/usr/bin/env python3
"""Debug Topic 1 HL-paper1: print bands, their texts, and the markscheme
answer-region each question resolves to."""
import os, re
import pypdfium2 as pdfium
import extract_physics_topic as E

SRC = E.SRC_ROOT
folder = "Topic 1"
paper = "HL-paper1"
qpath = os.path.join(SRC, folder, paper + ".pdf")
mspath = E.find_markscheme(os.path.join(SRC, folder), paper)
print("qpath", qpath, "exists", os.path.exists(qpath))
print("mspath", mspath, "exists", os.path.exists(mspath) if mspath else False)

q_doc = pdfium.PdfDocument(qpath)
ms_doc = pdfium.PdfDocument(mspath)
E._MS_DOC = ms_doc
ms_index = E.build_markscheme_index(ms_doc)

questions = E.extract_questions(q_doc)
print(f"\n=== {len(questions)} question bands ===")
for qi, q in enumerate(questions, start=1):
    parts = []
    for (pi, yt, yb) in q['bands']:
        t = E.band_text(q_doc[pi], yt, yb)
        if t:
            parts.append(t)
    raw = "\n\n".join(parts)
    cover = E.is_cover(raw)
    print(f"\n--- Q{qi:02d} pages={q['pages']} cover={cover} len={len(raw.strip())} ---")
    print("  TEXT:", repr(raw[:300]))

# Now simulate answer matching for each non-cover question
qtexts = []
for qi, q in enumerate(questions, start=1):
    parts = [E.band_text(q_doc[pi], yt, yb) for (pi, yt, yb) in q['bands'] if E.band_text(q_doc[pi], yt, yb)]
    raw = "\n\n".join(parts)
    qtexts.append(None if (E.is_cover(raw) or len(raw.strip())<5) else E.strip_title(raw))

def next_real(i):
    for j in range(i, len(qtexts)):
        if qtexts[j] is not None: return qtexts[j]
    return None

prev = 0
norm_full = ms_index['norm_full']; norm_to_raw = ms_index['norm_to_raw']
print("\n=== ANSWER REGIONS ===")
for qi, q in enumerate(questions, start=1):
    qt = qtexts[qi-1]
    if qt is None:
        print(f"Q{qi:02d}: SKIPPED (cover/blank)"); continue
    needle = E.normalize(qt).lower()[:90]
    ni = norm_full.find(needle, prev)
    print(f"\nQ{qi:02d}: needle={needle!r} found_ni={ni}")
    if ni < 0:
        print("   -> PROMPT NOT FOUND"); continue
    nxt = next_real(qi)
    nneedle = E.normalize(nxt).lower()[:90] if nxt else None
    npos = norm_full.find(nneedle, ni+1) if nneedle else -1
    print(f"   next needle={nneedle!r} npos={npos}")
    bound = npos if (npos and npos>ni) else len(norm_full)
    er = norm_full.find("examiners report", ni+1)
    mk = norm_full.find("markscheme", ni+1)
    cut = min([x for x in (bound, er if er>ni else 10**9, mk if mk>ni else 10**9)])
    raw_i = norm_to_raw[ni]; raw_e = norm_to_raw[cut] if cut<len(norm_to_raw) else len(ms_index['full'])
    print(f"   bound={bound} er={er} mk={mk} cut={cut}")
    print(f"   RAW region [{raw_i}:{raw_e}] text={ms_index['full'][raw_i:raw_e]!r}")
    prev = cut
