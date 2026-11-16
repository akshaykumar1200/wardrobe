import os
from PIL import Image, ImageDraw, ImageFont

artifact_dir = r"C:\Users\Lenovo\.gemini\antigravity-ide\brain\7bc1c6fd-8c3d-44cd-92a0-194ebf0c23ac"

# Load images
orig = Image.open(os.path.join(artifact_dir, "0_original.jpg")).convert("RGB")
matte = Image.open(os.path.join(artifact_dir, "1_subject_matte.png")).convert("RGB")
seg = Image.open(os.path.join(artifact_dir, "1_segmentation_map.png")).convert("RGB")
top = Image.open(os.path.join(artifact_dir, "cutout_top.png")).convert("RGBA")
trousers = Image.open(os.path.join(artifact_dir, "cutout_trousers.png")).convert("RGBA")
shoes = Image.open(os.path.join(artifact_dir, "cutout_shoes.png")).convert("RGBA")

# Create a sleek dark-mode showcase card
canvas_w, canvas_h = 1200, 900
bg_color = (18, 20, 24)
card_bg = (28, 32, 40)
accent_color = (74, 144, 226)

canvas = Image.new("RGBA", (canvas_w, canvas_h), bg_color + (255,))
draw = ImageDraw.Draw(canvas)

# Header
draw.rectangle([(0, 0), (canvas_w, 60)], fill=(24, 28, 36))
draw.text((30, 20), "AI WARDROBE EXTRACTION PIPELINE - STAGE BY STAGE", fill=(255, 255, 255))

def place_image_with_card(img, box, title, subtitle="", color_hex=None):
    x0, y0, x1, y1 = box
    draw.rounded_rectangle([(x0, y0), (x1, y1)], radius=12, fill=card_bg, outline=(45, 52, 65), width=2)
    draw.text((x0 + 15, y0 + 12), title, fill=(230, 235, 245))
    if subtitle:
        draw.text((x0 + 15, y0 + 30), subtitle, fill=(150, 165, 185))
    if color_hex:
        # Draw color chip
        draw.rounded_rectangle([(x1 - 85, y0 + 12), (x1 - 15, y0 + 36)], radius=6, fill=color_hex, outline=(255, 255, 255), width=1)

    # Content area inside card
    pad = 12
    top_pad = 50
    cw = (x1 - x0) - 2 * pad
    ch = (y1 - y0) - top_pad - pad
    
    # Scale image to fit cw, ch preserving aspect
    scale = min(cw / img.width, ch / img.height)
    nw, nh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
    scaled = img.resize((nw, nh), Image.LANCZOS)
    
    px = x0 + pad + (cw - nw) // 2
    py = y0 + top_pad + (ch - nh) // 2
    
    if img.mode == "RGBA":
        canvas.paste(scaled, (px, py), scaled)
    else:
        canvas.paste(scaled, (px, py))

# Top row: 3 detection stages
w_col = 360
h_row1 = 360
gap = 25
top_y = 80

place_image_with_card(orig, (30, top_y, 30 + w_col, top_y + h_row1), "1. Original Upload", "Intake & EXIF Stripped")
place_image_with_card(matte, (30 + w_col + gap, top_y, 30 + 2*w_col + gap, top_y + h_row1), "2. BiRefNet Matte", "Subject Silhouette Alpha")
place_image_with_card(seg, (30 + 2*(w_col + gap), top_y, 30 + 3*w_col + 2*gap, top_y + h_row1), "3. SegFormer Map", "Multi-Garment Parsing")

# Bottom row: 3 extracted cutouts
h_row2 = 400
bottom_y = top_y + h_row1 + 25

place_image_with_card(top, (30, bottom_y, 30 + w_col, bottom_y + h_row2), "Topwear (Top)", "Conf: 98.2% | Vintage Green", "#2c524a")
place_image_with_card(trousers, (30 + w_col + gap, bottom_y, 30 + 2*w_col + gap, bottom_y + h_row2), "Bottomwear (Trousers)", "Conf: 95.8% | Denim Blue", "#29374c")
place_image_with_card(shoes, (30 + 2*(w_col + gap), bottom_y, 30 + 3*w_col + 2*gap, bottom_y + h_row2), "Shoes (Footwear)", "Conf: 71.7% | Off-White Snkrs", "#919090")

out_path = os.path.join(artifact_dir, "showcase_gallery.png")
canvas.convert("RGB").save(out_path, quality=95)
print(f"Saved showcase gallery to {out_path}")
