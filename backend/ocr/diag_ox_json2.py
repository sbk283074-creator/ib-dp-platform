import json, os
from collections import defaultdict
here = os.path.dirname(__file__)
j = json.load(open(os.path.join(here, "book_json", "PH-OX-2023.json")))
qs = j["questions"]
print("total rows in json:", len(qs))
by_page = defaultdict(list)
for row in qs:
    by_page[row.get("book_page")].append(row)
for p in range(700, 721):
    rows = by_page.get(p, [])
    if rows:
        print(f"--- json book_page={p} count={len(rows)}")
        for r in rows:
            print("   id=", r.get("id"), "topic=", r.get("topic"), "qnum=", r.get("qnum"),
                  "qi=", r.get("question_image"))
