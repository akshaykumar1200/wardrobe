---
id: audit-inventory
readonly: true
effort: low
---
Read-only audit. Do NOT create, modify or delete any file. Do NOT open `.env` files, `*.db` contents, or print secrets/password hashes/tokens.

Root: `C:\Users\Lenovo\Desktop\fasion`. Skip contents of `venv/`, `.venv/`, `node_modules/`, `site-packages/`, `__pycache__/`, `.pytest_cache/` (just note they exist and their size).

Answer, with file paths as evidence:
1. Tree of every top-level folder (f1, f2, F3, f4, F5, f6, q2, wardrobe, android_app, prds, storage, extracted_garments, extracted_garments_2, root .py files): for each give a one-line purpose, language/framework, entry point, approx file count and size, and last-modified date of newest source file.
2. Is `fasion` or any subfolder a git repo (`.git` present)? Any CI config (`.github/`, etc.), Dockerfile, launch scripts (.bat/.ps1/.sh), `package.json`, `requirements*.txt`, `pyproject.toml`, `pubspec.yaml`, `build.gradle`, `.env.example`? List each with path.
3. List every `.env`, `.env.*`, `*.db`, `*.sqlite*`, `*.pem`, `*.key`, `*.jks`, `*.keystore` file by PATH and SIZE only (never content).
4. List every markdown/doc file (`*.md`, `*.txt` docs, `*.pdf`, `*.docx`) outside venvs with path and its title/first heading.
5. Duplicates: compare SHA-256 of `prds/*` vs `android_app/docs/prds/*`; and of same-named files across root, F5, f6 (`colors.py`, `outfit_color.py`, `pattern.py`, `segmenter.py`, `matting.py`). Report identical vs differing pairs.
6. Check whether the SHA-256 hashes listed in `prds/QUALITY-REPORT.md` "Source fingerprints" table still match the current F5 files. Report match/mismatch per file.
7. Image/design assets: any logos, icons, fonts, screenshots (`*.png|jpg|svg|ttf|woff*`) outside storage/extracted folders — paths and counts. Also note whether `f5_webview_main.png` / `f5_webview_outfit_modal.png` exist anywhere under the user profile `C:\Users\Lenovo` (search `.gemini` and `AppData` too; report path or "not found").

Output: concise markdown, sections 1–7, facts only, mark anything you couldn't check as UNCHECKED with the reason.
