---
id: drop-hf
files: [wardrobe/backend/config.py, wardrobe/backend/storage.py, wardrobe/deploy/Dockerfile, wardrobe/deploy/README.md, wardrobe/deploy/DEPLOY.md, wardrobe/deploy/requirements.txt, wardrobe/deploy/.dockerignore, wardrobe/deploy/prefetch_models.py, wardrobe/tests/test_security.py]
test: cd wardrobe && venv\Scripts\python.exe -m pytest tests -q
effort: high
sandbox: full
timeout: 45
---
The project is no longer deploying to Hugging Face Spaces. Strip every trace
of Hugging Face **as a host**, and leave the container setup working for any
Docker host (Google Cloud Run, Oracle Cloud, Fly, a plain VM).

This is a rename-and-reword task. **No behaviour may change.**

## 1. Move `wardrobe/space/` to `wardrobe/deploy/`

"Space" is Hugging Face's word for a hosted app. Move the whole directory and
keep all five files. Nothing outside it references the path by name, so the
move is safe; confirm that with a search before you finish.

## 2. Rename the `SPACE_MODE` setting to `CLOUD_MODE`

It appears in `backend/config.py` (the field, the `COOKIE_SECURE`
`default_factory`, and the startup check), `backend/storage.py`, and
`tests/test_security.py`. Rename every one. The meaning is unchanged:
**"running on a container whose disk does not survive a restart"**, which is
true of every cloud host, not just a Space.

Reword the startup error at `config.py:73` so it no longer names Hugging
Face. It should say that this mode needs a persistent Postgres database
because container storage is ephemeral.

Update the comment in `backend/storage.py:87` the same way — it currently
explains the behaviour in terms of "a Space".

## 3. `deploy/Dockerfile`

- **Change port 7860 to 8000**, in both `EXPOSE` and the `uvicorn` command.
  7860 is a Hugging Face convention; 8000 is what this app uses everywhere
  else, which means one less thing that differs between laptop and cloud.
- **Keep `HF_HOME` exactly as it is.** It is not about the host: it is the
  cache directory the `huggingface_hub` library uses to store the two vision
  models, which are downloaded from huggingface.co whatever machine this runs
  on. Changing or removing it breaks model loading. Add a one-line comment
  saying so, because the next reader will assume it is leftover.
- Leave the CPU-wheel torch install, the non-root user and the build-time
  model prefetch alone. All three are still right.

## 4. `deploy/README.md`

It is currently a Hugging Face Space card: YAML front matter with
`sdk: docker` and `app_port: 7860`. **Delete the front matter entirely** — it
means nothing outside Hugging Face.

Replace with a plain README: what the image contains, that it listens on
8000, the environment variables it needs, and that the first request after an
idle period is slow because the models load at import.

## 5. `deploy/BUILD.md` becomes `deploy/DEPLOY.md`

Rewrite it host-neutral. It must cover, in plain English:

- building the image locally: `docker build -f deploy/Dockerfile .` from the
  `wardrobe/` directory, because the build context is the repo root
- the environment variables to set on whatever host is used:
  `SUPABASE_DB_URL`, `SESSION_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`,
  `CLOUD_MODE=true`, `PUBLIC_ORIGIN`
- that these are set as the host's own secrets or environment settings, never
  committed to a file in the repository
- that `PUBLIC_ORIGIN` must be the public HTTPS address the browser will use,
  because password-reset links and CORS are both built from it

Do not name Hugging Face, and do not write instructions specific to any one
host; no host has been chosen yet.

## 6. Check nothing was missed

Search the tree for `SPACE_MODE`, `7860`, `hf.space`, `Hugging Face` and
`huggingface` outside `venv/`, `node_modules/`, `frontend/dist/` and
`.gaffer/`. The only surviving hits must be:

- `HF_HOME` and the model ids in the Dockerfile and `prefetch_models.py`
- `huggingface_hub` / `transformers` in the requirements files

Those are the model library, not the host. Everything else goes.

## Done when

`cd wardrobe && venv\Scripts\python.exe -m pytest tests -q` passes all **47**
tests, none skipped, and `wardrobe/space/` no longer exists.

## Do not

- Do not change any behaviour: same checks, same defaults, same cookie rules.
- Do not touch `backend/crops.py`, `database.py`, `models.py`, the routers,
  `mailer.py`, or anything under `../android_app/`.
- Do not delete `cloudflared.exe`.
- Do not edit files under `.gaffer/` — those are a historical record.
- Do not add or remove a dependency.
