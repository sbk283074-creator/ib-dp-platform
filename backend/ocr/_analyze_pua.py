#!/usr/bin/env python3
"""Inspect PUA math-glyph context in the AA HL P1 manifest to design a mapping."""
import json, re, collections

MANIFEST = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/data/paper_aa_p1_manifest.json"
recs = json.load(open(MANIFEST, encoding="utf-8"))

def annotate(s):
    out = []
    for ch in s:
        o = ord(ch)
        if 0xE000 <= o <= 0xF8FF:
            out.append(f"<U+{o:04X}>")
        else:
            out.append(ch)
    return "".join(out)

# 1) frequency of every PUA codepoint
freq = collections.Counter()
for r in recs:
    for key in ("question", "answer"):
        for ch in (r.get(key) or ""):
            o = ord(ch)
            if 0xE000 <= o <= 0xF8FF:
                freq[o] += 1

print("=== PUA codepoint frequency (top 60) ===")
for o, c in freq.most_common(60):
    print(f"  U+{o:04X}  {c}")

# 2) context windows for the STRUCTURAL codepoints (fraction/matrix pieces)
STRUCT = set(range(0xF0E6, 0xF0FC)) | set(range(0xF8EB, 0xF8F9))
print("\n=== Context windows for structural PUA codepoints ===")
shown = collections.Counter()
for r in recs:
    for key in ("question", "answer"):
        txt = r.get(key) or ""
        for m in re.finditer(r'[\ue000-\uf8ff]', txt):
            o = ord(m.group(0))
            if o not in STRUCT:
                continue
            if shown[o] >= 3:
                continue
            shown[o] += 1
            a = max(0, m.start()-45); b = min(len(txt), m.end()+45)
            print(f"\n-- U+{o:04X} [{r['id']}] --")
            print("   " + annotate(txt[a:b]).replace("\n", "\\n"))
