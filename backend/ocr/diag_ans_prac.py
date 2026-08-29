import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import extract_books as E
import extract_answers as A

book = next(b for b in E.BOOKS if b['id'] == 'PH-OX-2023')
practice, ext = A.build_answer_index(book['answer_path'])
# Simulated practice questions with KNOWN qnums (from the answer book's own qnums)
sim = [
    # printed 11 (header "Pages 11-12"), answer qnums 1,2 -> match Q1
    dict(book_id='PH-OX-2023', printed_page=11, sibling_index=0, qnum_int=1, extended=False, answer_path=book['answer_path']),
    # printed 25, answer qnums 14,15,17,18
    dict(book_id='PH-OX-2023', printed_page=25, sibling_index=0, qnum_int=15, extended=False, answer_path=book['answer_path']),
    dict(book_id='PH-OX-2023', printed_page=25, sibling_index=1, qnum_int=18, extended=False, answer_path=book['answer_path']),
    # printed 34, answer qnums 19,9,20,0,21,22,2,23,25,5
    dict(book_id='PH-OX-2023', printed_page=34, sibling_index=0, qnum_int=19, extended=False, answer_path=book['answer_path']),
    dict(book_id='PH-OX-2023', printed_page=34, sibling_index=1, qnum_int=2, extended=False, answer_path=book['answer_path']),
    # printed 46, answer qnums 1,2,4,5,6
    dict(book_id='PH-OX-2023', printed_page=46, sibling_index=0, qnum_int=4, extended=False, answer_path=book['answer_path']),
]
for q in sim:
    rel, note = A.match_one_question(q, practice, ext, offset=8, extended=True)
    print(f"printed={q['printed_page']} Q{q['qnum_int']} -> {rel} ({note})")
