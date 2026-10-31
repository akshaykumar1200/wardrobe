---
id: crops-in-db
files: [wardrobe/backend/crops.py, wardrobe/backend/models.py, wardrobe/backend/storage.py, wardrobe/backend/routers/images.py, wardrobe/backend/routers/items.py, wardrobe/backend/routers/uploads.py, wardrobe/backend/scoring.py, wardrobe/tests/test_crops.py]
test: cd wardrobe && venv\Scripts\python.exe -m pytest tests -q
effort: high
sandbox: full
timeout: 45
---
What's wrong: garment crops are written to local disk under
`settings.STORAGE_ROOT`. The app is moving to a Hugging Face Space, whose disk
is **wiped on every restart**, so every photo would vanish. Supabase Storage
would solve it but needs a second credential and introduces a partial-failure
window where the file lands and the row does not — the exact orphan problem
`storage.sweep_orphan_crops` already exists to clean up.

Put the crops in the database instead, beside the rows that reference them.
One store, one backup, one transaction.

## The rule

**SQLite → disk, exactly as today. Postgres → database.** The database already
in use decides it; there is no third setting. `backend/database.py` exposes
`DB_URL` and `_is_sqlite`; read the public one.

## 1. `backend/models.py` — one table

`Blob`: `stored_name` (String, **primary key**), `user_id` (FK users, CASCADE),
`data` (LargeBinary, not null), `bytes` (Integer), `created_at`.

Filenames are sha256 content hashes, so the same bytes always produce the same
name. Two users uploading the same photo therefore collide on the primary key:
make the primary key **composite on (user_id, stored_name)**, so each account
keeps its own copy and deleting one user never removes another's image. Add
`Index("idx_blobs_user", Blob.user_id)` and the `relationship` on `User` with
`cascade="all, delete-orphan"`, matching the existing ones.

## 2. `backend/crops.py` — new file, the only module that knows where bytes live

```python
def put(db, user_id: int, stored_name: str, data: bytes) -> int   # returns size
def get(db, user_id: int, stored_name: str) -> bytes | None
def exists(db, user_id: int, stored_name: str) -> bool
def delete(db, user_id: int, stored_name: str) -> None
def names(db, user_id: int) -> set[str]
```

On SQLite each one does what the code does today: read and write
`STORAGE_ROOT/users/<id>/items/<name>`, keeping the existing `.resolve()`
path-traversal guard — **do not drop that check**, it is what stops a crafted
`stored_name` escaping the user's folder. On Postgres each one reads and writes
the `Blob` table filtered by `user_id`.

`put` is idempotent: storing a name that already exists for that user is a
no-op, not an error. Crops are content-addressed, so identical bytes are
genuinely the same image.

## 3. Route the six existing call sites through it

- `backend/routers/images.py:22` — serve from `crops.get`, 404 when it returns
  None. Keep the current behaviour where a crop with **no item row yet** still
  serves: that fix is why the Review screen can show its cut-outs.
- `backend/routers/items.py:37` — the create guard becomes `crops.exists`, and
  the size comes from the stored blob, never from the client.
- `backend/routers/items.py:123` — deletion uses `crops.delete`, and **keeps
  the existing guard that only unlinks on the last reference**. Two items can
  legitimately share one crop file; deleting one must not blind the other.
- `backend/storage.py:77` `save_garment_crop` — write through `crops.put`. It
  needs a `db` session passed in; update its caller in `uploads.py`.
- `backend/storage.py:112` `sweep_orphan_crops` — list via `crops.names` and
  remove via `crops.delete`. Keep the `ORPHAN_CROP_AGE` behaviour on disk; on
  Postgres use `created_at` for the same age check.
- `backend/scoring.py:50` — read bytes through `crops.get` and open them with
  `Image.open(io.BytesIO(...))`. **Keep the `lru_cache` keyed on
  `stored_name`** — names are content hashes so the cache cannot go stale, and
  without it recommendations re-decode every garment on every request.

`validate_and_store_original` keeps writing originals to disk. Originals are
not served to the app and are not worth a database round trip.

## 4. `wardrobe/tests/test_crops.py`

Copy the fixture pattern from `tests/test_item_create.py` exactly, including
restoring any previous `app.dependency_overrides.get(get_db)`, with its own
sqlite filename.

Must prove:
1. `put` then `get` returns the same bytes.
2. `put` twice with the same name does not error and does not duplicate.
3. `get` for another user's `stored_name` returns None — one account cannot
   read another's image even knowing the hash.
4. `exists` is False for an unknown name.
5. A `stored_name` containing `..` cannot escape the user's directory.
6. `names` returns only that user's crops.

## Done when

`venv\Scripts\python.exe -m pytest tests -q` passes with **more** than the 30
tests passing now, and all 30 existing ones still pass.

## Do not

- Do not add a Supabase Storage client or any new dependency.
- Do not change `backend/auth.py`, `schemas.py`, `outfits.py`, `wears.py`,
  `outfit_color.py`, `pattern.py`, or anything under `../android_app/`.
- Do not remove the path-traversal guard or the last-reference delete guard.
- Do not create a lint or test baseline file.
