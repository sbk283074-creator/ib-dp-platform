import sqlite3, os
DP="/Users/lucas.ma/Downloads/dp learning"
db=os.path.join(DP,"ib-dp-platform","backend","app.db")
print("db exists:", os.path.exists(db), os.path.getsize(db) if os.path.exists(db) else "")
con=sqlite3.connect(db); con.row_factory=sqlite3.Row
cur=con.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("TABLES:", [r[0] for r in cur.fetchall()])
