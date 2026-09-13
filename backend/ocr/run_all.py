"""Run the v3 extractor over every book in the registry."""
import sys, os, time, logging, traceback
logging.disable(logging.CRITICAL)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract_v3 as E
from book_registry import BOOKS

only = sys.argv[1:] if len(sys.argv) > 1 else None
t0 = time.time()
tot = 0
for cfg in BOOKS:
    if only and cfg["id"] not in only:
        continue
    t = time.time()
    try:
        book, qs = E.extract_book(cfg, verbose=False)
        tot += len(qs)
        print(f"[ok]   {cfg['id']:18} Q={len(qs):5}  {time.time()-t:6.1f}s", flush=True)
    except Exception as ex:
        print(f"[FAIL] {cfg['id']:18} {type(ex).__name__}: {ex}", flush=True)
        traceback.print_exc()
print(f"DONE  total questions={tot}  elapsed={time.time()-t0:.0f}s", flush=True)
