---
id: outfits-wears-api
files: [backend/models.py, backend/schemas.py, backend/main.py, backend/routers/outfits.py, backend/routers/wears.py, tests/test_outfits.py, tests/test_wears.py]
test: venv\Scripts\python.exe -m pytest tests -q
effort: high
sandbox: full
timeout: 45
---
What's missing: the wardrobe backend has users, sessions, uploads and items, but
no way to save an outfit or record that clothes were worn. Specs live in
`../android_app/docs/prds/13-outfit-builder.md`, `15-saved-outfits.md` and
`16-wear-tracking.md`. Those PRDs describe an idealised API (`/api/v1/`,
keyset cursors, `If-Match`, idempotency-key headers, item version numbers).
**Do not build any of that.** Match the conventions already in
`backend/routers/items.py`: plain `/api/...` paths, `Depends(current_user)`,
ownership filtered by `user_id`, no pagination, no ETags, no version columns.

## Build

### 1. `backend/models.py` — four tables, same style as the existing ones

- `Outfit`: `id`, `user_id` (FK users, CASCADE), `name`, `created_at`.
- `OutfitItem`: `id`, `outfit_id` (FK outfits, CASCADE), `item_id`
  (FK items, **SET NULL**, nullable), `item_name` (String, not null).
- `WearEvent`: `id`, `user_id` (FK users, CASCADE), `worn_on` (String,
  `YYYY-MM-DD`), `composition_key` (String, not null), `outfit_id`
  (FK outfits, SET NULL, nullable), `created_at`.
- `WearEventItem`: `id`, `wear_event_id` (FK wear_events, CASCADE), `item_id`
  (FK items, SET NULL, nullable), `item_name` (String, not null).

`item_name` is a snapshot on purpose: deleting a garment must not erase the
record that it was worn. Comment it as
`# shortcut: name snapshot, not a full item copy; history shows "unavailable" for deleted items`.

Add a unique constraint on `(user_id, worn_on, composition_key)` and indexes
`idx_outfits_user` on `Outfit.user_id` and `idx_wears_user` on
`WearEvent.user_id`. Add the matching `relationship(...)` entries to `User`
with `cascade="all, delete-orphan"`, as `items` already has.

New tables need no migration: `backend/main.py:42` already calls
`Base.metadata.create_all`.

### 2. `backend/schemas.py` — follow the existing validator style

- `OutfitCreate`: `name` (1–120 chars, same `Field` style as `ItemCreate.name`),
  `item_ids: list[int]` with a `field_validator` enforcing 1–8 entries, all
  distinct. Reject duplicates with a clear message.
- `OutfitItemOut`: `item_id: int | None`, `name: str`, `available: bool`,
  `image_url: str | None`.
- `OutfitOut`: `id`, `name`, `created_at`, `items: list[OutfitItemOut]`.
- `WearCreate`: `item_ids: list[int]` (same 1–8 distinct rule),
  `worn_on: str | None = None`, `outfit_id: int | None = None`.
  Validate `worn_on` parses as `YYYY-MM-DD` via `date.fromisoformat`;
  reject anything else.
- `WearOut`: `id`, `worn_on`, `outfit_id`, `created_at`,
  `items: list[OutfitItemOut]`, `already_recorded: bool`.

### 3. `backend/routers/outfits.py` — prefix `/api/outfits`, tag `outfits`

- `POST ""` → `OutfitOut`. Load the given item ids **filtered by
  `Item.user_id == user.id`**. If the number found is fewer than requested,
  raise `HTTPException(400, "No such garment in your wardrobe")` — never reveal
  whether the id exists for another user. Snapshot each `item.name` into
  `OutfitItem.item_name`. One commit.
- `GET ""` → `list[OutfitOut]`, newest first, this user only.
- `GET "/{outfit_id}"` → 404 unless owned.
- `DELETE "/{outfit_id}"` → 404 unless owned; deletes the outfit and its links
  and **nothing else**. Items must survive.

### 4. `backend/routers/wears.py` — prefix `/api/wears`, tag `wears`

- `POST ""` → `WearOut`. `worn_on` defaults to `date.today().isoformat()`.
  Build `composition_key` as the distinct item ids sorted ascending and joined
  with `,` so the same set in a different order is the same composition.
  Validate ownership exactly as the outfit route does.
  If a `WearEvent` already exists for this `(user_id, worn_on,
  composition_key)`, return it with `already_recorded: True` and **create
  nothing** — that is the whole point, a retry or a double tap must not count
  twice. Otherwise insert the event and its item links in one commit and
  return `already_recorded: False`.
- `GET ""` → `list[WearOut]`, newest `worn_on` first, this user only.
  Optional `limit: int = 50`, capped at 200.
- `DELETE "/{wear_event_id}"` → 404 unless owned. This is Undo.
- `GET "/stats"` → `{"counts": {"<item_id>": <int>}, "last_worn": {"<item_id>": "<YYYY-MM-DD>"}}`
  for this user, built with **one** grouped query over `WearEventItem` joined
  to `WearEvent` — not a query per item. Register this route **before**
  `/{wear_event_id}` or `stats` is parsed as an id.

For a deleted garment set `available: False`, `item_id: None`,
`image_url: None`, and keep the snapshot name. For a live one build
`image_url` the same way `items.py` does.

### 5. `backend/main.py`

Import and `include_router` both new routers alongside the existing five.

### 6. Tests

Copy the fixture pattern from `tests/test_item_create.py` exactly — including
saving and restoring any previous `app.dependency_overrides.get(get_db)` — but
use your own sqlite filenames (`test_outfits.db`, `test_wears.db`) so the
suites do not share state.

`tests/test_outfits.py` must prove:
1. An outfit can be created and read back with its item names.
2. Another user's item id is rejected with 400.
3. Deleting an outfit leaves the items in place.
4. Deleting an item leaves the outfit readable with `available: False`.

`tests/test_wears.py` must prove:
5. Recording a wear returns `already_recorded: False`, and posting the **same
   item set in a different order on the same day** returns the same `id` with
   `already_recorded: True`, with still exactly one row in the table.
6. The same set on a different `worn_on` creates a second event.
7. `GET /api/wears/stats` returns a count of 2 for an item worn on two days.
8. Deleting a wear event drops its count back.

## Done when

`venv\Scripts\python.exe -m pytest tests -q` passes with **more** tests than
the 17 passing now, and the 17 existing ones still pass unchanged.

## Do not

- Do not touch `backend/routers/items.py`, `auth.py`, `uploads.py` or anything
  under `../android_app/`.
- Do not add a denormalised `wear_count` column to `items` — counts are
  derived, so they cannot drift.
- Do not build outfit scoring or recommendations (PRDs 13 §scoring and 14).
  Those are a separate decision.
- Do not add a dependency. Everything needed is installed.
- Do not create a lint or test baseline file.
