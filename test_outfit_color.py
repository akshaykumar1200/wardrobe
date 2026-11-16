import json
import numpy as np
from colors import get_nearest_color_name
from outfit_color import outfit_palette, score_outfit, rank_combinations

def test_outfits():
    print("=" * 70)
    print("TESTING OUTFIT COLOR ENGINE (Problem 2 & Problem 3)")
    print("=" * 70)

    # 1. The Mountain Photo Look (Extracted earlier)
    # Top: #2c524a (Forest Green)
    # Trousers: #29374c (Denim)
    # Shoes: #919090 (Grey / Silver)
    mountain_outfit = [
        {
            "id": 1,
            "category": "topwear",
            "name": "Green Mineral-Wash T-Shirt",
            "area": 74448,
            "colors": [{"hex": "#2c524a", "name": get_nearest_color_name("#2c524a"), "share": 1.0}],
            "pattern": "solid",
            "scale": "none"
        },
        {
            "id": 2,
            "category": "bottomwear",
            "name": "Straight-Leg Denim Jeans",
            "area": 64484,
            "colors": [{"hex": "#29374c", "name": "denim", "share": 1.0}],
            "pattern": "solid",
            "scale": "none"
        },
        {
            "id": 3,
            "category": "shoes",
            "name": "White/Grey Low-Top Sneakers",
            "area": 13206,
            "colors": [{"hex": "#919090", "name": "grey", "share": 1.0}],
            "pattern": "solid",
            "scale": "none"
        }
    ]

    print("\n--- [OUTFIT 1] Mountain Photo Look (Green Tee + Denim Jeans + Grey Sneakers) ---")
    pal1 = outfit_palette(mountain_outfit)
    print("Whole-Outfit Palette Signature:")
    print(json.dumps(pal1, indent=2))

    res1 = score_outfit(mountain_outfit)
    print(f"\nScore: {res1['score']}/100 | Verdict: {res1['verdict'].upper()}")
    print("Styling Notes:")
    for note in res1["notes"]:
        print(f"  • {note}")

    # 2. Test Wardrobe Ranking
    wardrobe = [
        # Tops
        {"id": "top_green", "category": "topwear", "area": 70000, "colors": [{"hex": "#2c524a", "name": "forest green", "share": 1.0}]},
        {"id": "top_white", "category": "topwear", "area": 70000, "colors": [{"hex": "#FFFFFF", "name": "white", "share": 1.0}]},
        {"id": "top_orange", "category": "topwear", "area": 70000, "colors": [{"hex": "#FFA500", "name": "orange", "share": 1.0}]},
        # Bottoms
        {"id": "bot_denim", "category": "bottomwear", "area": 65000, "colors": [{"hex": "#29374c", "name": "denim", "share": 1.0}]},
        {"id": "bot_khaki", "category": "bottomwear", "area": 65000, "colors": [{"hex": "#F0E68C", "name": "khaki", "share": 1.0}]},
        {"id": "bot_magenta", "category": "bottomwear", "area": 65000, "colors": [{"hex": "#FF00FF", "name": "magenta", "share": 1.0}]},
        # Shoes
        {"id": "shoe_white", "category": "shoes", "area": 15000, "colors": [{"hex": "#FFFFFF", "name": "white", "share": 1.0}]},
        {"id": "shoe_puma_grey", "category": "shoes", "area": 15000, "colors": [{"hex": "#716f70", "name": "grey", "share": 1.0}]},
    ]

    print("\n" + "=" * 70)
    print("RANKING COMBINATIONS FROM SAMPLE WARDROBE")
    print("=" * 70)
    top_combos = rank_combinations(wardrobe, top_n=5)
    for i, c in enumerate(top_combos):
        print(f"\n#{i+1}: Combo {c['items']} -> Score: {c['score']}/100 ({c['verdict'].upper()})")
        for n in c["notes"]:
            print(f"    - {n}")

if __name__ == "__main__":
    test_outfits()
