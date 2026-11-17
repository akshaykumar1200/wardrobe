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

**If either is missing, the laptop has old code. Run `git pull` in
`C:\wardrobe-repo` and check again. If they are still missing after the pull,
stop and report it. Do not write this code yourself.**

Then run the cut-out tests once, to prove the code you have works:

```powershell
cd C:\wardrobe-repo\wardrobe
.\venv\Scripts\python.exe -m pytest tests/test_cutout.py -q
```

The TryOffDiff tests are `test_top_becomes_a_drawn_product_picture_in_its_real_colour`,
`test_failed_drawing_keeps_the_real_cutout`, `test_two_tops_keep_their_cutouts`
and `test_drawn_top_is_not_also_sent_to_gemini`. They must pass. Two older tests
(`test_identical_photos_share_one_run`, `test_failed_run_is_not_reused`) start
the whole app and can fail if `.env` points at a database this laptop cannot
reach. Report them, but they do not block this step.

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
- For each step 1 to 10: done, skipped (already done), or failed, with the
  exact error text for any failure.
- The tunnel link.
- Whether TryOffDiff ran on `cuda`, and how many seconds the test run took.
- Anything you could not check.
