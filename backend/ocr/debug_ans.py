#!/usr/bin/env python3
import os, re
import pypdfium2 as pdfium
import extract_physics_topic as E

folder, paper = "Topic 1", "HL-paper1"
qpath = os.path.join(E.SRC_ROOT, folder, paper + ".pdf")
mspath = E.find_markscheme(os.path.join(E.SRC_ROOT, folder), paper)
q_doc = pdfium.PdfDocument(qpath); ms_doc = pdfium.PdfDocument(mspath)
E._MS_DOC = ms_doc
ms_index = E.build_markscheme_index(ms_doc)
questions = E.extract_questions(q_doc)
norm_full = ms_index['norm_full']; norm_to_raw = ms_index['norm_to_raw']; full = ms_index['full']

qtexts = []
for qi, q in enumerate(questions, start=1):
    parts = [E.band_text(q_doc[pi], yt, yb) for (pi, yt, yb) in q['bands'] if E.band_text(q_doc[pi], yt, yb)]
    raw = "\n\n".join(parts)
    qtexts.append(None if (E.is_cover(raw) or len(raw.strip()) < 5) else E.strip_title(raw))

def next_real(i):
    for j in range(i, len(qtexts)):
        if qtexts[j] is not None: return qtexts[j]
    return None

prev = 0
for qi, q in enumerate(questions, start=1):
    qt = qtexts[qi-1]
    if qt is None:
        # show what the band text actually was
        parts = [E.band_text(q_doc[pi], yt, yb) for (pi, yt, yb) in q['bands']]
        print(f"Q{qi:02d} SKIPPED. band raw text(s): {[repr(p[:60]) for p in parts]}")
        continue
    needle = E.normalize(qt).lower()[:90]
    ni = norm_full.find(needle, prev)
    nxt = next_real(qi)
    nneedle = E.normalize(nxt).lower()[:90] if nxt else None
    npos = norm_full.find(nneedle, ni+1) if (nneedle and ni>=0) else -1
    bound = npos if (npos and npos>ni) else len(norm_full)
    er = norm_full.find("examiners report", ni+1) if ni>=0 else -1
    mk = norm_full.find("markscheme", ni+1) if ni>=0 else -1
    cut = min([x for x in (bound, er if er>ni else 10**9, mk if mk>ni else 10**9)])
    raw_i = norm_to_raw[ni] if ni>=0 else 0
    raw_e = norm_to_raw[cut] if (ni>=0 and cut < len(norm_to_raw)) else len(full)
    ans = full[raw_i:raw_e]
    ans = E.HEADER_LINE.sub("", ans); ans = E.NA_TOKEN.sub("", ans); ans = E.strip_title(ans).strip()
    print(f"Q{qi:02d}: found_ni={ni} npos={npos} cut={cut}")
    print(f"   needle={needle!r}")
    print(f"   ANSWER({len(ans)}c): {ans[:200]!r}")
    prev = cut if ni>=0 else prev
