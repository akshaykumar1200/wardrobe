"""One-off migration: dedup originals, re-extract every item with the current
pipeline, and drop crops whose source photo no longer exists.

Backs up wardrobe.db and the user's storage tree before touching anything.
Run from the wardrobe/ directory:

    venv/Scripts/python.exe reprocess.py --user 6
    venv/Scripts/python.exe reprocess.py --user 6 --apply
"""
import argparse
import hashlib
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image

from backend.config import settings
from backend.segmenter import extract_garments

DB = Path("wardrobe.db")


def backup(user_id: int) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = Path("backups") / f"{stamp}-user{user_id}"
    dest.mkdir(parents=True, exist_ok=True)

    for name in ("wardrobe.db", "wardrobe.db-wal", "wardrobe.db-shm"):
        src = Path(name)
        if src.exists():
            shutil.copy2(src, dest / name)

    user_dir = Path(settings.STORAGE_ROOT) / "users" / str(user_id)
    if user_dir.exists():
        shutil.copytree(user_dir, dest / "storage", dirs_exist_ok=True)

    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", type=int, required=True)
    ap.add_argument("--apply", action="store_true", help="without this, only prints the plan")
    args = ap.parse_args()
    uid = args.user

    originals = Path(settings.STORAGE_ROOT) / "users" / str(uid) / "originals"
    items_dir = Path(settings.STORAGE_ROOT) / "users" / str(uid) / "items"
    if not originals.exists():
        print(f"no originals for user {uid}")
        return 1

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    old_items = conn.execute(
        "select id, stored_name, bytes from items where user_id=?", (uid,)
    ).fetchall()
    uploads = conn.execute(
        "select id, stored_name from uploads where user_id=? order by id", (uid,)
    ).fetchall()

    # Group uploads by the content of the file they point at. Everything after
    # the first row in a group is a duplicate of it.
    by_hash: dict[str, list[sqlite3.Row]] = {}
    missing = []
    for up in uploads:
        f = originals / up["stored_name"]
        if not f.exists():
            missing.append(up)
            continue
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        by_hash.setdefault(h, []).append(up)

    on_disk = sorted(items_dir.glob("*.png")) if items_dir.exists() else []
    disk_bytes = sum(p.stat().st_size for p in on_disk)

    print(f"user {uid}")
    print(f"  item rows in db     {len(old_items)}")
    print(f"  item files on disk  {len(on_disk)}  ({disk_bytes/1024/1024:.1f} MB)")
    print(f"  orphan files        {len(on_disk) - len({i['stored_name'] for i in old_items})}")
    print(f"  upload rows         {len(uploads)}")
    print(f"  unique photos       {len(by_hash)}")
    if missing:
        print(f"  uploads whose original is gone: {[u['id'] for u in missing]}")
    print()

    if not args.apply:
        print("dry run. re-run with --apply to execute.")
        return 0

    dest = backup(uid)
    print(f"backed up to {dest}\n")

    # Wipe derived data. Crops are regenerated from the originals below; any
    # item whose source photo is missing is intentionally not rebuilt.
    conn.execute("delete from items where user_id=?", (uid,))
    for p in on_disk:
        p.unlink()

    # Collapse duplicate upload rows onto the first of each group.
    keep_ids = []
    for group in by_hash.values():
        keeper = group[0]
        keep_ids.append(keeper["id"])
        for dup in group[1:]:
            conn.execute("delete from uploads where id=?", (dup["id"],))
    for up in missing:
        conn.execute("delete from uploads where id=?", (up["id"],))

    # Rename each surviving original to its content hash so the dedup check in
    # storage.validate_and_store_original matches it on a future re-upload.
    total = 0
    for keeper_id in keep_ids:
        row = conn.execute("select stored_name from uploads where id=?", (keeper_id,)).fetchone()
        src = originals / row["stored_name"]
        payload = src.read_bytes()
        new_name = f"{hashlib.sha256(payload).hexdigest()[:32]}.jpg"
        if new_name != row["stored_name"]:
            src.rename(originals / new_name)
            conn.execute("update uploads set stored_name=? where id=?", (new_name, keeper_id))

        img = Image.open(originals / new_name)
        result = extract_garments(img, uid)
        found = result["items"]
        if result["notice"]:
            print(f"  {new_name[:12]}  note: {result['notice']}")
        for g in found:
            conn.execute(
                "insert into items (user_id, name, category, stored_name, color, bytes,"
                " upload_id, is_manual, created_at) values (?,?,?,?,?,?,?,0,datetime('now'))",
                (uid, g["name"], g["category"], g["stored_name"], g["color"],
                 g["bytes"], keeper_id),
            )
        total += len(found)
        detail = ", ".join("{} {}".format(g["name"], g["confidence"]) for g in found)
        print(f"  {new_name[:12]}  -> {len(found)} items ({detail or 'none'})")

    # Duplicate upload rows are gone; the files they pointed at are now
    # unreferenced and would otherwise sit on disk forever.
    referenced = {
        r["stored_name"]
        for r in conn.execute("select stored_name from uploads where user_id=?", (uid,))
    }
    for p in originals.glob("*.jpg"):
        if p.name not in referenced:
            print(f"  removing unreferenced original {p.name[:12]} "
                  f"({p.stat().st_size/1024/1024:.1f} MB)")
            p.unlink()

    conn.commit()

    now = sorted(items_dir.glob("*.png"))
    print(f"\n  {total} items, {len(now)} files, "
          f"{sum(p.stat().st_size for p in now)/1024/1024:.1f} MB "
          f"(was {len(on_disk)} files, {disk_bytes/1024/1024:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
