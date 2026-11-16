import os
import torch
import torch.nn.functional as F
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

from data.base_dataset import Normalize_image
from utils.saving_utils import load_checkpoint_mgpu
from networks import U2NET

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

image_dir = "input_images"
result_dir = "output_images"
checkpoint_path = os.path.join("trained_checkpoint", "cloth_segm_u2net_latest.pth")

os.makedirs(image_dir, exist_ok=True)
os.makedirs(result_dir, exist_ok=True)

def get_palette(num_cls):
    palette = [0] * (num_cls * 3)
    # 0: Background (black)
    # 1: Upper body (red)
    palette[1 * 3 + 0] = 255
    palette[1 * 3 + 1] = 0
    palette[1 * 3 + 2] = 0

    # 2: Lower body (green)
    palette[2 * 3 + 0] = 0
    palette[2 * 3 + 1] = 255
    palette[2 * 3 + 2] = 0

    # 3: Full body / Dress (yellow)
    palette[3 * 3 + 0] = 255
    palette[3 * 3 + 1] = 255
    palette[3 * 3 + 2] = 0

    return palette

transforms_list = [transforms.ToTensor(), Normalize_image(0.5, 0.5)]
transform_rgb = transforms.Compose(transforms_list)

print("Loading U2NET model architecture and weights...")
net = U2NET(in_ch=3, out_ch=4)
net = load_checkpoint_mgpu(net, checkpoint_path)
net = net.to(device)
net = net.eval()

palette = get_palette(4)

images_list = sorted([f for f in os.listdir(image_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])

if not images_list:
    print(f"No images found in {image_dir}")
else:
    print(f"Found {len(images_list)} images to process...")
    for image_name in tqdm(images_list):
        img_path = os.path.join(image_dir, image_name)
        img = Image.open(img_path).convert("RGB")
        orig_w, orig_h = img.size

        # Model input (resize for model, then resize back output)
        img_resized = img.resize((768, 768), Image.BILINEAR)
        image_tensor = transform_rgb(img_resized)
        image_tensor = torch.unsqueeze(image_tensor, 0).to(device)

        with torch.no_grad():
            output_tensor = net(image_tensor)
            output_tensor = F.log_softmax(output_tensor[0], dim=1)
            output_tensor = torch.max(output_tensor, dim=1, keepdim=True)[1]
            output_tensor = torch.squeeze(output_tensor, dim=0).squeeze(0)
            output_arr = output_tensor.cpu().numpy().astype(np.uint8)

        # Resize output mask to original dimensions
        mask_img = Image.fromarray(output_arr, mode="L").resize((orig_w, orig_h), Image.NEAREST)
        mask_np = np.array(mask_img)

        # Save Palette Color Mask
        paletted_img = mask_img.copy()
        paletted_img.putpalette(palette)
        base_name = os.path.splitext(image_name)[0]
        mask_out_path = os.path.join(result_dir, f"{base_name}_palette_mask.png")
        paletted_img.save(mask_out_path)

        # Save Side-by-Side Visualization
        plt.figure(figsize=(12, 6))
        plt.subplot(1, 2, 1)
        plt.imshow(img)
        plt.axis("off")
        plt.title("Input Photo")

        plt.subplot(1, 2, 2)
        plt.imshow(paletted_img)
        plt.axis("off")
        plt.title("U2NET Cloth Parsing\n(Red: Upper, Green: Lower, Yellow: Full Body)")
        plt.tight_layout()
        plt.savefig(os.path.join(result_dir, f"{base_name}_visualization.png"), bbox_inches="tight")
        plt.close()

        # Save RGBA Garment Cutouts
        orig_np = np.array(img)
        # Upper Body (1)
        upper_cutout = np.zeros((orig_h, orig_w, 4), dtype=np.uint8)
        upper_cutout[..., :3] = orig_np
        upper_cutout[..., 3] = np.where(mask_np == 1, 255, 0).astype(np.uint8)
        Image.fromarray(upper_cutout).save(os.path.join(result_dir, f"{base_name}_cutout_upper.png"))

        # Lower Body (2)
        lower_cutout = np.zeros((orig_h, orig_w, 4), dtype=np.uint8)
        lower_cutout[..., :3] = orig_np
        lower_cutout[..., 3] = np.where(mask_np == 2, 255, 0).astype(np.uint8)
        Image.fromarray(lower_cutout).save(os.path.join(result_dir, f"{base_name}_cutout_lower.png"))

        # All Clothes / Person Cutout (1, 2, 3)
        all_cutout = np.zeros((orig_h, orig_w, 4), dtype=np.uint8)
        all_cutout[..., :3] = orig_np
        all_cutout[..., 3] = np.where(mask_np > 0, 255, 0).astype(np.uint8)
        Image.fromarray(all_cutout).save(os.path.join(result_dir, f"{base_name}_cutout_all_clothes.png"))

        print(f"Processed {image_name} successfully!")

print("All inference completed!")