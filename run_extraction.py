import os
import sys
import json
import time
import numpy as np
import torch
from PIL import Image

# Add wardrobe to sys.path
sys.path.insert(0, r"c:\Users\Lenovo\Desktop\fasion\wardrobe")

from backend.config import settings
from backend import segmenter
from backend import matting

def run_extraction_on_user_image():
    input_image_path = r"C:\Users\Lenovo\.gemini\antigravity-ide\brain\7bc1c6fd-8c3d-44cd-92a0-194ebf0c23ac\.user_uploaded\media_1786824813034.jpg"
    output_dir = r"c:\Users\Lenovo\Desktop\fasion\extracted_garments"
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print(f"Starting extraction flow for: {input_image_path}")
    print("=" * 60)

    start_time = time.time()
    img = Image.open(input_image_path).convert("RGB")
    print(f"Original Image Size: {img.size} ({img.width}x{img.height})")

    # Save original copy
    img.save(os.path.join(output_dir, "0_original.jpg"), quality=95)

    # 1. Prepare & Inference
    work = segmenter._resize_to(img, settings.WORK_SIDE)
    print(f"Working Resolution: {work.size}")
    
    print("Running SegFormer inference...")
    probs = segmenter._predict(work)
    certainty = probs.max(axis=0)
    rgb = np.array(work).astype(np.float32)
    frame_area = work.width * work.height
    feather_width = max(1.5, max(work.size) / 640)

    # 2. Branch: Person score
    person_frac, person_conf = segmenter._person_score(probs)
    print(f"Person Check -> Fraction: {person_frac:.4f}, Confidence: {person_conf:.4f}")
    is_worn = not (person_frac < segmenter.MIN_PERSON_FRAC or person_conf < segmenter.MIN_PERSON_CONF)
    print(f"Path selected: {'WORN' if is_worn else 'FLAT-LAY'}")

    # 3. Matting
    print("Running BiRefNet subject matting (if enabled)...")
    subject = matting.subject_matte(work)
    if subject is not None:
        print("BiRefNet subject matte successfully obtained!")
        matte_img = Image.fromarray((subject * 255).astype(np.uint8))
        matte_img.save(os.path.join(output_dir, "1_subject_matte.png"))
    else:
        print("BiRefNet not loaded or disabled; proceeding with geometric/colour fallback.")

    # 4. Save full segmentation label map
    pred_labels = probs.argmax(axis=0)
    palette = [
        0, 0, 0,        # 0 Background
        255, 0, 0,      # 1 Hat
        0, 255, 0,      # 2 Hair
        0, 0, 255,      # 3 Sunglasses
        255, 165, 0,    # 4 Upper-clothes (Top)
        255, 255, 0,    # 5 Skirt
        0, 128, 255,    # 6 Pants / Trousers
        128, 0, 128,    # 7 Dress
        255, 192, 203,  # 8 Belt
        255, 255, 255,  # 9 Left-shoe
        200, 200, 200,  # 10 Right-shoe
        255, 218, 185,  # 11 Face
        0, 255, 128,    # 12 Left-leg
        0, 200, 100,    # 13 Right-leg
        255, 200, 150,  # 14 Left-arm
        230, 180, 130,  # 15 Right-arm
        165, 42, 42,    # 16 Bag
        210, 105, 30,   # 17 Scarf
    ] + [128, 128, 128] * 238

    seg_img = Image.fromarray(pred_labels.astype(np.uint8), mode="P")
    seg_img.putpalette(palette)
    seg_img.convert("RGB").save(os.path.join(output_dir, "1_segmentation_map.png"))

    # 5. Extract garment groups
    extracted_items = []
    
    for group in segmenter.GARMENT_GROUPS:
        g_name = group["name"]
        mask = segmenter._group_mask(probs, group["ids"])
        area = mask.sum()
        if area < frame_area * segmenter.MIN_AREA_FRAC:
            print(f"Skipping {g_name}: area too small ({area} < {frame_area * segmenter.MIN_AREA_FRAC:.0f})")
            continue

        mask = segmenter._clean_mask(mask, group["parts"])
        reason = segmenter._reject(mask, certainty, frame_area)
        if reason:
            print(f"Rejecting {g_name}: reason = {reason}")
            continue

        score = float(certainty[mask].mean())
        print(f"Detected {g_name} with confidence {score:.3f}")

        if score < segmenter.REFINE_BELOW:
            print(f"  -> Refining {g_name} mask via colour grow...")
            refined = segmenter._refine_mask(mask, rgb, probs)
            mask = segmenter._clean_mask(refined, group["parts"])
            if segmenter._reject(mask, certainty, frame_area):
                print(f"  -> Rejected {g_name} after refinement")
                continue

        alpha = segmenter._feather_alpha(mask, feather_width)

        if subject is not None:
            alpha = (alpha.astype(np.float32) * subject).astype(np.uint8)
            if (alpha > 8).sum() < frame_area * segmenter.MIN_AREA_FRAC:
                print(f"  -> Skipping {g_name} after subject matte multiplication (area too small)")
                continue

        ys, xs = np.where(alpha > 8)
        box = (ys.min(), ys.max(), xs.min(), xs.max())
        crop = segmenter._compose_crop(img, alpha, box)

        # Dominant color
        core = segmenter.ndimage.binary_erosion(mask, np.ones((5, 5)))
        if not core.any():
            core = mask
        dom_color = segmenter._dominant_color(rgb.astype(np.uint8), core)

        # Save cutout
        safe_name = g_name.lower().replace(" ", "_")
        crop_filename = f"cutout_{safe_name}.png"
        crop_path = os.path.join(output_dir, crop_filename)
        crop.save(crop_path, optimize=True)

        extracted_items.append({
            "name": g_name,
            "category": group["category"],
            "confidence": round(score, 3),
            "dominant_color": dom_color,
            "crop_file": crop_filename,
            "crop_size": crop.size
        })
        print(f"  -> Successfully saved {g_name} crop ({crop.width}x{crop.height}) with color {dom_color}")

    # 6. Generate Composite Overview Image using PIL
    thumb_h = 400
    thumbs = [work.resize((int(work.width * thumb_h / work.height), thumb_h), Image.LANCZOS)]
    for item in extracted_items:
        c_img = Image.open(os.path.join(output_dir, item["crop_file"]))
        c_w = max(1, int(c_img.width * thumb_h / c_img.height))
        # paste on checkerboard or neutral grey
        bg = Image.new("RGBA", (c_w, thumb_h), (240, 243, 246, 255))
        resized_crop = c_img.resize((c_w, thumb_h), Image.LANCZOS)
        bg.paste(resized_crop, (0, 0), resized_crop)
        thumbs.append(bg.convert("RGB"))

    total_w = sum(t.width for t in thumbs) + 15 * (len(thumbs) - 1)
    summary_img = Image.new("RGB", (total_w, thumb_h), (255, 255, 255))
    curr_x = 0
    for t in thumbs:
        summary_img.paste(t, (curr_x, 0))
        curr_x += t.width + 15

    summary_path = os.path.join(output_dir, "extraction_summary.png")
    summary_img.save(summary_path, quality=92)

    elapsed = time.time() - start_time
    print(f"\nExtraction completed in {elapsed:.2f}s!")
    print(f"Results summary saved to {summary_path}")

    # Save JSON manifest
    with open(os.path.join(output_dir, "extraction_results.json"), "w") as f:
        json.dump({
            "input_file": input_image_path,
            "elapsed_seconds": round(elapsed, 2),
            "is_worn": is_worn,
            "person_confidence": round(person_conf, 3),
            "items": extracted_items
        }, f, indent=2)

if __name__ == "__main__":
    run_extraction_on_user_image()
