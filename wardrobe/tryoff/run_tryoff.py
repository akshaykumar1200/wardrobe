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
