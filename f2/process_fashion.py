import os
import torch
import torch.nn as nn
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from transformers import SegformerImageProcessor, AutoModelForSemanticSegmentation

def process_image(image_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Loading input image from {image_path}...")
    orig_img = Image.open(image_path).convert("RGB")
    orig_np = np.array(orig_img)
    w, h = orig_img.size

    print("Loading SegFormer model (mattmdjaga/segformer_b2_clothes)...")
    processor = SegformerImageProcessor.from_pretrained("mattmdjaga/segformer_b2_clothes")
    model = AutoModelForSemanticSegmentation.from_pretrained("mattmdjaga/segformer_b2_clothes")
    
    labels_map = model.config.id2label
    print("Model labels:", labels_map)

    print("Running inference...")
    inputs = processor(images=orig_img, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    logits = outputs.logits.cpu()

    upsampled_logits = nn.functional.interpolate(
        logits,
        size=(h, w),
        mode="bilinear",
        align_corners=False,
    )

    pred_mask = upsampled_logits.argmax(dim=1)[0].numpy() # shape (h, w)

    # 1. Save Colored Segmentation Visualization
    plt.figure(figsize=(12, 12))
    plt.subplot(1, 2, 1)
    plt.imshow(orig_img)
    plt.axis("off")
    plt.title("Original Photo")

    plt.subplot(1, 2, 2)
    plt.imshow(pred_mask, cmap="tab20")
    plt.axis("off")
    plt.title("SegFormer Garment Segmentation")
    plt.tight_layout()
    segmentation_path = os.path.join(output_dir, "1_segmentation_map.png")
    plt.savefig(segmentation_path, bbox_inches="tight")
    plt.close()
    print(f"Saved segmentation visualization to {segmentation_path}")

    # Helper function to create RGBA cutouts
    def make_cutout(mask_condition, filename):
        cutout = np.zeros((h, w, 4), dtype=np.uint8)
        cutout[..., :3] = orig_np
        cutout[..., 3] = np.where(mask_condition, 255, 0).astype(np.uint8)
        out_img = Image.fromarray(cutout)
        save_path = os.path.join(output_dir, filename)
        out_img.save(save_path)
        print(f"Saved cutout: {save_path}")
        return cutout

    # Identify label IDs for upper clothes, pants, shoes, person
    # Typical IDs in segformer_b2_clothes:
    # 4: Sunglasses, 5: Upper-clothes, 7: Coat, 9: Pants, 18: Left-shoe, 19: Right-shoe
    upper_ids = [k for k, v in labels_map.items() if "upper" in v.lower() or "coat" in v.lower() or "dress" in v.lower()]
    pants_ids = [k for k, v in labels_map.items() if "pant" in v.lower() or "skirt" in v.lower()]
    shoes_ids = [k for k, v in labels_map.items() if "shoe" in v.lower()]
    bg_ids = [0] # 0 is background

    upper_mask = np.isin(pred_mask, upper_ids)
    pants_mask = np.isin(pred_mask, pants_ids)
    shoes_mask = np.isin(pred_mask, shoes_ids)
    person_mask = pred_mask != 0

    # 2. Save Cutouts
    make_cutout(upper_mask, "2_cutout_tshirt.png")
    make_cutout(pants_mask, "3_cutout_jeans.png")
    make_cutout(shoes_mask, "4_cutout_shoes.png")
    make_cutout(person_mask, "5_cutout_person_no_bg.png")

    # 3. Garment Recoloring Demonstration
    # Recolor the green t-shirt into different colors preserving luminance/texture
    img_float = orig_np.astype(np.float32) / 255.0
    
    # Calculate luminance channel
    luminance = 0.299 * img_float[..., 0] + 0.587 * img_float[..., 1] + 0.114 * img_float[..., 2]

    target_colors = {
        "black_tshirt.png": (0.15, 0.15, 0.18),    # Sleek Black / Charcoal
        "red_tshirt.png": (0.85, 0.12, 0.15),      # Ruby Red
        "blue_tshirt.png": (0.10, 0.35, 0.85),     # Royal Blue
        "purple_tshirt.png": (0.55, 0.15, 0.75),   # Deep Violet
    }

    fig, axes = plt.subplots(2, 2, figsize=(12, 12))
    axes = axes.flatten()

    for idx, (fname, rgb_color) in enumerate(target_colors.items()):
        recolored = orig_np.copy()
        for c in range(3):
            # blend target color with luminance
            recolored_c = np.clip(luminance * rgb_color[c] * 255.0 * 1.5, 0, 255).astype(np.uint8)
            recolored[..., c] = np.where(upper_mask, recolored_c, orig_np[..., c])

        recolored_img = Image.fromarray(recolored)
        recolored_path = os.path.join(output_dir, f"6_recolored_{fname}")
        recolored_img.save(recolored_path)
        
        axes[idx].imshow(recolored_img)
        axes[idx].axis("off")
        color_name = fname.replace("_tshirt.png", "").capitalize()
        axes[idx].set_title(f"Recolored T-Shirt ({color_name})")

    plt.tight_layout()
    recolor_summary_path = os.path.join(output_dir, "6_recolor_variations.png")
    plt.savefig(recolor_summary_path, bbox_inches="tight")
    plt.close()
    print(f"Saved recoloring summary to {recolor_summary_path}")

    print("All processing finished successfully!")

if __name__ == "__main__":
    src_img = r"C:\Users\Lenovo\.gemini\antigravity-ide\brain\316605a8-d959-447d-8964-11210b6bfe12\media__1786551512894.jpg"
    out_dir = r"c:\Users\Lenovo\Desktop\fasion\f2"
    process_image(src_img, out_dir)
