---
id: audit-toolchain
readonly: true
effort: low
---
Read-only environment check on this Windows laptop. Do NOT install, update, configure or delete anything. Do NOT open `.env`/`.db` files or print any secret, token or credential. Only run version/listing commands.

Report each item as FOUND (version/path) / NOT FOUND / UNCHECKED (reason):
1. Machine: Windows version, CPU model + cores, total/free RAM, GPU model(s) and whether CUDA/`nvidia-smi` is available, free disk space on C:.
2. Tools on PATH: git, python/py (all versions via `py -0p`), node, npm, npx, java/javac (JAVA_HOME), flutter, dart, Android SDK (ANDROID_HOME/ANDROID_SDK_ROOT, `adb`, `sdkmanager`, platform/build-tools folders under `%LOCALAPPDATA%\Android\Sdk`), Android Studio install, gradle, psql/PostgreSQL service (`Get-Service *postgres*`), docker, openssl, mkcert, codex, gh.
3. Python envs: for `F5\venv` (and `wardrobe`, `f6` venvs if present) report python version and `pip list` versions of: fastapi, uvicorn, torch, torchvision, transformers, timm, pillow, numpy, opencv-python, scikit-learn, sqlalchemy, alembic, psycopg/psycopg2, posthog, passlib/argon2-cffi, python-multipart. Use the venv's own python.exe with `-m pip list`; do not import project code.
4. Model cache: does the Hugging Face cache (`%USERPROFILE%\.cache\huggingface\hub` or HF_HOME) contain `mattmdjaga/segformer_b2_clothes` and `ZhengPeng7/BiRefNet`? Report folder sizes and snapshot revision hashes.
5. Network: is Windows firewall profile for the current network Private or Public (`Get-NetConnectionProfile`)? Laptop's LAN IPv4 (just say whether a 192.168/10./172.16 address exists — do not print it). Any process listening on 8000/8443/5432?
6. Phone: any device visible to `adb devices` (if adb exists)?

Output: concise markdown checklist, facts only.
