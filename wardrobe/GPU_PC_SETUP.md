# Run the cut-out service on the UK PC

This PC takes over from Akshay's laptop. The Lovable website
(my-style-memory-closet.lovable.app) sends each outfit photo here, and this PC
cuts out every garment and sends the pictures back.

All commands are for **Windows PowerShell**. Run them one block at a time.
Never put the cut-out key in a file you commit, a chat, or a screenshot.

## What you need from Akshay

- Access to the GitHub repo `akshaykumar1200/wardrobe`.
- The **cut-out key**, sent to you privately. It must match the
  `LAPTOP_CUTOUT_KEY` secret in Lovable.

## 1. Install the tools (once)

```powershell
winget install -e --id Git.Git
winget install -e --id Python.Python.3.11
winget install -e --id Cloudflare.cloudflared
```

Close PowerShell and open it again so the new commands are found.

Then send Akshay the output of this (it tells him which GPU and how much memory
the PC has):

```powershell
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
```

## 2. Get the code (once)

```powershell
git clone https://github.com/akshaykumar1200/wardrobe.git C:\wardrobe-repo
cd C:\wardrobe-repo\wardrobe
```

## 3. Install Python packages

```powershell
cd C:\wardrobe-repo\wardrobe
py -3.11 -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
```

## 4. Create the settings file (once)

This writes `.env` with the cut-out key, plus a random admin password and
session secret, because the service is reachable from the internet. **Skip this
step if `.env` already exists**: running it again replaces the file.

```powershell
cd C:\wardrobe-repo\wardrobe
$env:CUT_KEY = Read-Host "Paste the cut-out key from Akshay"
.\venv\Scripts\python.exe -c "import os,secrets; k=os.environ['CUT_KEY'].strip(); open('.env','w').write('CUTOUT_API_KEY='+k+'\nSESSION_SECRET='+secrets.token_urlsafe(32)+'\nADMIN_PASSWORD='+secrets.token_urlsafe(16)+'\n')"
Remove-Item Env:CUT_KEY
```

## 5. Download the models (once, about 1 GB)

```powershell
cd C:\wardrobe-repo\wardrobe
.\venv\Scripts\python.exe -m deploy.prefetch_models
```

## 6. Start the service

Keep this window open. It is the service.

```powershell
cd C:\wardrobe-repo\wardrobe
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Check it: open http://127.0.0.1:8000/healthz in a browser on this PC. It should
show `{"ok":true}`.

## 7. Give it a public link

Open a **second** PowerShell window and pick one option.

**Option A: quick test, no account.** The link changes every time this
command restarts, so Akshay has to update Lovable each time.

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

Copy the `https://....trycloudflare.com` link it prints.

**Option B: permanent link (recommended).** Needs a free Tailscale account.
Install Tailscale from https://tailscale.com/download, sign in, then:

```powershell
tailscale funnel --bg 8000
```

The first time it may print a link to turn Funnel on. Open it, allow it, and run
the command again. It prints a link like `https://pc-name.tail1234.ts.net`. That
link stays the same after restarts and keeps working without this window.

## 8. Connect the Lovable website (Akshay does this)

1. In Lovable, open **Settings → Secrets**.
2. Set `LAPTOP_CUTOUT_URL` to the link from step 7. Use just the link, with no
   `/api/cutout` and no slash at the end.
3. Leave `LAPTOP_CUTOUT_KEY` as it is.
4. Upload an outfit photo on the website.

On this PC, the service window should show a line like
`cutout 900x1600 -> [('Top', ...), ('Trousers', ...)] in 30s`, then
`"POST /api/cutout HTTP/1.1" 200 OK`. That means it is connected.

- `401` means the key in `.env` does not match `LAPTOP_CUTOUT_KEY`.
- Nothing appears means the link in Lovable is wrong, or the tunnel is not running.

## 9. Keep it running

Stop the PC from sleeping while plugged in:

```powershell
powercfg /change standby-timeout-ac 0
```

Start the service automatically when you sign in to Windows. The PC must sign
in after a restart, either by itself or by someone signing in.

```powershell
schtasks /Create /TN "Wardrobe cutout" /SC ONLOGON /TR "cmd /c cd /d C:\wardrobe-repo\wardrobe && venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
```

With Option B, Tailscale starts on its own, so nothing else is needed. With
Option A, you have to start the tunnel by hand and send Akshay the new link.

## After every `git pull`

```powershell
cd C:\wardrobe-repo\wardrobe
git pull
.\venv\Scripts\python.exe -m pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
schtasks /End /TN "Wardrobe cutout"
schtasks /Run /TN "Wardrobe cutout"
```

If you started the service by hand instead, press `Ctrl+C` in its window and
run step 6 again.

## About the GPU

For now the service runs on the CPU, exactly as it does on the laptop. A later
update will use the GPU to draw shop-style product pictures. When that update
lands, this file will get a new step. Follow "After every `git pull`" and then
that step.
