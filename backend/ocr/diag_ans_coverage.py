import sys, os, re, json
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import booklib as BB
import extract_answers as A
book=next(b for b in E.BOOKS if b['id']=='PH-OX-2023')
practice, ext = A.build_answer_index(book['answer_path'])
# textbook question counts per printed page (from book_json)
j=json.load(open('book_json/PH-OX-2023.json'))
offset=8
from collections import Counter
tb=Counter()
for q in j['questions']:
    pp=q['book_page']-offset
    tb[pp]+=1
for pp in [11,16,25,34,46,59,61]:
    ans_qnums=[q for (q,p,y) in practice.get(pp,[])]
    print(f"printed {pp}: textbook={tb.get(pp,0)} answers_qnums={ans_qnums}")
print("=== EXT index ===", [(q,p) for q,p,y in ext])
