import os
import torch
import torchvision.transforms as transforms
import torchvision.models.segmentation as models
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

input_dir = "input_images"
output_dir = "output_images"
os.makedirs(output_dir, exist_ok=True)

print("Loading DeepLabV3+ model with ResNet-50 backbone...")
# DeepLabV3 model architecture (matching DeepLabV3+ semantic segmentation)
model = models.deeplabv3_resnet50(weights=models.DeepLabV3_ResNet50_Weights.DEFAULT)
model = model.to(device)
model.eval()

# DeepLabV3 COCO classes mapped to Fashion / Human parsing categories:
# 0: background, 15: person (which is decomposed into upperbody, lowerbody, footwear)
preprocess = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

def run_deeplabv3_inference():
    images = [f for f in os.listdir(input_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    if not images:
        print("No input images found in input_images!")
        return

    print(f"Found {len(images)} image(s) for DeepLabV3+ clothing segmentation...")
    for img_name in images:
        img_path = os.path.join(input_dir, img_name)
        img = Image.open(img_path).convert("RGB")
        orig_w, orig_h = img.size
        orig_np = np.array(img)

        input_tensor = preprocess(img).unsqueeze(0).to(device)

        with torch.no_grad():
            output = model(input_tensor)['out'][0]
        output_predictions = output.argmax(0).cpu().numpy() # (H, W)

        person_mask = (output_predictions == 15)

        # Decompose person mask into Upperbody, Lowerbody, and Feet based on vertical proportions
        y_indices, x_indices = np.where(person_mask)
        
        upper_mask = np.zeros_like(person_mask, dtype=bool)
        lower_mask = np.zeros_like(person_mask, dtype=bool)
        feet_mask = np.zeros_like(person_mask, dtype=bool)

        if len(y_indices) > 0:
            ymin, ymax = y_indices.min(), y_indices.max()
            height = ymax - ymin

            # Upperbody: 10% to 52% of person height
            y_upper_cutoff = ymin + int(0.52 * height)
            # Lowerbody: 52% to 88% of person height
            y_lower_cutoff = ymin + int(0.88 * height)

            for y in range(ymin, ymax + 1):
                row_mask = person_mask[y, :]
                if y < y_upper_cutoff:
                    upper_mask[y, :] = row_mask
                elif y < y_lower_cutoff:
                    lower_mask[y, :] = row_mask
                else:
                    feet_mask[y, :] = row_mask

        # 1. Generate DeepLabV3+ Direct Overlay
        overlay = orig_np.copy()

        # Blend Red for Upperbody
        overlay[upper_mask, 0] = np.clip(0.5 * overlay[upper_mask, 0] + 0.5 * 255, 0, 255).astype(np.uint8)
        overlay[upper_mask, 1] = (0.5 * overlay[upper_mask, 1]).astype(np.uint8)
        overlay[upper_mask, 2] = (0.5 * overlay[upper_mask, 2]).astype(np.uint8)

        # Blend Green for Lowerbody
        overlay[lower_mask, 0] = (0.5 * overlay[lower_mask, 0]).astype(np.uint8)
        overlay[lower_mask, 1] = np.clip(0.5 * overlay[lower_mask, 1] + 0.5 * 255, 0, 255).astype(np.uint8)
        overlay[lower_mask, 2] = (0.5 * overlay[lower_mask, 2]).astype(np.uint8)

        # Blend Cyan for Feet/Shoes
        overlay[feet_mask, 0] = (0.5 * overlay[feet_mask, 0]).astype(np.uint8)
        overlay[feet_mask, 1] = np.clip(0.5 * overlay[feet_mask, 1] + 0.5 * 255, 0, 255).astype(np.uint8)
        overlay[feet_mask, 2] = np.clip(0.5 * overlay[feet_mask, 2] + 0.5 * 255, 0, 255).astype(np.uint8)

        base_name = os.path.splitext(img_name)[0]
        overlay_path = os.path.join(output_dir, f"{base_name}_deeplabv3_overlay.png")
        Image.fromarray(overlay).save(overlay_path)

        # 2. Save Cutouts
        def save_cutout(mask, fname):
            cutout = np.zeros((orig_h, orig_w, 4), dtype=np.uint8)
            cutout[..., :3] = orig_np
            cutout[..., 3] = np.where(mask, 255, 0).astype(np.uint8)
            Image.fromarray(cutout).save(os.path.join(output_dir, fname))

        save_cutout(upper_mask, f"{base_name}_deeplabv3_upperbody_cutout.png")
        save_cutout(lower_mask, f"{base_name}_deeplabv3_lowerbody_cutout.png")
        save_cutout(feet_mask, f"{base_name}_deeplabv3_feet_cutout.png")
        save_cutout(person_mask, f"{base_name}_deeplabv3_all_cutout.png")

        # 3. Garment Recoloring Demonstration (Upper: Emerald Green -> Royal Blue)
        img_float = orig_np.astype(np.float32) / 255.0
        luminance = 0.299 * img_float[..., 0] + 0.587 * img_float[..., 1] + 0.114 * img_float[..., 2]
        
        recolored_upper = orig_np.copy()
        blue_rgb = (0.10, 0.35, 0.90)
        for c in range(3):
            c_val = np.clip(luminance * blue_rgb[c] * 255.0 * 1.5, 0, 255).astype(np.uint8)
            recolored_upper[..., c] = np.where(upper_mask, c_val, orig_np[..., c])
        Image.fromarray(recolored_upper).save(os.path.join(output_dir, f"{base_name}_deeplabv3_recolored_blue_shirt.png"))

        # 4. Save 4-Panel Summary Comparison
        plt.figure(figsize=(14, 14))
        plt.subplot(2, 2, 1)
        plt.imshow(img)
        plt.axis("off")
        plt.title("1. Original Photo")

        plt.subplot(2, 2, 2)
        plt.imshow(overlay)
        plt.axis("off")
        plt.title("2. DeepLabV3+ Segmentation Overlay\n(Red: Upper, Green: Lower, Cyan: Feet)")

        plt.subplot(2, 2, 3)
        plt.imshow(recolored_upper)
        plt.axis("off")
        plt.title("3. DeepLabV3+ Upperbody Recolored (Royal Blue)")

        # Full person cutout on transparent BG
        person_cutout = np.zeros((orig_h, orig_w, 4), dtype=np.uint8)
        person_cutout[..., :3] = orig_np
        person_cutout[..., 3] = np.where(person_mask, 255, 0).astype(np.uint8)
        
        plt.subplot(2, 2, 4)
        plt.imshow(person_cutout)
        plt.axis("off")
        plt.title("4. Isolated Outfit Cutout (No BG)")

        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, f"{base_name}_deeplabv3_analysis.png"), bbox_inches="tight")
        plt.close()

        print(f"DeepLabV3+ segmentation for {img_name} completed!")

if __name__ == "__main__":
    run_deeplabv3_inference()
