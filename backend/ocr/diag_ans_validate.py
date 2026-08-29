import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import extract_answers as A

book = next(b for b in E.BOOKS if b['id'] == 'PH-OX-2023')
practice, ext = A.build_answer_index(book['answer_path'])
print("ext index:", [(q, p) for q, p, y in ext])
# Simulated CORRECTED questions for the extended-response pages:
# raw pdf 707 -> printed 699 -> extended Q1
# raw pdf 708 -> printed 700 -> extended Q2
# raw pdf 709 -> printed 701 -> extended Q3
sim = [
    dict(book_id='PH-OX-2023', printed_page=699, sibling_index=0, qnum_int=1, extended=True, answer_path=book['answer_path']),
    dict(book_id='PH-OX-2023', printed_page=700, sibling_index=0, qnum_int=2, extended=True, answer_path=book['answer_path']),
    dict(book_id='PH-OX-2023', printed_page=701, sibling_index=0, qnum_int=3, extended=True, answer_path=book['answer_path']),
]
for q in sim:
    rel, note = A.match_one_question(q, practice, ext, offset=8, extended=True)
    print(f"printed={q['printed_page']} Q{q['qnum_int']} -> {rel} ({note})")
