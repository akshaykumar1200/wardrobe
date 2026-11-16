import os
import shutil
import json
from pathlib import Path
from backend import db

brain_dir = Path(r"C:\Users\Lenovo\.gemini\antigravity-ide\brain\7bc1c6fd-8c3d-44cd-92a0-194ebf0c23ac")
items_dir = Path("storage/items")
items_dir.mkdir(parents=True, exist_ok=True)

db.init_db()

seed_items = [
    {
        "src": "cutout_top.png",
        "dst": "top_green_vintage.png",
        "name": "Vintage Green Mineral-Wash Tee",
        "category": "topwear",
        "color_hex": "#2c524a",
        "color_name": "pine",
        "colors": [
            {"hex": "#224741", "name": "charcoal", "share": 0.31},
            {"hex": "#88d3ba", "name": "emerald", "share": 0.284},
            {"hex": "#3d6d61", "name": "pine", "share": 0.149},
            {"hex": "#5a9c8a", "name": "teal", "share": 0.144}
        ],
        "pattern": "graphic",
        "pattern_scale": "bold",
        "area": 46681,
        "confidence": 0.982,
        "wear_count": 3
    },
    {
        "src": "cutout_trousers.png",
        "dst": "bottom_denim_straight.png",
        "name": "Straight-Leg Denim Jeans",
        "category": "bottomwear",
        "color_hex": "#29384d",
        "color_name": "denim",
        "colors": [
            {"hex": "#29384d", "name": "denim", "share": 0.715},
            {"hex": "#a2cdf0", "name": "sky blue", "share": 0.153},
            {"hex": "#7297c0", "name": "royal blue", "share": 0.096}
        ],
        "pattern": "solid",
        "pattern_scale": "none",
        "area": 42928,
        "confidence": 0.958,
        "wear_count": 4
    },
    {
        "src": "cutout_shoes.png",
        "dst": "shoes_white_grey_lowtop.png",
        "name": "Low-Top White & Grey Sneakers",
        "category": "shoes",
        "color_hex": "#9a9794",
        "color_name": "grey",
        "colors": [
            {"hex": "#9a9794", "name": "grey", "share": 0.274},
            {"hex": "#b6b8bb", "name": "silver", "share": 0.231},
            {"hex": "#7d7a77", "name": "grey", "share": 0.195},
            {"hex": "#f6f4e0", "name": "beige", "share": 0.158}
        ],
        "pattern": "solid",
        "pattern_scale": "none",
        "area": 5029,
        "confidence": 0.717,
        "wear_count": 2
    },
    {
        "src": "cutout_flatlay_2.png",
        "dst": "shoes_puma_rs_grey.png",
        "name": "Puma RS Grey/White Sneakers",
        "category": "shoes",
        "color_hex": "#7c7a7b",
        "color_name": "grey",
        "colors": [
            {"hex": "#7c7a7b", "name": "grey", "share": 0.201},
            {"hex": "#a9a5a4", "name": "silver", "share": 0.187},
            {"hex": "#d9d7d3", "name": "light grey", "share": 0.175},
            {"hex": "#5b5554", "name": "taupe", "share": 0.171}
        ],
        "pattern": "solid",
        "pattern_scale": "none",
        "area": 812841,
        "confidence": 0.88,
        "wear_count": 1
    }
]

conn = db.get_conn()
# Clean existing seed
conn.execute("DELETE FROM items")

for it in seed_items:
    src_file = brain_dir / it["src"]
    dst_file = items_dir / it["dst"]
    if src_file.exists():
        shutil.copyfile(src_file, dst_file)
        print(f"Copied {it['src']} -> {dst_file}")
    
    conn.execute(
        """
        INSERT INTO items (name, category, image_path, color_hex, color_name, colors_json, pattern, pattern_scale, area, confidence, wear_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            it["name"],
            it["category"],
            f"/storage/items/{it['dst']}",
            it["color_hex"],
            it["color_name"],
            json.dumps(it["colors"]),
            it["pattern"],
            it["pattern_scale"],
            it["area"],
            it["confidence"],
            it["wear_count"]
        )
    )

conn.commit()
conn.close()
print("Seeding completed successfully!")
