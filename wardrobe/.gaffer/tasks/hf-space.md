---
id: hf-space
files: [wardrobe/space/Dockerfile, wardrobe/space/README.md, wardrobe/space/requirements.txt, wardrobe/space/.dockerignore, wardrobe/space/prefetch_models.py, wardrobe/space/BUILD.md, wardrobe/backend/config.py, wardrobe/backend/main.py]
test: cd wardrobe && venv\Scripts\python.exe -m pytest tests -q
effort: high
sandbox: full
timeout: 45
---
What's missing: this FastAPI app runs only on the user's laptop. Package it to
run as a **Docker Space on Hugging Face**, so the phone can reach it when the
laptop is off. Produce the files under `wardrobe/space/`. **Do not push
anything** — there are no credentials here and the push is a separate step.

Read `wardrobe/backend/main.py` and `wardrobe/requirements.txt` first.

## What the app is

FastAPI + SQLAlchemy. Serves `/api/*` and mounts a built React SPA from
`frontend/dist` as a catch-all **after** the API routes. Two vision models load
at import time: `mattmdjaga/segformer_b2_clothes` and `ZhengPeng7/BiRefNet`
(~529 MB of weights). Database is SQLite locally, Postgres when
`SUPABASE_DB_URL` is set; `backend/database.py` already resolves this.
Garment crops live in the `blobs` table on Postgres — **nothing persistent
touches the filesystem**, which matters because a Space wipes its disk on
restart.

## 1. `space/Dockerfile`

- Base `python:3.11-slim`. The laptop runs 3.11; do not change the minor version.
- **Listen on port 7860** — Spaces expect that and nothing else.
- Create a non-root user and run as it. Spaces run containers unprivileged, and
  a root-owned cache directory makes the model download fail at runtime.
- Set `HF_HOME=/home/user/.cache/huggingface` and make it writable by that user.
- **Download both models at build time** by running `prefetch_models.py`, so the
  weights are baked into the image. Downloading them on first request instead
  would add about a minute to an already slow cold start.
- Install `torch` and `torchvision` from the CPU wheel index
  (`https://download.pytorch.org/whl/cpu`) — the default wheels pull CUDA and
  add gigabytes for a GPU the free tier does not have.
- Copy `backend/`, `frontend/dist/` and `requirements.txt` from the **repo root**
  (build context is `wardrobe/`, not `wardrobe/space/`).
- Start with `uvicorn backend.main:app --host 0.0.0.0 --port 7860`. One worker:
  two would each load the models and exhaust the 16 GB.

## 2. `space/requirements.txt`

Derive from `wardrobe/requirements.txt`, dropping what the server does not
need: `pytest`, `selenium`, `trio`, `trio-websocket`, `wsproto`,
`websocket-client`, `outcome`, `PySocks`, `sortedcontainers`, `iniconfig`,
`pluggy`. **Add `psycopg[binary]`**, which the Postgres path needs and is not
in the current file. Keep the pinned versions; they are known to work together.
Do not include `supabase` — crops go through SQLAlchemy, not their client.

## 3. `space/prefetch_models.py`

Imports the same `from_pretrained` calls `backend/segmenter.py` and
`backend/matting.py` make, so the build populates the same cache the app reads
at runtime. Keep the model ids in one place: import them from
`backend.config.settings` rather than retyping the strings.

## 4. `space/README.md`

Spaces read YAML front matter. It must set `sdk: docker`, `app_port: 7860`, a
title, and `short_description`. Below the front matter, document in plain
English: what the Space is, which secrets it needs, and that the first request
after it sleeps is slow.

## 5. `space/.dockerignore`

Exclude `venv/`, `storage/`, `backups/`, `*.db`, `.env`, `__pycache__/`,
`.gaffer/`, `tests/`, `frontend/node_modules/`, `frontend/src/`,
`cloudflared.exe`, and the loose `*.png` screenshots in the repo root.
**`.env` and `*.db` must never enter the image** — one holds the admin password
and session secret, the other the user's wardrobe.

## 6. `backend/config.py` and `backend/main.py` — small changes only

- `config.py`: add `SPACE_MODE: bool = False`. When true the app must **refuse
  to start on SQLite**, raising a clear error at import. A Space on SQLite
  silently loses every garment on restart, and failing loudly beats that.
- `config.py`: `COOKIE_SECURE` must default to **True** when `SPACE_MODE` is
  set. A Space is served over HTTPS and the session cookie must not be sent in
  the clear.
- `main.py`: add `GET /healthz` returning `{"ok": true}` **without touching the
  database** — it is a liveness check, and one that fails when the database
  sleeps is worse than none.
- `main.py`: the CORS `origins` list is hardcoded to localhost and one LAN IP.
  Add any origin from `settings.PUBLIC_ORIGIN` so the Space's own URL works.

## 7. `space/BUILD.md`

The human steps, in order, in plain English: create the Space, set the secrets
(`SUPABASE_DB_URL`, `SESSION_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`,
`SPACE_MODE=true`, `PUBLIC_ORIGIN`), and push. State plainly that secrets go in
the Space's **Settings → Variables and secrets**, never in the repo.

## Done when

`venv\Scripts\python.exe -m pytest tests -q` still passes all **36** tests —
the laptop path must be untouched — and the Dockerfile, requirements, README,
prefetch script, .dockerignore and BUILD.md all exist under `wardrobe/space/`.

## Do not

- Do not run `docker build`, `huggingface-cli`, or `git push`. No credentials
  exist here and nothing is to be published.
- Do not change `backend/crops.py`, `database.py`, `models.py`, the routers, or
  anything under `../android_app/`.
- Do not add a dependency beyond `psycopg[binary]`.
- Do not commit or create a `.env` under `space/`.
