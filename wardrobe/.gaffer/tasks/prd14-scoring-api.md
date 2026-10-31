---
id: prd14-scoring-api
files: [wardrobe/backend/scoring.py, wardrobe/backend/outfit_color.py, wardrobe/backend/colors.py, wardrobe/backend/routers/outfits.py, wardrobe/backend/schemas.py, wardrobe/tests/test_scoring.py]
test: cd wardrobe && venv\Scripts\python.exe -m pytest tests -q
effort: high
sandbox: full
timeout: 45
---
What's missing: PRD 14 (outfit recommendations) and the scoring half of PRD 13,
at `../android_app/docs/prds/14-outfit-recommendations.md`. The colour engine
**already exists and is unused**: `backend/outfit_color.py` has
`score_outfit(items)` and `rank_combinations(wardrobe, top_n)`, and
`backend/pattern.py` has `analyze_garment(img, category, name, item_id)` which
returns exactly the dict `score_outfit` expects. Nothing in the backend
imports any of them.

Wire them up. **Do not rewrite the scoring maths.**

## 1. Fix the import that stops the module loading

`backend/outfit_color.py:18` is `from colors import PALETTE, _hex_to_lab`, a
bare absolute import that fails when the app runs as `backend.main:app`. Make
it `from backend.colors import PALETTE, _hex_to_lab`. Check `backend/colors.py`
and `backend/pattern.py` for the same problem and fix those too. That and
nothing else in these three files.

## 2. `backend/scoring.py` — new file, the adapter

One job: turn an `Item` row into the dict the scorer wants.

```python
def describe(item: Item) -> dict | None
```

- The crop lives at
  `Path(settings.STORAGE_ROOT) / "users" / str(item.user_id) / "items" / item.stored_name`.
  When that file exists, call `analyze_garment(Image.open(path), item.category,
  item.name, item.id)`. That reads real pixel area from the alpha channel and
  real colour shares — far better than the flat hex column.
- **Cache the expensive part by `stored_name` only.** Filenames are
  content-addressed sha256, so the same name always means the same bytes and
  the cache can never go stale. Cache `colors`, `pattern`, `scale` and `area`,
  then attach `id`, `name` and `category` per call. Use `functools.lru_cache`
  with `maxsize=512`.
- **Manual garments have no file.** Fall back to the `item.color` hex with
  `share: 1.0`, `pattern: "solid"`, `scale: "none"`, and an area from this
  table, which matches the proportions in `../test_outfit_color.py`:
  topwear 70000, bottomwear 65000, shoes 13000, accessories 5000, other 20000.
  Comment it `# shortcut: fixed areas for photo-less garments, real pixel area when a crop exists`.
- Return `None` when the item has neither a crop nor a colour — it cannot be
  scored and must be left out rather than guessed at.

## 3. Two endpoints in `backend/routers/outfits.py`

Match the conventions already in that file: `Depends(current_user)`, ownership
by `user_id`, plain `/api/...` paths, no cursors, no ETags.

**`POST /api/outfits/score`** — body `{"item_ids": [int]}` (reuse the 1–8
distinct validator style already in `schemas.py`). Load the items **filtered by
`user_id`**; if fewer are found than asked for, raise
`HTTPException(400, "No such garment in your wardrobe")`. Drop any item
`describe()` returns `None` for. If fewer than 2 remain, raise
`HTTPException(400, "Need two scorable garments")` — `score_outfit` returns
`None` below two and must not reach the response. Return
`{score, verdict, notes, palette}`.

**`GET /api/outfits/recommendations?limit=5`** (cap `limit` at 10) — score
combinations from this user's wardrobe.

- **Bound the work before doing it** (PRD FR5). Count
  `len(tops) * len(bottoms) * max(len(shoes), 1)` first. Over **20000**, raise
  `HTTPException(400, "Too many combinations. Narrow your wardrobe first.")`.
  Never silently sample.
- With no topwear or no bottomwear, return
  `{"suggestions": [], "guidance": "Add at least one top and one bottom."}`
  rather than an empty list with no explanation (FR6).
- Call `rank_combinations(wardrobe, top_n=limit)`.
- **Sort by raw score, and break ties by the item ids ascending** so the same
  wardrobe always gives the same order. PRD FR3 is explicit that ranking is
  colour only and that the API must not imply wear history affects it, so do
  **not** fold wear counts into the score.
- Each suggestion returns the ranked `items` as full objects (`id`, `name`,
  `category`, `image_url`) — not bare ids — plus `score`, `verdict`, `notes`
  and `palette`. Build `image_url` the way the rest of that file does, and
  **keep it null when `stored_name` is empty**, as the existing code does.

## 4. `backend/tests/test_scoring.py`

Copy the fixture pattern from `tests/test_outfits.py` exactly, including
saving and restoring any previous `app.dependency_overrides.get(get_db)`, with
its own sqlite filename `test_scoring.db`.

Must prove:
1. Scoring three owned garments returns a score between 0 and 100 with a
   verdict.
2. Another user's item id is rejected with 400.
3. One scorable garment is rejected with 400, not a 500 from `score_outfit`
   returning `None`.
4. Recommendations with no bottomwear return the guidance string and an empty
   suggestion list.
5. Recommendations are deterministic: the same wardrobe gives the same order
   twice.
6. A manual garment with a colour but no photo can still be scored.

Manual items need no file on disk; give photo-backed ones a real small PNG via
`PIL` in the fixture so `analyze_garment` has something to read.

## Done when

`venv\Scripts\python.exe -m pytest tests -q` passes with **more** tests than
the 24 passing now, and all 24 existing ones still pass.

## Do not

- Do not change the scoring maths in `outfit_color.py` or the extraction in
  `pattern.py` — only the broken imports.
- Do not touch `backend/routers/items.py`, `wears.py`, `uploads.py`, `auth.py`,
  `models.py`, or anything under `../android_app/`.
- Do not add a database column or table. The cache is in memory.
- Do not add a dependency; numpy, scikit-image and Pillow are installed.
- Do not build any Android screen.
