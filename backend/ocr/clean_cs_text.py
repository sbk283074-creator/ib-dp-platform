#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Safe garbling cleanup for CS questions (does NOT alter meaning).

Fixes unambiguous OCR artifacts produced when OCR'ing the scanned CS book:
  - full-width characters (。，；：（） etc and full-width A-Z0-9) -> half-width
  - isolated CJK operator misreads: 二->=, 三->≡, 十->+, 一->-  (only when NOT
    surrounded by other CJK, so real Chinese phrases are never touched)
  - TZO -> TZ0 inside exam codes
  - strip control characters

Idempotent: running twice changes nothing after the first pass.
Reversible: DB was backed up to app.db.bak before running.

Usage:
  python3 clean_cs_text.py            # DB only (default)
  python3 clean_cs_text.py --with-json  # also rewrite cs_import.json
"""
import argparse, re, sqlite3, json, os

DB = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/data/app.db"
IMPORT_JSON = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/ocr/cs_import.json"
SUBJECT = "CS"
REPL_COLS = ["question", "answer", "explanation"]

CJK_SYM = {"\u4e8c": "=", "\u4e09": "\u2261", "\u5341": "+", "\u4e00": "-"}  # 二 三 十 一


def fw_to_hw(ch):
    o = ord(ch)
    if o == 0x3000:
        return " "
    if o == 0x3002:
        return "."          # ideographic full stop 。
    if o == 0x3001:
        return ","          # ideographic comma 、
    if 0xFF01 <= o <= 0xFF5E:
        return chr(o - 0xFEE0)
    return ch


def clean(text):
    if not text:
        return text
    # 1) full-width -> half-width (punctuation, letters, digits, space)
    text = "".join(fw_to_hw(c) for c in text)
    # 2) strip control chars (keep normal whitespace)
    text = "".join(c for c in text if not (ord(c) < 32 and c not in "\n\r\t"))
    # 2.5) collapsed CJK operator pairs in code (==, ===)
    text = text.replace("\u4e8c\u4e8c", "==").replace("\u4e09\u4e09", "===")
    # 3) isolated CJK operator misreads -> symbols
    out = []
    chars = list(text)
    for i, c in enumerate(chars):
        if c in CJK_SYM:
            prev = chars[i - 1] if i > 0 else ""
            nxt = chars[i + 1] if i + 1 < len(chars) else ""
            cjk_prev = "\u4e00" <= prev <= "\u9fff"
            cjk_nxt = "\u4e00" <= nxt <= "\u9fff"
            if not (cjk_prev or cjk_nxt):
                out.append(CJK_SYM[c])
                continue
        out.append(c)
    text = "".join(out)
    # 4) TZO -> TZ0 inside codes
    text = re.sub(r"TZ[Oo](?!\d)", "TZ0", text)
    return text


def count_issues(text):
    if not text:
        return 0
    fw = sum(1 for c in text if 0xFF01 <= ord(c) <= 0xFF5E or ord(c) in (0x3000, 0x3001, 0x3002))
    sym = sum(1 for c in text if c in CJK_SYM)
    tzo = len(re.findall(r"TZ[Oo](?!\d)", text))
    return fw + sym + tzo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-json", action="store_true")
    args = ap.parse_args()

    db = sqlite3.connect(DB)
    cols = [r[1] for r in db.execute("PRAGMA table_info(questions)")]
    missing = [c for c in REPL_COLS if c not in cols]
    if missing:
        raise SystemExit(f"missing columns: {missing}")

    rows = db.execute(
        f"SELECT id, {', '.join(REPL_COLS)} FROM questions WHERE subject=?",
        (SUBJECT,)).fetchall()

    before = sum(count_issues(" ".join(r[1:])) for r in rows)
    upd = 0
    for r in rows:
        rid = r[0]
        newvals = [clean(v) for v in r[1:]]
        if newvals != list(r[1:]):
            db.execute(
                f"UPDATE questions SET {', '.join(c+'=?' for c in REPL_COLS)} WHERE id=?",
                newvals + [rid])
            upd += 1
    db.commit()
    after = sum(count_issues(" ".join(
        db.execute(f"SELECT {', '.join(REPL_COLS)} FROM questions WHERE id=?", (rid,)).fetchone()))
        for rid in [x[0] for x in rows])
    print(f"[clean] CS rows={len(rows)} updated={upd} issue-chars before={before} after={after}", flush=True)

    if args.with_json and os.path.exists(IMPORT_JSON):
        data = json.load(open(IMPORT_JSON))
        jupd = 0
        for rec in data:
            if rec.get("subject") != SUBJECT:
                continue
            if any(rec.get(c) != clean(rec.get(c)) for c in REPL_COLS):
                for c in REPL_COLS:
                    rec[c] = clean(rec.get(c))
                jupd += 1
        json.dump(data, open(IMPORT_JSON, "w"), ensure_ascii=False, indent=1)
        print(f"[clean] cs_import.json updated={jupd}", flush=True)

    db.close()


if __name__ == "__main__":
    main()
