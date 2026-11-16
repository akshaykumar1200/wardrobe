import requests
from PIL import Image
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
from transformers import SegformerImageProcessor, AutoModelForSemanticSegmentation

def main():
    print("Loading model and processor: mattmdjaga/segformer_b2_clothes...")
    processor = SegformerImageProcessor.from_pretrained("mattmdjaga/segformer_b2_clothes")
    model = AutoModelForSemanticSegmentation.from_pretrained("mattmdjaga/segformer_b2_clothes")

    url = "https://plus.unsplash.com/premium_photo-1673210886161-bfcc40f54d1f?ixlib=rb-4.0.3&ixid=MnwxMjA3fDB8MHxzZWFyY2h8MXx8cGVyc29uJTIwc3RhbmRpbmd8ZW58MHx8MHx8&w=1000&q=80"

    print("Fetching image...")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    image = Image.open(response.raw)

    print(f"Image size: {image.size}")
    inputs = processor(images=image, return_tensors="pt")

    print("Running inference...")
    with torch.no_grad():
        outputs = model(**inputs)
    logits = outputs.logits.cpu()

    print("Upsampling segmentation logits...")
    upsampled_logits = nn.functional.interpolate(
        logits,
        size=image.size[::-1], # (height, width)
        mode="bilinear",
        align_corners=False,
    )

    pred_seg = upsampled_logits.argmax(dim=1)[0]
    
    print("Saving segmentation result to output_segmentation.png...")
    plt.figure(figsize=(10, 10))
    plt.imshow(pred_seg)
    plt.axis("off")
    plt.title("SegFormer Clothes Segmentation")
    plt.savefig("output_segmentation.png", bbox_inches="tight")
    print("Done! Result saved to output_segmentation.png")

if __name__ == "__main__":
    main()
