import os
import requests

url = "https://huggingface.co/maiti/cloth-segmentation/resolve/main/cloth_segm_u2net_latest.pth"
dest = os.path.join("trained_checkpoint", "cloth_segm_u2net_latest.pth")

os.makedirs("trained_checkpoint", exist_ok=True)
print(f"Downloading pre-trained U2NET cloth segmentation weights from Hugging Face ({url})...")

response = requests.get(url, stream=True)
response.raise_for_status()

total_size = int(response.headers.get('content-length', 0))
print(f"Total size: {total_size / (1024*1024):.2f} MB")

with open(dest, "wb") as f:
    downloaded = 0
    for chunk in response.iter_content(chunk_size=65536):
        if chunk:
            f.write(chunk)
            downloaded += len(chunk)

print(f"Successfully downloaded {os.path.getsize(dest)} bytes to {dest}!")
