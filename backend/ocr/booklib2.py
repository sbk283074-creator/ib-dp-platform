"""booklib2 — practice-question extraction core (clean restart).

Design goals (vs the old pipeline):
  * Extract ONLY practice questions (Exercise / Review set / Practice questions /
    Test yourself / End-of-chapter), never worked Examples, Investigations,
    Activities, chapter openers, objectives, summaries or answers.
  * Locate question bands by POSITION (left-margin digits) so it works even when
    the PDF text layer is a garbled subset font (e.g. Haese GlyphLessFont).
  * Crop each question (with its graphs/sub-parts) to its own image.
"""
import re, os
import pypdfium2 as pdfium

# ---------------------------------------------------------------------------
# word / line extraction
# ---------------------------------------------------------------------------
def page_words(page):
    ws = page.extract_words(extra_attrs=["size"])
    out = []
    for w in ws:
        t = (w.get("text") or "").strip()
        if not t:
            continue
        out.append({
            "text": t, "x0": w["x0"], "x1": w["x1"],
            "top": w["top"], "bottom": w["bottom"],
            "size": float(w.get("size") or 0),
        })
    return out

def group_lines(words, tol=4.0):
    words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines, cur, cur_top = [], [], None
    for w in words:
        if cur_top is None or abs(w["top"] - cur_top) <= tol:
            cur.append(w); cur_top = w["top"] if cur_top is None else cur_top
        else:
            lines.append(cur); cur, cur_top = [w], w["top"]
    if cur:
        lines.append(cur)
    out = []
    for ws in lines:
        ws = sorted(ws, key=lambda w: w["x0"])
        out.append({
            "top": min(w["top"] for w in ws),
            "bottom": max(w["bottom"] for w in ws),
            "x0": min(w["x0"] for w in ws),
            "x1": max(w["x1"] for w in ws),
            "text": " ".join(w["text"] for w in ws),
            "words": ws,
        })
    return out

# ---------------------------------------------------------------------------
# body-font / margin estimation
# ---------------------------------------------------------------------------
def estimate_body(words):
    """Return (body_size, body_left) from the bulk of the words on a page."""
    sizes = [w["size"] for w in words if w["size"] > 0]
    if not sizes:
        return 0.0, 0.0
    sizes.sort()
    body = sizes[len(sizes) // 2]          # median size
    xs = sorted(w["x0"] for w in words if abs(w["size"] - body) <= 1.5)
    left = xs[len(xs) // 10] if xs else min(w["x0"] for w in words)
    return body, left

# ---------------------------------------------------------------------------
# question-number detection
# ---------------------------------------------------------------------------
INT_RE = re.compile(r"^(\d{1,3})$")
NUMPFX_RE = re.compile(r"^(\d{1,3})[.)]$")

def is_qnum(w, body_size, body_left, cfg):
    """A left-margin integer that starts a question."""
    t = w["text"]
    m = INT_RE.match(t) or NUMPFX_RE.match(t)
    if not m:
        return False
    n = int(m.group(1))
    if n < 1 or n > cfg.get("qnum_max", 200):
        return False
    if w["x0"] > body_left - cfg.get("qnum_left_gap", 12):
        return False
    lo = body_size * cfg.get("qnum_size_lo", 0.75)
    hi = body_size * cfg.get("qnum_size_hi", 1.6)
    if not (lo <= w["size"] <= hi):
        return False
    return True
