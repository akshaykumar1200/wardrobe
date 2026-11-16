import os
import json
from PIL import Image
from pattern import analyze_garment
from outfit_color import outfit_palette, score_outfit, rank_combinations

def test_full_pipeline():
    print("=" * 70)
    print("END-TO-END VERIFICATION: PATTERN.PY + OUTFIT_COLOR.PY")
    print("=" * 70)

    brain_dir = r"C:\Users\Lenovo\.gemini\antigravity-ide\brain\7bc1c6fd-8c3d-44cd-92a0-194ebf0c23ac"

    # 1. Load the real extracted garment crops
    top_img = Image.open(os.path.join(brain_dir, "cutout_top.png"))
    pants_img = Image.open(os.path.join(brain_dir, "cutout_trousers.png"))
    shoes_img = Image.open(os.path.join(brain_dir, "cutout_shoes.png"))
    flatlay_img = Image.open(os.path.join(brain_dir, "cutout_flatlay_2.png"))

    print("\n--- STEP 1: Analyzing Individual Garments with pattern.py ---")
    top_item = analyze_garment(top_img, category="topwear", name="Vintage Green Mineral-Wash Tee", item_id="top_green_1")
    pants_item = analyze_garment(pants_img, category="bottomwear", name="Straight Denim Jeans", item_id="pants_denim_1")
    shoes_item = analyze_garment(shoes_img, category="shoes", name="Low-Top White/Grey Sneakers", item_id="shoes_white_1")
    flatlay_item = analyze_garment(flatlay_img, category="shoes", name="Puma RS Grey/White Sneakers", item_id="shoes_puma_1")

    for it in [top_item, pants_item, shoes_item, flatlay_item]:
        print(f"\nGarment: [{it['category'].upper()}] {it['name']}")
        print(f"  Pattern: {it['pattern']} (scale: {it['scale']}) | Area: {it['area']}px")
        print(f"  Dominant Colors:")
        for c in it["colors"]:
            print(f"    - {c['name']} ({c['hex']}): {c['share']*100:.1f}%")

    print("\n" + "=" * 70)
    print("--- STEP 2: Whole-Outfit Palette Signature & Scoring (outfit_color.py) ---")
    print("=" * 70)

    outfit_1 = [top_item, pants_item, shoes_item]
    result_1 = score_outfit(outfit_1)

    print(f"\nOutfit 1 Score: {result_1['score']}/100 | Verdict: {result_1['verdict'].upper()}")
    print("Stylist Feedback Notes:")
    for note in result_1["notes"]:
        print(f"  • {note}")

    print("\nPalette Signature:")
    print(json.dumps(result_1["palette"], indent=2))

    print("\n" + "=" * 70)
    print("--- STEP 3: Outfit 2 with Puma RS Sneakers ---")
    print("=" * 70)
    outfit_2 = [top_item, pants_item, flatlay_item]
    result_2 = score_outfit(outfit_2)
    print(f"\nOutfit 2 Score: {result_2['score']}/100 | Verdict: {result_2['verdict'].upper()}")
    for note in result_2["notes"]:
        print(f"  • {note}")

    print("\n" + "=" * 70)
    print("--- STEP 4: Wardrobe Rank Combinations ---")
    print("=" * 70)
    wardrobe = [top_item, pants_item, shoes_item, flatlay_item]
    ranked = rank_combinations(wardrobe, top_n=5)
    for i, r in enumerate(ranked):
        print(f"Rank #{i+1} Score {r['score']}/100 ({r['verdict'].upper()}) -> Items: {r['items']}")

if __name__ == "__main__":
    test_full_pipeline()
