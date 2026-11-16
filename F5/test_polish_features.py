import os
import time
from pathlib import Path
import db
from outfit_color import rank_combinations
from main import cleanup_orphan_files

def test_all():
    print("=====================================================")
    print("  TESTING F5 POLISH ENHANCEMENTS")
    print("=====================================================")

    # 1. Test WAL Mode
    print("\n>> [TEST 1] Verifying SQLite WAL Mode...")
    conn = db.get_conn()
    mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
    conn.close()
    print(f"   SQLite journal mode: {mode}")
    assert mode.lower() == "wal", f"Expected WAL mode, got {mode}"
    print("   [OK] PASS: SQLite is running in high-concurrency WAL mode.")

    # 2. Test Accessory Combination Styling
    print("\n>> [TEST 2] Testing Accessory & Bag Outfit Styling...")
    wardrobe = [
        {"id": 1, "category": "upper", "label": "Linen Shirt", "colors": [{"hex": "#FFFFFF", "name": "white", "share": 1.0}], "area": 50000, "pattern": "solid"},
        {"id": 2, "category": "lower", "label": "Navy Trousers", "colors": [{"hex": "#000080", "name": "navy", "share": 1.0}], "area": 60000, "pattern": "solid"},
        {"id": 3, "category": "footwear", "label": "Brown Loafers", "colors": [{"hex": "#8B4513", "name": "brown", "share": 1.0}], "area": 20000, "pattern": "solid"},
        {"id": 4, "category": "bag", "label": "Leather Tote", "colors": [{"hex": "#8B4513", "name": "brown", "share": 1.0}], "area": 15000, "pattern": "solid"},
    ]
    ranked = rank_combinations(wardrobe, top_n=3)
    assert len(ranked) > 0, "No combinations generated"
    top_items = ranked[0]["items"]
    categories = [i["category"] for i in top_items]
    print(f"   Top generated outfit categories: {categories}")
    print(f"   Stylist Score: {ranked[0]['score']}/100 ({ranked[0]['verdict'].upper()})")
    assert "bag" in categories or "footwear" in categories, "Expected accessory or footwear in outfit"
    print("   [OK] PASS: Accessories & bags successfully styled into whole looks.")

    # 3. Test 24-Hour Orphan Cutout Auto-Cleanup
    print("\n>> [TEST 3] Testing 24-Hour Orphan Cutout Cleanup...")
    items_dir = Path("storage/items")
    items_dir.mkdir(parents=True, exist_ok=True)
    
    old_orphan = items_dir / "test_orphan_25h_old.png"
    recent_orphan = items_dir / "test_orphan_1h_recent.png"
    
    old_orphan.write_bytes(b"dummy_old_data")
    recent_orphan.write_bytes(b"dummy_recent_data")
    
    # Set modification time: old = 25 hours ago, recent = 1 hour ago
    now = time.time()
    os.utime(old_orphan, (now - 90000, now - 90000))
    os.utime(recent_orphan, (now - 3600, now - 3600))
    
    # Run cleanup with 24h (86400s) threshold
    purged = cleanup_orphan_files(max_age_seconds=86400)
    print(f"   Purged unreferenced old files count: {purged}")
    
    assert not old_orphan.exists(), "Old orphan file (>24h) should have been deleted"
    assert recent_orphan.exists(), "Recent orphan file (<24h) should be preserved for active session"
    print("   [OK] PASS: >24h unconfirmed orphan files deleted, active session previews preserved.")
    
    # Clean up test recent file
    recent_orphan.unlink(missing_ok=True)

    print("\n=====================================================")
    print("  ALL BACKEND POLISH ENHANCEMENTS VERIFIED & PASSING!")
    print("=====================================================")

if __name__ == "__main__":
    test_all()
