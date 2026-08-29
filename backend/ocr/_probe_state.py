import sqlite3, os, json, re
from collections import defaultdict

DB = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/data/app.db"
OCR = "/Users/lucas.ma/Downloads/dp learning/ib-dp-platform/backend/ocr"
con = sqlite3.connect(DB)
cur = con.cursor()

print("=== PAPER image breakdown ===")
r = cur.execute("SELECT COUNT(*), SUM(CASE WHEN question_image IS NOT NULL AND question_image<>'' THEN 1 ELSE 0 END), SUM(CASE WHEN (question_image IS NULL OR question_image='') THEN 1 ELSE 0 END) FROM questions WHERE source_type='paper'").fetchone()
print("paper: total=%s with_image=%s text(orphan)=%s" % r)

print("\n=== BOOK counts + answer coverage ===")
rows = cur.execute("""SELECT book_id, COUNT(*),
  SUM(CASE WHEN answer IS NOT NULL AND answer<>'' THEN 1 ELSE 0 END),
  SUM(CASE WHEN answer_image IS NOT NULL AND answer_image<>'' THEN 1 ELSE 0 END),
  SUM(CASE WHEN explanation IS NOT NULL AND explanation<>'' THEN 1 ELSE 0 END)
  FROM questions WHERE source_type='book' GROUP BY book_id ORDER BY book_id""").fetchall()
for b,n,a,ai,e in rows:
    print("  %-16s n=%-5s answer=%-5s answer_img=%-4s explanation=%-5s" % (b,n,a,ai,e))

print("\n=== HODDER books ===")
hd = cur.execute("SELECT book_id, COUNT(*) FROM questions WHERE source_type='book' AND book_id LIKE '%HODDER%' GROUP BY book_id").fetchall()
for b,n in hd: print("  %s %s" % (b,n))

print("\n=== book questions with NO answer/explanation/answer_image ===")
z = cur.execute("SELECT COUNT(*) FROM questions WHERE source_type='book' AND (answer IS NULL OR answer='') AND (explanation IS NULL OR explanation='') AND (answer_image IS NULL OR answer_image='')").fetchone()
print("  ", z[0])

print("\n=== reports table ===")
try:
    reps = cur.execute("SELECT id, target_id, report_type, status, detail, resolved_at FROM reports ORDER BY id").fetchall()
    print("  total reports: %d" % len(reps))
    for rid,tid,rt,st,det,ra in reps:
        print("  [%s] %s | type=%s | status=%s | resolved=%s" % (rid, tid, rt, st, ra))
        if det: print("        detail: %s" % det[:160])
except Exception as ex:
    print("  reports query error:", ex)

print("\n=== manifest + checkpoint topic progress ===")
mf = os.path.join(OCR, "screenshot_manifest.jsonl")
prefixes = set()
with open(mf) as f:
    for line in f:
        m = re.search(r'"prefix": "([^"]+)"', line)
        if m: prefixes.add(m.group(1))
topic_pref = sorted(p for p in prefixes if "XXXX" in p)
print("  manifest total records: %d" % sum(1 for _ in open(mf)))
print("  manifest unique prefixes: %d" % len(prefixes))
print("  manifest unique TOPIC(XXXX) prefixes: %d  (expected 62)" % len(topic_pref))
for p in topic_pref: print("    %s" % p)

ck = os.path.join(OCR, "screenshot_ckpt.json")
ckpt = json.load(open(ck))
done = [k for k,v in ckpt.items() if v=="done"]
topic_done = [k for k in done if "XXXX" in k]
print("  checkpoint done entries: %d" % len(done))
print("  checkpoint TOPIC done: %d" % len(topic_done))

con.close()
print("\nDB file mtime:", os.path.getmtime(DB))
