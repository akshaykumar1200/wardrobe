import os
import sys
import json
import time
import shutil
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

# Add wardrobe to sys.path
sys.path.insert(0, r"c:\Users\Lenovo\Desktop\fasion\wardrobe")

from backend.config import settings
from backend import segmenter
from backend import matting

def process_target_image():
    input_image_path = r"C:\Users\Lenovo\Downloads\image-1786821112747.webp"
    output_dir = r"c:\Users\Lenovo\Desktop\fasion\extracted_garments_2"
    brain_dir = r"C:\Users\Lenovo\.gemini\antigravity-ide\brain\7bc1c6fd-8c3d-44cd-92a0-194ebf0c23ac"
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(brain_dir, exist_ok=True)

    print("=" * 65)
    print(f"Starting extraction flow for: {input_image_path}")
    print("=" * 65)

    start_time = time.time()
    img = Image.open(input_image_path).convert("RGB")
    print(f"Input Image Resolution: {img.size} ({img.width}x{img.height})")

    # Save original copy
    img.save(os.path.join(output_dir, "0_original.jpg"), quality=95)
    img.save(os.path.join(brain_dir, "0_original_2.jpg"), quality=95)

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
    print("Running BiRefNet subject matting...")
    subject = matting.subject_matte(work)
    if subject is not None:
        print("BiRefNet subject matte successfully obtained!")
        matte_img = Image.fromarray((subject * 255).astype(np.uint8))
        matte_img.save(os.path.join(output_dir, "1_subject_matte.png"))
        matte_img.save(os.path.join(brain_dir, "1_subject_matte_2.png"))
    else:
        print("BiRefNet disabled/fallback mode.")

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
    seg_img_rgb = seg_img.convert("RGB")
    seg_img_rgb.save(os.path.join(output_dir, "1_segmentation_map.png"))
    seg_img_rgb.save(os.path.join(brain_dir, "1_segmentation_map_2.png"))

    # 5. Extract garment groups
    extracted_items = []
    
    if not is_worn:
        # FLAT-LAY processing
        matte = matting.subject_matte(work)
        if matte is not None:
            alpha = (matte * 255).astype(np.uint8)
            mask = matte > 0.5
        else:
            mask = segmenter._flatlay_mask(rgb)
            if mask is not None:
                alpha = segmenter._feather_alpha(mask, feather_width)
            else:
                alpha = None

        if mask is not None and mask.mean() <= segmenter.FLATLAY_MAX_AREA and mask.mean() >= segmenter.MIN_AREA_FRAC:
            ys, xs = np.where(alpha > 8)
            crop = segmenter._compose_crop(img, alpha, (ys.min(), ys.max(), xs.min(), xs.max()))
            core = segmenter.ndimage.binary_erosion(mask, np.ones((5, 5)))
            dom_color = segmenter._dominant_color(rgb.astype(np.uint8), core if core.any() else mask)
            crop_filename = "cutout_flatlay.png"
            crop.save(os.path.join(output_dir, crop_filename), optimize=True)
            crop.save(os.path.join(brain_dir, "cutout_flatlay_2.png"), optimize=True)
            extracted_items.append({
                "name": "Untitled piece",
                "category": "other",
                "confidence": None,
                "dominant_color": dom_color,
                "crop_file": crop_filename,
                "brain_crop_file": "cutout_flatlay_2.png",
                "crop_size": crop.size
            })
    else:
        # WORN processing
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

            core = segmenter.ndimage.binary_erosion(mask, np.ones((5, 5)))
            if not core.any():
                core = mask
            dom_color = segmenter._dominant_color(rgb.astype(np.uint8), core)

            safe_name = g_name.lower().replace(" ", "_")
            crop_filename = f"cutout_{safe_name}.png"
            brain_crop_filename = f"cutout_{safe_name}_2.png"
            crop.save(os.path.join(output_dir, crop_filename), optimize=True)
            crop.save(os.path.join(brain_dir, brain_crop_filename), optimize=True)

            extracted_items.append({
                "name": g_name,
                "category": group["category"],
                "confidence": round(score, 3),
                "dominant_color": dom_color,
                "crop_file": crop_filename,
                "brain_crop_file": brain_crop_filename,
                "crop_size": crop.size
            })
            print(f"  -> Successfully saved {g_name} crop ({crop.width}x{crop.height}) with color {dom_color}")

    # 6. Generate Showcase Card
    print("Generating sleek showcase card...")
    orig_card = img.convert("RGB")
    matte_card = (Image.open(os.path.join(brain_dir, "1_subject_matte_2.png")).convert("RGB") 
                  if subject is not None else seg_img_rgb)
    seg_card = seg_img_rgb

    # Calculate layout
    num_items = max(1, len(extracted_items))
    cols = max(3, num_items)
    canvas_w = max(1200, 400 * cols)
    canvas_h = 920
    bg_color = (18, 20, 24)
    card_bg = (28, 32, 40)

    canvas = Image.new("RGBA", (canvas_w, canvas_h), bg_color + (255,))
    draw = ImageDraw.Draw(canvas)

    draw.rectangle([(0, 0), (canvas_w, 60)], fill=(24, 28, 36))
    draw.text((30, 20), "AI WARDROBE EXTRACTION - RESULTS", fill=(255, 255, 255))

    def place_card(card_img, box, title, subtitle="", color_hex=None):
        x0, y0, x1, y1 = box
        draw.rounded_rectangle([(x0, y0), (x1, y1)], radius=12, fill=card_bg, outline=(45, 52, 65), width=2)
        draw.text((x0 + 15, y0 + 12), title, fill=(230, 235, 245))
        if subtitle:
            draw.text((x0 + 15, y0 + 30), subtitle, fill=(150, 165, 185))
        if color_hex:
            draw.rounded_rectangle([(x1 - 85, y0 + 12), (x1 - 15, y0 + 36)], radius=6, fill=color_hex, outline=(255, 255, 255), width=1)

        pad = 12
        top_pad = 50
        cw = (x1 - x0) - 2 * pad
        ch = (y1 - y0) - top_pad - pad
        scale = min(cw / card_img.width, ch / card_img.height)
        nw, nh = max(1, int(card_img.width * scale)), max(1, int(card_img.height * scale))
        scaled = card_img.resize((nw, nh), Image.LANCZOS)
        px = x0 + pad + (cw - nw) // 2
        py = y0 + top_pad + (ch - nh) // 2
        if card_img.mode == "RGBA":
            canvas.paste(scaled, (px, py), scaled)
        else:
            canvas.paste(scaled, (px, py))

    w_col = (canvas_w - 60 - (cols - 1) * 20) // cols
    h_row1 = 360
    top_y = 80

    place_card(orig_card, (30, top_y, 30 + w_col, top_y + h_row1), "1. Input Photo", f"{img.width}x{img.height}")
    place_card(matte_card, (30 + w_col + 20, top_y, 30 + 2*w_col + 20, top_y + h_row1), "2. BiRefNet Matte", "Subject Alpha")
    place_card(seg_card, (30 + 2*(w_col + 20), top_y, 30 + 3*w_col + 40, top_y + h_row1), "3. SegFormer Map", "Class Labels")

    h_row2 = 410
    bottom_y = top_y + h_row1 + 25

    for i, item in enumerate(extracted_items):
        item_img = Image.open(os.path.join(brain_dir, item["brain_crop_file"])).convert("RGBA")
        bx0 = 30 + i * (w_col + 20)
        bx1 = bx0 + w_col
        sub = f"Conf: {item['confidence']} | {item['dominant_color']}" if item['confidence'] else item['dominant_color']
        place_card(item_img, (bx0, bottom_y, bx1, bottom_y + h_row2), f"{item['name']} ({item['category']})", sub, item['dominant_color'])

    showcase_path = os.path.join(brain_dir, "showcase_gallery_2.png")
    canvas.convert("RGB").save(showcase_path, quality=95)
    canvas.convert("RGB").save(os.path.join(output_dir, "showcase_gallery.png"), quality=95)

    elapsed = time.time() - start_time
    print(f"\nCompleted in {elapsed:.2f}s!")
    print(f"Showcase saved to: {showcase_path}")

    # JSON output
    results_json = {
        "input_file": input_image_path,
        "elapsed_seconds": round(elapsed, 2),
        "is_worn": is_worn,
        "person_confidence": round(person_conf, 3) if person_conf else None,
        "items": extracted_items
    }
    with open(os.path.join(brain_dir, "extraction_results_2.json"), "w") as f:
        json.dump(results_json, f, indent=2)

if __name__ == "__main__":
    process_target_image()
