# Run the cut-out service on the GPU laptop

For the laptop with the **NVIDIA GeForce RTX 3060 Laptop GPU (6 GB)**.

- **Part A** is done once. It makes the GPU draw a product-style picture of the top.
- **Part B** is done every time the laptop was restarted or went to sleep.

It assumes the basic setup in `GPU_PC_SETUP.md` is done and the code is in
`C:\wardrobe-repo\wardrobe`. All commands are for **Windows PowerShell**. Run
them one block at a time.

What the GPU does and does not do:

- **Top:** drawn by the TryOffDiff model on the GPU, in the garment's real colours.
- **Trousers, shoes, accessories:** real cut-outs, made on the CPU. A 6 GB GPU
  is too small for a model that draws every item.

---

## Part A: turn on the GPU (once)

### A1. Get the latest code

Akshay must have pushed the `tryoff` folder first. If `C:\wardrobe-repo\wardrobe\tryoff`
does not exist after this, stop and tell him.

```powershell
cd C:\wardrobe-repo\wardrobe; git pull
```

### A2. Make the TryOffDiff environment

It is separate from the service's own environment, because it needs newer packages.

```powershell
cd C:\wardrobe-repo\wardrobe\tryoff
py -3.11 -m venv tryoff-venv
.\tryoff-venv\Scripts\python.exe -m pip install --upgrade pip
```

### A3. Install the GPU version of PyTorch (about 2.5 GB)

```powershell
.\tryoff-venv\Scripts\python.exe -m pip install torch==2.2.2 torchvision==0.17.2 --index-url https://download.pytorch.org/whl/cu121
```

### A4. Check that the GPU is found

```powershell
.\tryoff-venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

It must print `True NVIDIA GeForce RTX 3060 Laptop GPU`. If it prints `False`,
update the NVIDIA driver (GeForce Experience or nvidia.com), restart, and run
A3 again. Do not go on until it says `True`.

### A5. Install the other packages

```powershell
.\tryoff-venv\Scripts\python.exe -m pip install -r requirements.txt
```

### A6. Run it once by hand (downloads about 5 GB of models)

Copy any photo of a person wearing a top into `C:\wardrobe-repo\wardrobe\tryoff`
and name it `test.jpg`. Then:

```powershell
cd C:\wardrobe-repo\wardrobe\tryoff
.\tryoff-venv\Scripts\python.exe run_tryoff.py 30 42 test.jpg:test_out.png
```

- It must print `models ready on cuda`. If it says `cpu`, go back to A4.
- Open `test_out.png`. It should show a flat product picture of the top.
- If the download fails with `401` or `403`, sign in with
  `.\tryoff-venv\Scripts\huggingface-cli.exe login` using your own free Hugging
  Face account, accept the model's terms on its page, and run it again. Never
  share your token.

### A7. Tell the service to use it

```powershell
cd C:\wardrobe-repo\wardrobe
Add-Content .env "TRYOFF_PYTHON=C:/wardrobe-repo/wardrobe/tryoff/tryoff-venv/Scripts/python.exe"
```

Run this only once. To switch the GPU drawing off later, delete that line from
`.env` and restart the service.

---

## Part B: start the service (every time)

You need **two PowerShell windows**. Both must stay open.

### B1. Window 1: the service

```powershell
cd C:\wardrobe-repo\wardrobe; .\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Wait about a minute until it prints `Uvicorn running on http://127.0.0.1:8000`.
Check it: http://127.0.0.1:8000/healthz in a browser on this laptop should show
`{"ok":true}`.

### B2. Window 2: the tunnel

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

It prints a link like `https://some-random-words.trycloudflare.com`.
**Send that link to Akshay.**

### B3. Akshay: connect the website

1. In Lovable, open **Settings → Secrets → `LAPTOP_CUTOUT_URL`**.
2. Paste the new link. Use just the link, with no `/api/cutout` and no slash at
   the end.
3. Leave `LAPTOP_CUTOUT_KEY` as it is.
4. Upload a photo on the website.

---

## How to tell it worked

After an upload, Window 1 shows one line per photo. Each piece is marked
`'drawn'` (made on the GPU) or `'cut-out'`:

```
cutout 900x1600 -> [('Top', 310, 420, 0.0, 'drawn'), ('Trousers', 272, 499, 0.0, 'cut-out')] in 34s
"POST /api/cutout HTTP/1.1" 200 OK
```

To watch the GPU work, open Task Manager → Performance → GPU during an upload.
Its memory use should jump by about 3 to 4 GB for a few seconds.

## If something goes wrong

| What you see | Cause and fix |
|---|---|
| The top says `'cut-out'`, and lines above start with `product shot failed` | The GPU drawing failed and the real cut-out was sent instead. Send those lines to Akshay. |
| `product shot failed (TimeoutExpired...)` | The drawing took more than 70 seconds. Check A4 says `True`. On the CPU it takes about 12 minutes. |
| The failed lines mention `out of memory` | Close games, browsers and other apps that use the GPU, then upload again. |
| The failed lines mention `offline` or a missing file | The models were not downloaded. Do A6 again. |
| No `'drawn'` or `'cut-out'` words at all | The service is running old code. Do A1, then restart Window 1. |
| The photo has a shirt and a jacket, and both say `'cut-out'` | Expected. With two tops the service cannot tell which one was drawn. |
| Window 1: `No module named uvicorn`, or the `venv` path is not found | The basic setup was not finished. Do steps 2 to 5 of `GPU_PC_SETUP.md`. |
| Window 2: `cloudflared` is not recognized | Run `winget install -e --id Cloudflare.cloudflared`, then close and reopen PowerShell. |
| Window 1 shows `401` after an upload | The key in this laptop's `.env` does not match `LAPTOP_CUTOUT_KEY` in Lovable. |
| Window 1 shows `503` after an upload | `.env` has no `CUTOUT_API_KEY`. Do step 4 of `GPU_PC_SETUP.md`. |
| Nothing appears in Window 1 after an upload | The link in Lovable is wrong or old. Send Akshay the link from Window 2 again. |

## Remember

- The link **changes** every time Window 2 is restarted or the laptop sleeps.
  Akshay then has to paste the new link into Lovable again. For a link that
  never changes, use Tailscale: Option B in step 7 of `GPU_PC_SETUP.md`.
- Keep the laptop **plugged in**. On battery, Windows slows the GPU down.
- To stop it sleeping while plugged in:

```powershell
powercfg /change standby-timeout-ac 0
```

- Uploads never fail because of the GPU. If the drawing fails for any reason,
  the website still gets the real cut-out.
