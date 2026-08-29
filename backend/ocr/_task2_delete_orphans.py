"""Task 2: delete the ~8,053 orphaned paper text rows for re-screenshotted papers.

After import_shots.mjs has upserted every manifest record as an image-backed
row, the only source_type='paper' rows that still have question_image empty
are the old text-extraction orphans. This script removes them, but ONLY
those whose id is NOT in the current manifest (i.e. truly orphaned), and
NEVER a row flagged well_down=1.

Usage:
  python3 _task2_delete_orphans.py            # dry-run: show counts only
  python3 _task2_delete_orphans.py --execute  # actually delete
"""
import argparse, json, os, sqlite3, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DB   = os.path.join(ROOT, "ib-dp-platform", "backend", "data", "app.db")
MAN  = os.path.join(ROOT, "ib-dp-platform", "backend", "ocr", "screenshot_manifest.jsonl")

def load_manifest_ids(path):
    ids = set()
    with open(path) as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("type") == "question" and rec.get("id"):
                ids.add(rec["id"])
    return ids

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="actually delete (default: dry-run)")
    args = ap.parse_args()

    if not os.path.exists(DB):
        print(f"DB not found: {DB}", file=sys.stderr); sys.exit(1)
    if not os.path.exists(MAN):
        print(f"Manifest not found: {MAN}", file=sys.stderr); sys.exit(1)

    manifest_ids = load_manifest_ids(MAN)
    print(f"manifest ids (question records): {len(manifest_ids)}")

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # overall paper breakdown
    cur.execute("SELECT COUNT(*) AS n FROM questions WHERE source_type='paper'")
    total_paper = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM questions WHERE source_type='paper' AND (question_image IS NULL OR question_image='')")
    text_paper = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM questions WHERE source_type='paper' AND question_image IS NOT NULL AND question_image!=''")
    img_paper = cur.fetchone()["n"]
    print(f"questions source_type='paper': total={total_paper}  text(orphan candidates)={text_paper}  with_image={img_paper}")

    # text rows that are ALSO in the manifest id set (these will be overwritten
    # by import_shots; we should NOT touch them here, but report them)
    q = ("SELECT COUNT(*) AS n FROM questions "
         "WHERE source_type='paper' AND (question_image IS NULL OR question_image='') "
         "AND id IN (SELECT id FROM questions WHERE source_type='paper' AND (question_image IS NULL OR question_image='') AND id IN (" +
         ",".join("?" * len(manifest_ids)) + "))")
    # the above is silly; simpler: count overlap of text ids with manifest
    cur.execute("SELECT id FROM questions WHERE source_type='paper' AND (question_image IS NULL OR question_image='')")
    text_ids = {r["id"] for r in cur.fetchall()}
    overlap = text_ids & manifest_ids
    print(f"text-row ids that ALSO appear in manifest (will be replaced by import_shots): {len(overlap)}")

    # true orphans: text rows whose id is NOT in the manifest
    orphan_ids = text_ids - manifest_ids
    print(f"true orphan text-row ids (id NOT in manifest): {len(orphan_ids)}")

    # of those, how many are well_down=1 (must be preserved)
    if orphan_ids:
        ph = ",".join("?" * len(orphan_ids))
        cur.execute(f"SELECT COUNT(*) AS n FROM questions WHERE id IN ({ph}) AND well_down=1", list(orphan_ids))
        wd = cur.fetchone()["n"]
        cur.execute(f"SELECT COUNT(*) AS n FROM questions WHERE id IN ({ph}) AND well_down=0", list(orphan_ids))
        deletable = cur.fetchone()["n"]
        print(f"  of orphans: well_down=1 (KEEP): {wd}  well_down=0 (delete): {deletable}")
    else:
        wd = deletable = 0
        print("  no orphans.")

    # by subject (for the deletable ones)
    if deletable:
        ph = ",".join("?" * len(orphan_ids))
        cur.execute(f"SELECT subject, COUNT(*) AS n FROM questions WHERE id IN ({ph}) AND well_down=0 GROUP BY subject", list(orphan_ids))
        print("  deletable by subject:")
        for r in cur.fetchall():
            print(f"    {r['subject']:18s}  {r['n']}")

    if not args.execute:
        print("\n[DRY-RUN] pass --execute to actually delete.")
        con.close()
        return

    if deletable == 0:
        print("\n[execute] nothing to delete.")
        con.close()
        return

    # safety: show first 8 ids about to be deleted
    sample = sorted(orphan_ids - set())[:8]  # all deletable are well_down=0; we already filtered
    ph = ",".join("?" * len(orphan_ids))
    cur.execute(f"SELECT id, subject, source FROM questions WHERE id IN ({ph}) AND well_down=0 ORDER BY id LIMIT 8", list(orphan_ids))
    print("\nfirst 8 ids to delete:")
    for r in cur.fetchall():
        print(f"  {r['id']}  {r['subject']}  {r['source']}")

    ph = ",".join("?" * len(orphan_ids))
    cur.execute(f"DELETE FROM questions WHERE id IN ({ph}) AND well_down=0", list(orphan_ids))
    n = cur.rowcount
    con.commit()
    print(f"\n[execute] deleted {n} orphan text rows.")

    # after
    cur.execute("SELECT COUNT(*) AS n FROM questions WHERE source_type='paper'")
    print(f"after: questions source_type='paper' = {cur.fetchone()['n']}")
    con.close()

if __name__ == "__main__":
    main()
