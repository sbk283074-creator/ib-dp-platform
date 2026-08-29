import sqlite3, os
DP="/Users/lucas.ma/Downloads/dp learning"
db=os.path.join(DP,"ib-dp-platform","backend","data","app.db")
con=sqlite3.connect(db); con.row_factory=sqlite3.Row
cur=con.cursor()
cur.execute("""SELECT id,book_page,topic,question,answer_image,question_image
               FROM questions WHERE book_id='PH-OX-2023' AND book_page BETWEEN 700 AND 720
               ORDER BY book_page, id""")
rows=cur.fetchall()
print("rows 700-720:", len(rows))
for r in rows:
    print("==== book_page=",r["book_page"],"id=",r["id"],"topic=",r["topic"])
    print("  question=",repr(r["question"])[:140])
    print("  answer_image=",r["answer_image"])
    print("  question_image=",r["question_image"])
