"""Copy accounts, garments and history from the old SQLite file into the configured database.

Dry run by default; pass --apply to write. Re-running is safe: an account that
already has garments in the target is skipped whole, never merged.

    venv\\Scripts\\python.exe migrate_from_sqlite.py
    venv\\Scripts\\python.exe migrate_from_sqlite.py --apply
"""

import sqlite3
import sys
from datetime import datetime, date
from pathlib import Path

from backend import crops
from backend.database import SessionLocal, DB_URL
from backend.models import (
    Blob, Item, Outfit, OutfitItem, Upload, User, WearEvent, WearEventItem,
)

SRC = Path("wardrobe.db")
APPLY = "--apply" in sys.argv


def _dt(value):
    """SQLite hands back strings where the models want datetimes."""
    if value is None or isinstance(value, (datetime, date)):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _crop_bytes(old_user_id: int, stored_name: str) -> bytes | None:
    if not stored_name:
        return None
    path = Path("storage/users") / str(old_user_id) / "items" / stored_name
    return path.read_bytes() if path.is_file() else None


def main() -> int:
    if not SRC.is_file():
        print(f"{SRC} not found")
        return 1

    src = sqlite3.connect(SRC)
    src.row_factory = sqlite3.Row
    db = SessionLocal()

    print(f"from : {SRC}")
    print(f"to   : {DB_URL.split('@')[-1]}")
    print(f"mode : {'APPLY' if APPLY else 'dry run'}\n")

    # Only accounts that actually hold something. The rest are leftover test signups.
    worth_moving = [
        row for row in src.execute(
            """
            select * from users u where exists (select 1 from items where user_id = u.id)
               or exists (select 1 from outfits where user_id = u.id)
               or exists (select 1 from wear_events where user_id = u.id)
            order by u.id
            """
        )
    ]

    moved = {"users": 0, "uploads": 0, "items": 0, "crops": 0, "outfits": 0, "wears": 0}
    skipped = []
    missing_crops = []

    for su in worth_moving:
        email = su["email"]
        existing = db.query(User).filter(User.email == email).first()
        if existing is not None and db.query(Item).filter(Item.user_id == existing.id).count():
            skipped.append(f"{email} (already has garments here)")
            continue

        n_items = src.execute("select count(*) from items where user_id=?", (su["id"],)).fetchone()[0]
        print(f"  {email}: {n_items} garments")

        if not APPLY:
            moved["users"] += 1
            moved["items"] += n_items
            for row in src.execute("select user_id, stored_name from items where user_id=?", (su["id"],)):
                if row["stored_name"] and _crop_bytes(su["id"], row["stored_name"]) is None:
                    missing_crops.append(row["stored_name"])
            continue

        user = existing
        if user is None:
            user = User(
                email=email,
                password_hash=su["password_hash"],
                display_name=su["display_name"],
                is_admin=bool(su["is_admin"]),
                is_active=bool(su["is_active"]),
                created_at=_dt(su["created_at"]),
                last_login=_dt(su["last_login"]),
            )
            db.add(user)
            db.flush()
            moved["users"] += 1

        upload_map = {}
        for ro in src.execute("select * from uploads where user_id=?", (su["id"],)):
            up = Upload(
                user_id=user.id,
                stored_name=ro["stored_name"],
                bytes=ro["bytes"],
                created_at=_dt(ro["created_at"]),
            )
            db.add(up)
            db.flush()
            upload_map[ro["id"]] = up.id
            moved["uploads"] += 1

        item_map = {}
        for ri in src.execute("select * from items where user_id=? order by id", (su["id"],)):
            data = _crop_bytes(su["id"], ri["stored_name"])
            if ri["stored_name"] and data is None:
                missing_crops.append(ri["stored_name"])
            it = Item(
                user_id=user.id,
                name=ri["name"],
                category=ri["category"],
                stored_name=ri["stored_name"],
                color=ri["color"],
                bytes=ri["bytes"],
                upload_id=upload_map.get(ri["upload_id"]),
                is_manual=bool(ri["is_manual"]),
                created_at=_dt(ri["created_at"]),
            )
            db.add(it)
            db.flush()
            item_map[ri["id"]] = it.id
            moved["items"] += 1
            if data is not None:
                crops.put(db, user.id, ri["stored_name"], data)
                moved["crops"] += 1

        outfit_map = {}
        for ro in src.execute("select * from outfits where user_id=? order by id", (su["id"],)):
            out = Outfit(user_id=user.id, name=ro["name"], created_at=_dt(ro["created_at"]))
            db.add(out)
            db.flush()
            outfit_map[ro["id"]] = out.id
            moved["outfits"] += 1
            for roi in src.execute("select * from outfit_items where outfit_id=?", (ro["id"],)):
                db.add(OutfitItem(
                    outfit_id=out.id,
                    item_id=item_map.get(roi["item_id"]),
                    item_name=roi["item_name"],
                ))

        for rw in src.execute("select * from wear_events where user_id=? order by id", (su["id"],)):
            worn_items = list(src.execute(
                "select * from wear_event_items where wear_event_id=?", (rw["id"],)))
            # The key is built from item ids, which change here. Rebuilt from the
            # new ids so "already worn today" still recognises this outfit; the old
            # key would point at rows that no longer exist. Same format as wears.py.
            new_ids = sorted(item_map[r["item_id"]] for r in worn_items
                             if r["item_id"] in item_map)
            ev = WearEvent(
                user_id=user.id,
                worn_on=rw["worn_on"],  # a String column holding 'YYYY-MM-DD', not a date
                composition_key=",".join(str(i) for i in new_ids) or rw["composition_key"],
                outfit_id=outfit_map.get(rw["outfit_id"]),
                created_at=_dt(rw["created_at"]),
            )
            db.add(ev)
            db.flush()
            moved["wears"] += 1
            for rwi in worn_items:
                db.add(WearEventItem(
                    wear_event_id=ev.id,
                    item_id=item_map.get(rwi["item_id"]),
                    item_name=rwi["item_name"],
                ))

        db.commit()

    print()
    for key, count in moved.items():
        print(f"{key:>8}: {count}")
    for line in skipped:
        print(f" skipped: {line}")
    if missing_crops:
        print(f" crop files not on disk: {len(missing_crops)}")

    if APPLY:
        print(f"\nnow in target: {db.query(User).count()} users, "
              f"{db.query(Item).count()} items, {db.query(Blob).count()} crops")
    else:
        print("\nnothing written. re-run with --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
