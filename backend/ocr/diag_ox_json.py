import json, collections
d = json.load(open('book_json/PH-OX-2023.json'))
rows = d['questions']
print('TOTAL rows:', len(rows))
# page distribution
pages = collections.Counter(r['book_page'] for r in rows)
print('distinct book_page:', len(pages))
print('min/max page:', min(pages), max(pages))
# reported bad pages (printed)
reported = [673,674,689,694,701,705,706,707,709]
print('\n--- reported pages presence ---')
for p in reported:
    n = pages.get(p, 0)
    print(f'printed {p}: {n} rows')
# anomalies from live validation: printed 700, 701
for p in [700,701]:
    n = pages.get(p,0)
    print(f'printed {p} (anomaly): {n} rows')
# show rows on pages 694-709
print('\n--- rows on printed 690..712 ---')
for r in sorted([r for r in rows if r['book_page'] and 690 <= r['book_page'] <= 712],
                key=lambda x:(x['book_page'], x.get('in_book_order') or 0)):
    q = (r.get('question') or '')[:60].replace('\n',' ')
    print(f"  p{r['book_page']:4} {r['id']:18} sec={r.get('book_section')!r:40} q={q!r}")
# any rows whose question text looks like non-question (IA / index / heading only)?
print('\n--- suspicious: very short question text ---')
for r in rows:
    q = (r.get('question') or '').strip()
    if len(q) < 25:
        print(f"  p{r['book_page']} {r['id']}: {q!r}")
