"""Remove item rows whose image file is gone, and accounts created by tests.

Dry run by default. Nothing is deleted unless you pass --apply.

    venv\\Scripts\\python.exe cleanup_orphans.py            # show what would go
    venv\\Scripts\\python.exe cleanup_orphans.py --apply    # do it

Why this exists: seed scripts and the test suite wrote rows into the real
database pointing at image files that were never created. The web closet and
the Android app both render those as blank cards.
"""
import shutil
import sys
from datetime import datetime
from pathlib import Path

from backend.config import settings
from backend.database import SessionLocal
from backend.models import Item, Session as SessionModel, Upload, User

# Accounts that exist only because seeding or pytest ran against the real DB.
TEST_EMAIL_PREFIXES = ("alice_", "public_tester_")
TEST_EMAILS = ("admin@exmple.com",)  # typo'd domain, created by a test run


def main() -> int:
    apply = "--apply" in sys.argv
    db = SessionLocal()
    root = Path(settings.STORAGE_ROOT)

    orphans = [
        item
        for item in db.query(Item).all()
        if not (root / "users" / str(item.user_id) / "items" / item.stored_name).exists()
    ]
    junk_users = [
        user
        for user in db.query(User).all()
        if user.email.startswith(TEST_EMAIL_PREFIXES) or user.email in TEST_EMAILS
    ]

    print(f"item rows with no image file: {len(orphans)}")
    for item in orphans[:40]:
        print(f"    user {item.user_id}  {item.name[:28]:<30} {item.stored_name}")
    if len(orphans) > 40:
        print(f"    ... and {len(orphans) - 40} more")

    print(f"\ntest accounts: {len(junk_users)}")
    for user in junk_users:
        items = db.query(Item).filter(Item.user_id == user.id).count()
        uploads = db.query(Upload).filter(Upload.user_id == user.id).count()
        print(f"    {user.email:<34} items={items} uploads={uploads}")

    if not apply:
        print("\nDry run. Nothing changed. Pass --apply to delete the above.")
        db.close()
        return 0

    # A copy of the database before touching it, since this cannot be undone.
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = Path("backups") / f"{stamp}-cleanup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    db_file = settings.DATABASE_URL.replace("sqlite:///", "").lstrip("./")
    shutil.copy2(db_file, backup_dir / Path(db_file).name)
    print(f"\ndatabase copied to {backup_dir}/")

    for item in orphans:
        db.delete(item)

    for user in junk_users:
        # Explicit, in dependency order: the models declare no cascade.
        db.query(Item).filter(Item.user_id == user.id).delete()
        db.query(Upload).filter(Upload.user_id == user.id).delete()
        db.query(SessionModel).filter(SessionModel.user_id == user.id).delete()
        db.delete(user)

    db.commit()

    print("\n--- after ---")
    for user in db.query(User).all():
        items = db.query(Item).filter(Item.user_id == user.id).all()
        missing = sum(
            1
            for i in items
            if not (root / "users" / str(user.id) / "items" / i.stored_name).exists()
        )
        print(f"    {user.email:<34} items={len(items):>3} missing={missing}")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
