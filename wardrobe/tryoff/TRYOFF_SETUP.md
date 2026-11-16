# Make a product picture of a top (TryOffDiff)

This turns a photo of someone wearing a top into a clean, flat product picture
of that top, then fixes its colours to match the real garment.

It runs on any Windows laptop or PC. With an NVIDIA GPU it is much faster.

| Machine | Time per photo (30 steps) |
|---|---|
| Laptop, CPU only | about 12 minutes (measured: 726 s) |
| PC with NVIDIA GPU | roughly 10 to 30 seconds (estimate, not measured) |

**Limits. Read these first.**

- **Tops only:** T-shirts, shirts, jumpers. It cannot do trousers, shoes,
  watches or bracelets.
- **The pattern is the AI's guess.** The shape and colours come out right, but a
  print or acid-wash pattern will not be your exact one.
- **The website uses it only after step 9.** Until then you run it by hand on photos.
- **Licence:** the TryOffDiff model is under SSPL. Check its terms before any
  commercial use.

All commands are for **Windows PowerShell**. Run them one block at a time.

## 1. Install Python (once)

```powershell
winget install -e --id Python.Python.3.11
```

Close PowerShell and open it again.

## 2. Get the code (once)

If you already cloned the repo, run `git pull` in it instead.

```powershell
git clone https://github.com/akshaykumar1200/wardrobe.git C:\wardrobe-repo
cd C:\wardrobe-repo\wardrobe\tryoff
```

## 3. Create a separate Python environment (once)

This one is separate from the cut-out service, because it needs newer packages.

```powershell
cd C:\wardrobe-repo\wardrobe\tryoff
py -3.11 -m venv tryoff-venv
.\tryoff-venv\Scripts\python.exe -m pip install --upgrade pip
```

## 4. Install PyTorch: pick ONE

**Laptop or PC without an NVIDIA GPU:**

```powershell
.\tryoff-venv\Scripts\python.exe -m pip install torch==2.2.2 torchvision==0.17.2 --index-url https://download.pytorch.org/whl/cpu
```

**PC with an NVIDIA GPU (RTX 20, 30 or 40 series):**

```powershell
.\tryoff-venv\Scripts\python.exe -m pip install torch==2.2.2 torchvision==0.17.2 --index-url https://download.pytorch.org/whl/cu121
```

An RTX 50 series card needs a newer PyTorch than this. Ask Akshay first.

On the GPU the script runs in half precision, so a 6 GB card such as the
RTX 3060 Laptop is enough.

Check which one you got. `True` means it will use the GPU, and `False` means CPU.

```powershell
.\tryoff-venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available())"
```

## 5. Install the other packages (once)

```powershell
.\tryoff-venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 6. Add your photos

Copy the photos into `C:\wardrobe-repo\wardrobe\tryoff`. They must be **JPG**
files with simple names and no spaces, for example `me1.jpg`, `me2.jpg`.

- Use photos where the whole top is visible.
- A full photo works better than a tight crop.
- Two to five photos of the same top in different light make the colour fix
  more accurate.

## 7. Make the product picture

```powershell
cd C:\wardrobe-repo\wardrobe\tryoff
.\tryoff-venv\Scripts\python.exe run_tryoff.py 30 42 me1.jpg:shirt.png
```

- `30` is the number of steps. Fewer steps are faster but rougher, and 20 is
  still usable.
- `42` is the random seed. Change it to get a different version.
- `me1.jpg:shirt.png` means read `me1.jpg` and write `shirt.png`. Use plain file
  names, not full paths like `C:\...`, because the colon in `C:` confuses it.

The first run downloads about 5 GB of models, so it takes longer. Later runs
start straight away. The first line says `models ready on cuda` (GPU) or
`models ready on cpu`.

If the download fails with `401` or `403`, sign in to Hugging Face with
`.\tryoff-venv\Scripts\huggingface-cli.exe login` and accept the model's terms on
its Hugging Face page. Use your own token, and never share it.

## 8. Fix the colours

The AI usually makes the colour too bright. This step measures the real colour
from your photos and repaints the picture.

```powershell
mkdir out -Force
.\tryoff-venv\Scripts\python.exe color_fix.py out me1.jpg me2.jpg -- shirt.png
```

Put the photos before `--` and the picture from step 7 after it.

You get:

- `out\shirt_fixed.png`: the final product picture.
- `out\color_fix_sheet.png`: a check sheet showing the shirt found in each
  photo, the real colours, and the picture before and after.

The window also prints the colour error, `dE`. Below about 2.3 you cannot see
the difference, and the fix normally brings it to 0.

## 9. Connect it to the website

Do this only after step 7 has worked once by hand. That run downloads the
models, and the website never downloads them itself.

Add one line to the cut-out service's settings file, then restart the service.
The path must point at the Python inside `tryoff-venv`.

```powershell
cd C:\wardrobe-repo\wardrobe
Add-Content .env "TRYOFF_PYTHON=C:/wardrobe-repo/wardrobe/tryoff/tryoff-venv/Scripts/python.exe"
schtasks /End /TN "Wardrobe cutout"
schtasks /Run /TN "Wardrobe cutout"
```

If you started the service by hand, press `Ctrl+C` in its window and start it
again (step 6 of `GPU_PC_SETUP.md`).

From now on, when the website sends a photo:

- The top is drawn by TryOffDiff on the GPU while the CPU cuts out the other
  pieces, then repainted in the real colours and sent back with a transparent
  background.
- Trousers, shoes and accessories are still real cut-outs.
- If the photo has two tops (a shirt and a jacket), or the drawing fails or
  takes longer than 70 seconds, the real cut-out of the top is sent instead.
  The upload never fails because of TryOffDiff.

Check the service window after an upload. Each piece is marked `'drawn'` or
`'cut-out'`:

```
cutout 900x1600 -> [('Top', 310, 420, 0.0, 'drawn'), ('Trousers', 272, 499, 0.0, 'cut-out')] in 34s
```

If the top says `'cut-out'`, the lines above it start with
`product shot failed` and show the error. Send those lines to Akshay.

To switch it off, delete the `TRYOFF_PYTHON` line from `.env` and restart.

## Quick reference

```powershell
cd C:\wardrobe-repo\wardrobe\tryoff
.\tryoff-venv\Scripts\python.exe run_tryoff.py 30 42 me1.jpg:shirt.png
.\tryoff-venv\Scripts\python.exe color_fix.py out me1.jpg me2.jpg -- shirt.png
```
