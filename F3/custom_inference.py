import os
import torch
import torch.nn.functional as F
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt

from data.base_dataset import Normalize_image
from utils.saving_utils import load_checkpoint_mgpu
from networks import U2NET

device = "cuda" if torch.cuda.is_available() else "cpu"

def run_custom_u2net(img_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Loading input image: {img_path}")
    orig_img = Image.open(img_path).convert("RGB")
    orig_w, orig_h = orig_img.size
    orig_np = np.array(orig_img)

    checkpoint_path = os.path.join("trained_checkpoint", "cloth_segm_u2net_latest.pth")
    
    print("Loading U2NET model...")
    net = U2NET(in_ch=3, out_ch=4)
    net = load_checkpoint_mgpu(net, checkpoint_path)
    net = net.to(device)
    net = net.eval()

    transforms_list = [transforms.ToTensor(), Normalize_image(0.5, 0.5)]
    transform_rgb = transforms.Compose(transforms_list)

    img_resized = orig_img.resize((768, 768), Image.BILINEAR)
    image_tensor = transform_rgb(img_resized)
    image_tensor = torch.unsqueeze(image_tensor, 0).to(device)

    print("Executing U2NET inference...")
    with torch.no_grad():
        output_tensor = net(image_tensor)
        output_tensor = F.log_softmax(output_tensor[0], dim=1)
        output_tensor = torch.max(output_tensor, dim=1, keepdim=True)[1]
        output_tensor = torch.squeeze(output_tensor, dim=0).squeeze(0)
        output_arr = output_tensor.cpu().numpy().astype(np.uint8)

    # Resize mask to original size
    mask_img = Image.fromarray(output_arr, mode="L").resize((orig_w, orig_h), Image.NEAREST)
    mask_np = np.array(mask_img)

    # 1. Create Direct Mask Overlay on original photo
    overlay = orig_np.copy()
    upper_mask = (mask_np == 1)
    lower_mask = (mask_np == 2)
    full_mask = (mask_np == 3)

    # Blend Red for Upper clothes
    overlay[upper_mask, 0] = np.clip(0.5 * overlay[upper_mask, 0] + 0.5 * 255, 0, 255).astype(np.uint8)
    overlay[upper_mask, 1] = (0.5 * overlay[upper_mask, 1]).astype(np.uint8)
    overlay[upper_mask, 2] = (0.5 * overlay[upper_mask, 2]).astype(np.uint8)

    # Blend Green for Lower clothes
    overlay[lower_mask, 0] = (0.5 * overlay[lower_mask, 0]).astype(np.uint8)
    overlay[lower_mask, 1] = np.clip(0.5 * overlay[lower_mask, 1] + 0.5 * 255, 0, 255).astype(np.uint8)
    overlay[lower_mask, 2] = (0.5 * overlay[lower_mask, 2]).astype(np.uint8)

    # Save Overlay Image
    overlay_path = os.path.join(output_dir, "u2net_direct_overlay.png")
    Image.fromarray(overlay).save(overlay_path)
    print(f"Saved direct overlay to {overlay_path}")

    # 2. U2NET Garment Recoloring Demonstration (Upper: Black, Red, Blue; Lower: Black, Grey)
    img_float = orig_np.astype(np.float32) / 255.0
    luminance = 0.299 * img_float[..., 0] + 0.587 * img_float[..., 1] + 0.114 * img_float[..., 2]

    # Recolor Upper Clothes to Crimson Red
    recolored_upper = orig_np.copy()
    red_rgb = (0.85, 0.10, 0.15)
    for c in range(3):
        c_val = np.clip(luminance * red_rgb[c] * 255.0 * 1.5, 0, 255).astype(np.uint8)
        recolored_upper[..., c] = np.where(upper_mask, c_val, orig_np[..., c])
    Image.fromarray(recolored_upper).save(os.path.join(output_dir, "u2net_recolored_red_shirt.png"))

    # Recolor Lower Clothes (Jeans to Dark Black Denim)
    recolored_pants = orig_np.copy()
    black_rgb = (0.12, 0.12, 0.15)
    for c in range(3):
        c_val = np.clip(luminance * black_rgb[c] * 255.0 * 1.3, 0, 255).astype(np.uint8)
        recolored_pants[..., c] = np.where(lower_mask, c_val, orig_np[..., c])
    Image.fromarray(recolored_pants).save(os.path.join(output_dir, "u2net_recolored_black_jeans.png"))

    # Save 4-panel comparison grid
    plt.figure(figsize=(14, 14))
    plt.subplot(2, 2, 1)
    plt.imshow(orig_img)
    plt.axis("off")
    plt.title("1. Original Input Photo")

    plt.subplot(2, 2, 2)
    plt.imshow(overlay)
    plt.axis("off")
    plt.title("2. U2NET Garment Mask Overlay\n(Red: Upper, Green: Lower)")

    plt.subplot(2, 2, 3)
    plt.imshow(recolored_upper)
    plt.axis("off")
    plt.title("3. U2NET Upper-Clothes Recolored (Red)")

    plt.subplot(2, 2, 4)
    plt.imshow(recolored_pants)
    plt.axis("off")
    plt.title("4. U2NET Lower-Clothes Recolored (Black)")

    plt.tight_layout()
    grid_path = os.path.join(output_dir, "u2net_full_analysis.png")
    plt.savefig(grid_path, bbox_inches="tight")
    plt.close()
    print(f"Saved full U2NET analysis to {grid_path}")

if __name__ == "__main__":
    img = os.path.join("input_images", "user_photo.jpg")
    out = "output_images"
    run_custom_u2net(img, out)
