---
id: audit-prototypes
readonly: true
effort: low
---
Read-only audit. Do NOT create, modify or delete any file; do not run servers; do not open `.env` or `*.db` contents.

Root: `C:\Users\Lenovo\Desktop\fasion`. The chosen base for a new Android app is `F5/` (see `prds/README.md`). Audit the OTHER code so we know what is reusable: `wardrobe/` (backend + frontend), `f6/` (backend + frontend + capture), `F3/`, `f1/`, `f2/`, `f4/`, `q2/`, and root scripts (`colors.py`, `outfit_color.py`, `pattern.py`, `process_user_image.py`, `run_extraction.py`, `make_showcase.py`, `test_full_pipeline.py`, `test_outfit_color.py`). Skip venv/node_modules/site-packages.

For each folder answer with file:line evidence:
1. Purpose, stack (framework + versions from requirements/package.json), entry point, routes/screens.
2. Auth model (email/username, cookie/bearer, hashing), DB (engine, models/tables, migrations e.g. Alembic), file storage & upload validation.
3. Tests present and what they cover.
4. Reusable pieces for the PRDs in `prds/` — specifically: upload validation (OOTD-07), private media serving (OOTD-09), signup/login/session (OOTD-03/04), profile editing (OOTD-17), SQLAlchemy models/migrations usable for PostgreSQL (OOTD-19), any PostHog/analytics code (OOTD-18), any mobile/Flutter/Android code (OOTD-01/20), any QR/pairing/HTTPS code (OOTD-02), job queue code (OOTD-08).
5. How root `outfit_color.py`/`colors.py`/`pattern.py` differ from the F5 copies (diff summary) — which is newer/more complete.
6. Anything that conflicts with the PRDs or would be risky to reuse.

Output: concise markdown per folder, then a "Reuse candidates" table: PRD | file/function | reuse as-is / adapt / reference only | reason.
