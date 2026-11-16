# Task for Claude: set up and start the cut-out service on this laptop

You are Claude Code, running on a Windows laptop with an NVIDIA GeForce
RTX 3060 Laptop GPU (6 GB). Please carry out every step below yourself, in
order, and check each one before moving on. The person at this laptop is not a
developer, so do the work and only ask them for the few things marked
**HUMAN**.

## What this is for

Akshay runs a website (my-style-memory-closet.lovable.app). When someone
uploads an outfit photo, the website sends it to a small service that must run
on this laptop. The service cuts out every garment and sends the pictures back.
On this laptop the GPU should also draw a clean product-style picture of the
top, using a model called TryOffDiff.

When you finish, this must be true:

1. The service answers at `http://127.0.0.1:8000/healthz` with `{"ok":true}`.
2. A public tunnel link to it exists, and you have given that link to the human
   to send to Akshay.
3. TryOffDiff runs on the GPU (`models ready on cuda`) and the service is set to
   use it. If the TryOffDiff code is not on GitHub yet, items 1 and 2 are
   enough, and you say so in your report.

## Rules

- **Secrets.** Never print, read aloud, or paste the contents of `.env`, the
  cut-out key, or any Hugging Face token. Do not ask the human to type the key
  into this chat. Where a secret is needed, the human runs one command in their
  own PowerShell window (see step 4).
- **Git.** Only `git clone` and `git pull`. Do not commit, push, or change
  branches.
- **System settings.** Do not change the PowerShell execution policy, antivirus
  or firewall settings. If Windows blocks a script, stop and report it.
- **Check before you redo.** Each step says how to tell it is already done. If
  it is, skip it. Never delete or overwrite an existing `.env`.
- **When a step fails,** read the error, try the obvious fix once, and if it
  still fails, stop and report the exact error text. Do not improvise around a
  failed step.
- **Long commands.** Installs and downloads take many minutes. Run them in the
  background and wait for them to finish. Do not start a second copy.
- PowerShell here does not accept `&&`. Chain commands with `;`.

## Step 1. Check the tools

Run each check. Install only what is missing, then open a fresh shell so the
new command is found.

| Tool | Check | Install if missing |
|---|---|---|
| Git | `git --version` | `winget install -e --id Git.Git` |
| Python 3.11 | `py -3.11 --version` | `winget install -e --id Python.Python.3.11` |
| cloudflared | `cloudflared --version` | `winget install -e --id Cloudflare.cloudflared` |
| NVIDIA driver | `nvidia-smi --query-gpu=name,memory.total --format=csv` | **HUMAN** installs the driver from nvidia.com |

Write down the GPU name and memory for your report.

## Step 2. Get the code

- Already done if `C:\wardrobe-repo\wardrobe\backend` exists. Then just run
  `git pull` in `C:\wardrobe-repo`.
- Otherwise:

```powershell
git clone https://github.com/akshaykumar1200/wardrobe.git C:\wardrobe-repo
```

If the clone asks for a login or says the repository is not found, stop.
**HUMAN** needs access to the repo from Akshay.

## Step 3. Install the service's packages

- Already done if this prints a version without an error:

```powershell
C:\wardrobe-repo\wardrobe\venv\Scripts\python.exe -c "import uvicorn, torch, transformers; print(torch.__version__)"
```

- Otherwise:

```powershell
cd C:\wardrobe-repo\wardrobe
py -3.11 -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
```

The service's own environment uses the CPU build of PyTorch on purpose. The GPU
is used by the separate environment in step 6.

## Step 4. Settings file (HUMAN step)

- Already done if `C:\wardrobe-repo\wardrobe\.env` exists. Check only that the
  file exists. Do not open it.
- Otherwise, ask the human to open their own PowerShell window and run this.
  They paste the cut-out key that Akshay sent them privately:

```powershell
cd C:\wardrobe-repo\wardrobe
$env:CUT_KEY = Read-Host "Paste the cut-out key from Akshay"
.\venv\Scripts\python.exe -c "import os,secrets; k=os.environ['CUT_KEY'].strip(); open('.env','w').write('CUTOUT_API_KEY='+k+'\nSESSION_SECRET='+secrets.token_urlsafe(32)+'\nADMIN_PASSWORD='+secrets.token_urlsafe(16)+'\n')"
Remove-Item Env:CUT_KEY
```

Wait until they say it is done, then confirm the file exists.

## Step 5. Download the cut-out models (about 1 GB)

```powershell
cd C:\wardrobe-repo\wardrobe
.\venv\Scripts\python.exe -m deploy.prefetch_models
```

It is safe to run again. When the models are already there it finishes quickly.

## Step 6. Turn on the GPU drawing (TryOffDiff)

First check that the code is there. Both of these files must exist:

- `C:\wardrobe-repo\wardrobe\tryoff\run_tryoff.py`
- `C:\wardrobe-repo\wardrobe\backend\product_shot.py`

**If either is missing, the code is not on GitHub yet. Create it yourself from
the appendix at the end of this file, test it, and then carry on with 6a.**

### 6-pre. Create and test the code (only when it is missing)

1. Run `git status --short` in `C:\wardrobe-repo`. `wardrobe/backend/config.py`,
   `wardrobe/backend/routers/cutout.py` and `wardrobe/tests/test_cutout.py`
   must be unmodified. If any of them has local changes, stop and report.
2. Create each file in the appendix with exactly the content given. Copy the
   code as it is. Do not rewrite, reformat or "improve" it.
3. Make the one-line change to `backend/config.py` and append the tests to
   `tests/test_cutout.py`, as the appendix describes.
4. Run the tests:

```powershell
cd C:\wardrobe-repo\wardrobe
.\venv\Scripts\python.exe -m pytest tests/test_cutout.py -q
```

   Every test must pass. The three new ones are
   `test_top_becomes_a_drawn_product_picture_in_its_real_colour`,
   `test_failed_drawing_keeps_the_real_cutout` and
   `test_two_tops_keep_their_cutouts`. If a test fails, compare your files with
   the appendix again before changing anything. If it still fails, stop and
   report the failure text.
5. Do not commit or push these files. Mention in your report that you created
   them locally.

If a later `git pull` complains that these files would be overwritten, Akshay
has pushed the same code. Then run this and pull again:

```powershell
cd C:\wardrobe-repo\wardrobe
git checkout -- backend/config.py backend/routers/cutout.py tests/test_cutout.py
Remove-Item backend\product_shot.py, tryoff\run_tryoff.py, tryoff\requirements.txt, tryoff\.gitignore
git pull
```

### 6a. Make the environment

Skip if `tryoff\tryoff-venv\Scripts\python.exe` exists.

```powershell
cd C:\wardrobe-repo\wardrobe\tryoff
py -3.11 -m venv tryoff-venv
.\tryoff-venv\Scripts\python.exe -m pip install --upgrade pip
```

### 6b. Install the GPU build of PyTorch (about 2.5 GB), then the other packages

```powershell
cd C:\wardrobe-repo\wardrobe\tryoff
.\tryoff-venv\Scripts\python.exe -m pip install torch==2.2.2 torchvision==0.17.2 --index-url https://download.pytorch.org/whl/cu121
.\tryoff-venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 6c. Check the GPU is found

This must print `True` and the GPU name:

```powershell
.\tryoff-venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

If it prints `False`, stop and report. The usual cause is an old NVIDIA driver.

### 6d. Run the model once

This downloads about 5 GB the first time and proves the GPU path works.

Ask the human for a photo of a person wearing a top and save it as
`C:\wardrobe-repo\wardrobe\tryoff\test.jpg`. If they have none to hand, make a
plain test image instead. The picture will be meaningless, but the run still
proves the download and the GPU:

```powershell
.\tryoff-venv\Scripts\python.exe -c "from PIL import Image; Image.new('RGB',(512,768),(60,120,90)).save('test.jpg')"
```

Then:

```powershell
cd C:\wardrobe-repo\wardrobe\tryoff
.\tryoff-venv\Scripts\python.exe run_tryoff.py 30 42 test.jpg:test_out.png
```

Check all three:

- The output contains `models ready on cuda`.
- It ends with `saved test_out.png in <N>s`. Note N for your report.
- `test_out.png` exists.

If the download fails with `401` or `403`, the **HUMAN** signs in with their
own free Hugging Face account by running
`.\tryoff-venv\Scripts\huggingface-cli.exe login` in their own window, and
accepts the model terms on huggingface.co. Then run 6d again.

If it fails with a CUDA out-of-memory error, ask the human to close games and
browsers, and run it once more. If it still fails, stop and report.

### 6e. Tell the service to use it

First check whether it is already set, without printing the file:

```powershell
cd C:\wardrobe-repo\wardrobe
Select-String -Path .env -Pattern "^TRYOFF_PYTHON=" -Quiet
```

If that prints `False` or nothing, add the line:

```powershell
Add-Content .env "TRYOFF_PYTHON=C:/wardrobe-repo/wardrobe/tryoff/tryoff-venv/Scripts/python.exe"
```

## Step 7. Start the service

If something already answers at `http://127.0.0.1:8000/healthz`, an old copy is
running. Stop that process first, so the new settings are loaded.

Start it in the background and keep it running:

```powershell
cd C:\wardrobe-repo\wardrobe; .\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

It takes about a minute to load. Then check:

```powershell
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/healthz).Content
```

It must print `{"ok":true}`.

## Step 8. Start the tunnel

Start it in the background and keep it running:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

Read its output and find the line with a link ending in `.trycloudflare.com`.
Check the link works from outside, replacing THE-LINK with it:

```powershell
(Invoke-WebRequest -UseBasicParsing https://THE-LINK/healthz).Content
```

It must print `{"ok":true}`. The link is not a secret. Give it to the human.

## Step 9. Hand over (HUMAN and Akshay)

Tell the human, in plain words:

1. Send the tunnel link to Akshay.
2. Akshay pastes it into Lovable → Settings → Secrets → `LAPTOP_CUTOUT_URL`,
   with no `/api/cutout` and no slash at the end. He leaves
   `LAPTOP_CUTOUT_KEY` as it is.
3. Akshay uploads a photo on the website.
4. Keep this laptop on, plugged in, and awake. The link changes if the tunnel
   restarts, and then Akshay needs the new one.

Offer to stop the laptop sleeping while plugged in, and run this only if the
human agrees:

```powershell
powercfg /change standby-timeout-ac 0
```

## Step 10. Confirm a real upload

After Akshay uploads a photo, read the service's output. A good run looks like:

```
cutout 900x1600 -> [('Top', 310, 420, 0.0, 'drawn'), ('Trousers', 272, 499, 0.0, 'cut-out')] in 34s
"POST /api/cutout HTTP/1.1" 200 OK
```

What the results mean:

| You see | Meaning |
|---|---|
| `200 OK`, and the top says `'drawn'` | Everything works, GPU included. |
| `200 OK`, the top says `'cut-out'`, and `product shot failed` appears above it | The service works, but the GPU drawing failed and the real cut-out was sent. Report those lines. |
| `200 OK`, with no `'drawn'` or `'cut-out'` words | The service runs code without TryOffDiff (step 6 was skipped). |
| `401` | The key in `.env` does not match the one in Lovable. Akshay must resend the key. |
| `503` | `.env` has no `CUTOUT_API_KEY`. Redo step 4. |
| Nothing at all | The link in Lovable is wrong or old. |

A photo with two tops (a shirt and a jacket) always gives `'cut-out'` for both.
That is expected.

## Final report

End with a short report for the human to forward to Akshay:

- GPU name and memory.
- For each step 1 to 10: done, skipped (already done),
  created (for the code in the appendix), or failed, with the exact error
  text for any failure.
- The tunnel link.
- Whether TryOffDiff ran on `cuda`, and how many seconds the test run took.
- Anything you could not check.

## Appendix: the TryOffDiff code

Use this only for step 6-pre. All paths are inside `C:\wardrobe-repo\wardrobe`.

### File 1 (new): `tryoff/run_tryoff.py`

Runs the TryOffDiff model on one photo. Uses the GPU in half precision when one
is found.

```python
"""Port of the authors' TryOffDiff demo (rizavelioglu/tryoffdiff Space, app.py),
upper-body model only. Runs on an NVIDIA GPU when one is found, else the CPU. Same transforms, scheduler, guidance and decoding as the demo.

Two deliberate differences, both memory-only:
- the UNet is built from its config on the meta device instead of downloading the
  full Stable Diffusion v1.4 weights, which load_state_dict(strict=True) overwrites anyway
- the checkpoint is memory-mapped and assigned, so ~3.4 GB is not committed twice

usage: python run_tryoff.py STEPS SEED in1.jpg:out1.png [in2.jpg:out2.png ...]
"""

import sys
import time

import torch
import torchvision.transforms.v2 as transforms
from diffusers import AutoencoderKL, EulerDiscreteScheduler, UNet2DConditionModel
from huggingface_hub import hf_hub_download
from torch import nn
from torchvision.io import read_image
from torchvision.utils import make_grid
from transformers import SiglipImageProcessor, SiglipVisionModel

torch.set_num_threads(8)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
# Half precision on the GPU: the UNet alone is 3.4 GB in full precision, too much for a 6 GB card.
# The VAE stays in full precision, where it is known not to produce black images.
DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32
REPO = "rizavelioglu/tryoffdiff"


class PadToSquare:
    def __call__(self, img):
        _, h, w = img.shape
        side = max(h, w)
        ph, pw = (side - h) // 2, (side - w) // 2
        return transforms.functional.pad(img, (pw, ph, side - w - pw, side - h - ph), padding_mode="edge")


class TryOffDiffv2Single(nn.Module):
    def __init__(self):
        super().__init__()
        cfg = UNet2DConditionModel.load_config("CompVis/stable-diffusion-v1-4", subfolder="unet")
        self.unet = UNet2DConditionModel.from_config(cfg)
        self.proj = nn.Linear(1024, 77)
        self.norm = nn.LayerNorm(768)

    def forward(self, noisy_latents, t, cond_emb):
        cond_emb = self.proj(cond_emb.transpose(1, 2))
        cond_emb = self.norm(cond_emb.transpose(1, 2))
        return self.unet(noisy_latents, t, encoder_hidden_states=cond_emb).sample


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    steps, seed = int(sys.argv[1]), int(sys.argv[2])
    jobs = [a.split(":", 1) if a.count(":") == 1 else a.rsplit(":", 1) for a in sys.argv[3:]]

    log("downloading/locating weights")
    ckpt = hf_hub_download(REPO, "tryoffdiffv2_upper.pth")
    sched_cfg = hf_hub_download(REPO, "scheduler/scheduler_config_v2.json")

    log("building model")
    with torch.device("meta"):
        model = TryOffDiffv2Single()
    state = torch.load(ckpt, map_location="cpu", weights_only=True, mmap=True)
    # Saved from a torch.compile()d model, so every key carries this prefix.
    state = {k.removeprefix("_orig_mod."): v for k, v in state.items()}
    model.load_state_dict(state, strict=True, assign=True)
    left = [n for n, t in list(model.named_parameters()) + list(model.named_buffers()) if t.is_meta]
    assert not left, f"tensors still on meta device: {left[:5]}"
    model.eval().to(DEVICE, DTYPE)

    enc_ckpt = "google/siglip-base-patch16-512"
    processor = SiglipImageProcessor.from_pretrained(enc_ckpt, do_resize=False, do_rescale=False, do_normalize=False)
    encoder = SiglipVisionModel.from_pretrained(enc_ckpt).eval().to(DEVICE, DTYPE)
    vae = AutoencoderKL.from_pretrained("stabilityai/sd-vae-ft-mse").eval().to(DEVICE)
    scheduler = EulerDiscreteScheduler.from_pretrained(sched_cfg)
    scheduler.is_scale_input_called = True
    to_input = transforms.Compose([
        PadToSquare(),
        transforms.Resize((512, 512)),
        transforms.ToDtype(torch.float32, scale=True),
        transforms.Normalize(mean=[0.5], std=[0.5]),
    ])
    guidance = 2.0
    log(f"models ready on {DEVICE}")

    for src, dst in jobs:
        t0 = time.time()
        with torch.no_grad():
            scheduler.set_timesteps(steps, device=DEVICE)
            x = torch.randn(1, 4, 64, 64, generator=torch.Generator().manual_seed(seed)).to(DEVICE, DTYPE)
            inputs = processor(images=to_input(read_image(src)), return_tensors="pt")
            cond = encoder(inputs["pixel_values"].to(DEVICE, DTYPE)).last_hidden_state
            uncond = torch.zeros_like(cond)
            for i, t in enumerate(scheduler.timesteps):
                s = time.time()
                pred = model(torch.cat([x] * 2).to(DTYPE), t, torch.cat([uncond, cond])).chunk(2)
                pred = pred[0] + guidance * (pred[1] - pred[0])
                out = scheduler.step(pred, t, x)
                x = out.prev_sample
                log(f"{dst.rsplit('/', 1)[-1]} step {i + 1}/{steps} ({time.time() - s:.1f}s)")
            decoded = vae.decode(1 / vae.config.scaling_factor * out.pred_original_sample.float()).sample
        img = transforms.ToPILImage()(make_grid((decoded.cpu() / 2 + 0.5), nrow=1, normalize=True, scale_each=True))
        img.save(dst)
        log(f"saved {dst} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
```

### File 2 (new): `tryoff/requirements.txt`

```text
# Versions that produced the test sheet. torch and torchvision are installed
# separately (CPU or GPU build), see TRYOFF_SETUP.md.
diffusers==0.27.2
transformers==4.48.3
huggingface_hub==0.25.2
accelerate==1.15.0
safetensors==0.8.0
numpy==1.26.4
scipy==1.17.1
opencv-python==4.11.0.86
Pillow==9.5.0
```

### File 3 (new): `tryoff/.gitignore`

Keeps personal photos and the environment out of git.

```text
# Keep the environment, personal photos and outputs out of git.
tryoff-venv/
out/
*.jpg
*.jpeg
*.png
```

### File 4 (new): `backend/product_shot.py`

Starts `run_tryoff.py` as a separate process, waits for it, and repaints the
drawing in the garment's real colours.

```python
"""Product-style picture of a top, drawn by TryOffDiff in its own Python environment.

TryOffDiff needs newer torch/diffusers than this service pins, so it runs as a
separate process (tryoff/run_tryoff.py) and this module only starts it, waits,
and repaints its output with the garment's real colours. Off unless
TRYOFF_PYTHON is set, and every failure returns None so the caller keeps the
real cut-out.
"""

import os
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from backend.config import settings

SCRIPT = Path(__file__).resolve().parents[1] / "tryoff" / "run_tryoff.py"
STEPS, SEED = 30, 42
# The website gives the whole request 90 s; past this the cut-out is sent instead.
DEADLINE_S = 70


class ProductShot:
    """One TryOffDiff run. Started before the cut-out so both work at the same time."""

    def __init__(self, photo: Image.Image):
        self._started = time.monotonic()
        self._tmp = tempfile.TemporaryDirectory()
        self._dir = Path(self._tmp.name)
        photo.convert("RGB").save(self._dir / "in.jpg", quality=95)
        self._log = open(self._dir / "log.txt", "w")
        # Plain file names + cwd: the script splits its argument on ":", which a C:\ path breaks.
        # shortcut: loads the model on every upload (~15 s on a GPU); keep a warm worker if uploads get frequent.
        self._proc = subprocess.Popen(
            [settings.TRYOFF_PYTHON, str(SCRIPT), str(STEPS), str(SEED), "in.jpg:out.png"],
            cwd=self._dir, stdout=self._log, stderr=subprocess.STDOUT,
            env={**os.environ, "HF_HUB_OFFLINE": "1"},  # models are fetched once by hand, never mid-upload
        )

    def result(self) -> Image.Image | None:
        """Blocks until the picture is ready or the deadline passes."""
        try:
            code = self._proc.wait(max(1.0, DEADLINE_S - (time.monotonic() - self._started)))
            if code != 0:
                raise RuntimeError(f"exit code {code}")
            with Image.open(self._dir / "out.png") as img:
                return img.convert("RGB")
        except Exception as exc:
            self._log.flush()
            tail = (self._dir / "log.txt").read_text(errors="replace")[-600:]
            print(f"product shot failed ({exc!r}), keeping the cut-out. Last output:\n{tail}", flush=True)
            return None
        finally:
            self.close()

    def close(self):
        if self._proc.poll() is None:
            self._proc.kill()
            self._proc.wait()
        self._log.close()
        self._tmp.cleanup()


def start(photo: Image.Image) -> ProductShot | None:
    if not settings.TRYOFF_PYTHON:
        return None
    try:
        return ProductShot(photo)
    except Exception as exc:
        print(f"product shot could not start ({exc!r}), keeping the cut-out", flush=True)
        return None


def _largest(mask: np.ndarray) -> np.ndarray:
    labels, n = ndimage.label(mask)
    if n == 0:
        return mask
    sizes = ndimage.sum(mask, labels, range(1, n + 1))
    return labels == (int(np.argmax(sizes)) + 1)


def recolour(generated: Image.Image, cutout: Image.Image) -> Image.Image | None:
    """Repaint the drawn garment with the real cut-out's colours, on a transparent background.

    TryOffDiff gets the shape right but the colour too bright; each Lab channel of
    the drawing is quantile-mapped onto the real garment's pixels.
    """
    from skimage.color import lab2rgb, rgb2lab

    real = np.asarray(cutout.convert("RGBA"))
    # Edge pixels blend into skin and background; sample the inside of the garment.
    inside = ndimage.binary_erosion(real[..., 3] > 200, iterations=3)
    if inside.sum() < 50:
        inside = real[..., 3] > 200
    if inside.sum() < 50:
        return None
    ref = rgb2lab(real[..., :3][inside].reshape(-1, 1, 3) / 255.0).reshape(-1, 3)

    arr = np.asarray(generated.convert("RGB"))
    border = np.concatenate([arr[:8].reshape(-1, 3), arr[-8:].reshape(-1, 3),
                             arr[:, :8].reshape(-1, 3), arr[:, -8:].reshape(-1, 3)])
    distance = np.linalg.norm(arr.astype(np.float32) - np.median(border, axis=0), axis=2)
    mask = _largest(ndimage.binary_fill_holes(distance > 30))
    # A drawing that is nearly empty or fills the frame is not a garment on a plain background.
    if not 0.05 < mask.mean() < 0.95:
        return None

    lab = rgb2lab(arr[mask].reshape(-1, 1, 3) / 255.0).reshape(-1, 3)
    fixed = np.empty_like(lab)
    for c in range(3):
        rank = np.argsort(np.argsort(lab[:, c])) / max(len(lab) - 1, 1)
        fixed[:, c] = np.quantile(ref[:, c], rank)
    out = np.zeros((*arr.shape[:2], 4), np.uint8)
    out[..., :3] = arr
    out[..., :3][mask] = (np.clip(lab2rgb(fixed.reshape(-1, 1, 3)).reshape(-1, 3), 0, 1) * 255).round()
    out[..., 3] = (np.clip(ndimage.gaussian_filter(mask.astype(np.float32), 1) * 2 - 0.5, 0, 1) * 255).round()

    ys, xs = np.nonzero(out[..., 3])
    return Image.fromarray(out).crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
```

### File 5 (replace the whole file): `backend/routers/cutout.py`

```python
import asyncio
import base64
import hashlib
import io
import secrets
import time

from fastapi import APIRouter, File, Header, HTTPException, Request, UploadFile
from PIL import Image
from starlette.concurrency import run_in_threadpool

from backend import product_shot
from backend.auth import limiter
from backend.config import settings
from backend.segmenter import extract_garments
from backend.storage import capture_crops, validate_image

router = APIRouter(prefix="/api/cutout", tags=["cutout"])

# The caller may send the same photo several times at once (one call per piece it
# found); each run takes ~30 s of CPU, so identical photos share one run and its
# result is reused for a short while. shortcut: per-process, fine for one laptop worker.
REUSE_SECONDS = 300
_jobs: dict[str, tuple[float, asyncio.Task]] = {}


@router.post("")
@limiter.limit("20/minute")
async def cutout_photo(
    request: Request,
    image: UploadFile = File(...),
    x_cutout_key: str | None = Header(None, alias="X-Cutout-Key"),
):
    if not settings.CUTOUT_API_KEY:
        raise HTTPException(503, "Cut-out service is not configured.")
    if x_cutout_key is None or not secrets.compare_digest(
        x_cutout_key.encode("utf-8"), settings.CUTOUT_API_KEY.encode("utf-8")
    ):
        raise HTTPException(401, "Invalid cut-out key")

    raw = await image.read()
    if not raw:
        raise HTTPException(400, "Empty upload file")
    img_clean = validate_image(raw, image.content_type or "image/jpeg")

    now = time.monotonic()
    for key, (started, job) in list(_jobs.items()):
        if job.done() and now - started > REUSE_SECONDS:
            del _jobs[key]
    digest = hashlib.sha256(raw).hexdigest()
    if digest not in _jobs:
        _jobs[digest] = (now, asyncio.ensure_future(_cut_out(img_clean)))
    started, job = _jobs[digest]
    try:
        # shield: one caller hanging up must not cancel the run the others wait on
        return await asyncio.shield(job)
    except Exception:
        _jobs.pop(digest, None)   # never reuse a failure
        raise


async def _cut_out(img_clean: Image.Image) -> dict:
    started = time.monotonic()
    shot = product_shot.start(img_clean)   # draws the top on the GPU while the CPU cuts out
    try:
        with capture_crops() as captured:
            result = await run_in_threadpool(extract_garments, img_clean, 0, complete=True)
        # shortcut: TryOffDiff draws one upper garment, so with two tops (shirt + jacket)
        # there is no telling which it drew; both keep their cut-outs.
        tops = [i for i in result["items"] if i["category"] == "topwear"]
        if shot and len(tops) == 1:
            drawn = await run_in_threadpool(shot.result)
            if drawn is not None:
                with Image.open(io.BytesIO(captured[tops[0]["stored_name"]])) as real:
                    product = await run_in_threadpool(product_shot.recolour, drawn, real)
                if product is not None:
                    buf = io.BytesIO()
                    product.save(buf, format="PNG")
                    captured[tops[0]["stored_name"]] = buf.getvalue()
                    tops[0]["drawn"] = True
    finally:
        if shot:
            shot.close()
    seconds = time.monotonic() - started

    items = []
    for item in result["items"]:
        png = captured[item["stored_name"]]
        with Image.open(io.BytesIO(png)) as crop:
            width, height = crop.size
        items.append({
            "name": item["name"],
            "category": item["category"],
            "color": item["color"],
            "confidence": item.get("confidence"),
            "width": width,
            "height": height,
            "png_base64": base64.b64encode(png).decode("ascii"),
        })

    # Sizes and labels only, never the image or the key: shows what each caller's photo yielded.
    print(f"cutout {img_clean.size[0]}x{img_clean.size[1]} -> "
          f"{[(i['name'], i['width'], i['height'], r.get('filled'), 'drawn' if r.get('drawn') else 'cut-out') for i, r in zip(items, result['items'])]} in {seconds:.1f}s"
          f"{' notice: ' + result['notice'] if result['notice'] else ''}", flush=True)
    return {"items": items, "notice": result["notice"], "seconds": seconds}
```

### Change 6: `backend/config.py`

Find this line:

```python
    CUTOUT_API_KEY: str = ""
```

Add these three lines directly after it, with the same indentation:

```python
    # Python of the separate TryOffDiff environment (see tryoff/TRYOFF_SETUP.md).
    # Empty keeps the service on real cut-outs only.
    TRYOFF_PYTHON: str = ""
```

### Change 7: `tests/test_cutout.py`

Append this to the end of the file, after two blank lines. Leave everything
already in the file as it is.

```python
# --- product picture of the top (TryOffDiff) ---

def _fake_extract_big_top(img, user_id, complete=False):
    entries = []
    for name, category, size in (("Top", "topwear", (20, 20)), ("Shoes", "shoes", (4, 6))):
        stored_name, byte_count = save_garment_crop(Image.new("RGBA", size, (28, 65, 58, 255)), user_id)
        entries.append({"name": name, "category": category, "stored_name": stored_name, "color": "#1c413a",
                        "bytes": byte_count, "confidence": 0.9, "image_url": f"/api/images/item/{stored_name}"})
    return {"items": entries, "notice": None}


# Stands in for tryoff/run_tryoff.py: a bright green shirt-sized block on a pale background.
_FAKE_TRYOFF = """
import sys
from PIL import Image, ImageDraw
src, dst = sys.argv[3].split(":")
Image.open(src).close()
img = Image.new("RGB", (128, 128), (240, 240, 238))
ImageDraw.Draw(img).rectangle([30, 20, 97, 109], fill=(40, 200, 140))
img.save(dst)
"""


def _post_with_tryoff(client, monkeypatch, tmp_path, script_text):
    import sys
    from backend import product_shot
    from backend.routers import cutout
    script = tmp_path / "fake_tryoff.py"
    script.write_text(script_text)
    monkeypatch.setattr(product_shot, "SCRIPT", script)
    monkeypatch.setattr(settings, "TRYOFF_PYTHON", sys.executable)
    monkeypatch.setattr(settings, "CUTOUT_API_KEY", "shared-secret")
    monkeypatch.setattr(cutout, "extract_garments", _fake_extract_big_top)
    c, _, _ = client
    response = c.post("/api/cutout", files={"image": ("photo.png", _upload_bytes(), "image/png")},
                      headers={"X-Cutout-Key": "shared-secret"})
    assert response.status_code == 200, response.text
    return {i["name"]: i for i in response.json()["items"]}


def test_top_becomes_a_drawn_product_picture_in_its_real_colour(client, monkeypatch, tmp_path):
    items = _post_with_tryoff(client, monkeypatch, tmp_path, _FAKE_TRYOFF)
    assert (items["Shoes"]["width"], items["Shoes"]["height"]) == (4, 6)   # only the top is drawn
    top = Image.open(io.BytesIO(base64.b64decode(items["Top"]["png_base64"])))
    assert top.mode == "RGBA"
    assert abs(top.width - 68) <= 4 and abs(top.height - 90) <= 4          # the drawn block, cropped tight
    r, g, b, a = top.getpixel((top.width // 2, top.height // 2))
    assert a == 255
    assert max(abs(r - 28), abs(g - 65), abs(b - 58)) <= 6                 # real colour, not the bright green


def test_failed_drawing_keeps_the_real_cutout(client, monkeypatch, tmp_path):
    items = _post_with_tryoff(client, monkeypatch, tmp_path, "import sys; sys.exit(1)")
    assert (items["Top"]["width"], items["Top"]["height"]) == (20, 20)


def test_two_tops_keep_their_cutouts(client, monkeypatch, tmp_path):
    from backend.routers import cutout

    def two_tops(img, user_id, complete=False):
        result = _fake_extract_big_top(img, user_id, complete)
        result["items"][1]["category"] = "topwear"
        return result
    items = _post_with_tryoff(client, monkeypatch, tmp_path, _FAKE_TRYOFF)   # sets everything up
    cutout._jobs.clear()
    monkeypatch.setattr(cutout, "extract_garments", two_tops)
    c, _, _ = client
    body = c.post("/api/cutout", files={"image": ("photo.png", _upload_bytes(), "image/png")},
                  headers={"X-Cutout-Key": "shared-secret"}).json()
    assert [(i["width"], i["height"]) for i in body["items"]] == [(20, 20), (4, 6)]
```
