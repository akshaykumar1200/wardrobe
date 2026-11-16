# Source evidence and proposed-system boundary

Inspected: 20 October 2026. Root: `C:\Users\Lenovo\Desktop\fasion`.

## Selected source

The user's final choices are **F5 light OOTD design** and **F5-only data import**. Earlier suggestions of dark cards, email-first login and multi-prototype imports are not the selected parity baseline.

| Evidence | Verified in source | Consequence |
|---|---|---|
| `F5/static/index.html` | OOTD branding; cream background `#F7F6F2`, white cards, sage primary `#3B5B4C`; Plus Jakarta Sans; radii 8/14/22 px and pill controls; upload, camera, closet, auth/review/manual/edit/outfit modals | Recreate the light layout in Flutter; adapt modals for a narrow phone |
| Saved `f5_webview_main.png`, `f5_webview_outfit_modal.png` under the referenced Antigravity artifact directory | Visually inspected light upload hero, three help cards, closet entry, recommendation score, palette, garment cutouts | Supporting visual references; screenshots may predate current HTML |
| `F5/main.py` | Existing routes listed below; startup initializes SQLite and runs a file cleanup loop | Do not start/import the app merely to inspect or migrate data; it can write/delete |
| `F5/db.py` | SQLite users/items/outfits; integer IDs; case-insensitive username; salted PBKDF2-SHA256 (100,000 iterations); one reusable token per user; default-owner migrations | Preserve source identities with a mapping; new per-device sessions; legacy verification/rehash path; audit default/demo ownership |
| `F5/segmenter.py` | SegFormer `mattmdjaga/segformer_b2_clothes`; inference side 1024, work side 1280, four Torch threads; worn and flat-lay branches; PNG cutouts and garment analysis | Primary AI baseline; inference currently executes synchronously in the request path |
| `F5/matting.py` | Optional BiRefNet `ZhengPeng7/BiRefNet`, side 512; lazy loading; fallback on errors; `trust_remote_code=True` | Cache and pin a reviewed model revision before deployment; report fallback mode honestly |
| `F5/pattern.py`, `F5/colors.py` | Color palettes and heuristic pattern/scale classification | Describe as estimates, not guaranteed material recognition |
| `F5/outfit_color.py` | `score_outfit` needs at least two items; full-body and two-piece combinations; optional shoes/accessories; computes `adjusted_score` but sorts by raw `score` | Preserve raw-score ordering for parity; cycling recommendations is separate; changing rotation logic needs a versioned change |
| `F5/test_multiuser_isolation.py`, `F5/test_polish_features.py` | Auth/item isolation checks, DB WAL, accessory/full-body combinations and cleanup tests are present | Existing test intent is useful, but tests were not run and do not prove mobile readiness |
| `wardrobe/backend/*` | Separate email/cookie-auth app; upload validation, user directories, protected saved-item media; integer SQLAlchemy models | Reference implementation only; not selected import source |
| `f6/backend/*` | Different unauthenticated SQLite app with global items/outfits and dark AURA frontend | Neither design baseline nor import source |
| Root `run_extraction.py`, `process_user_image.py`, `make_showcase.py` | Stage images/showcase generation with hard-coded artifact paths | Stage diagnostics exist in scripts, not as verified F5 response fields |
| `extracted_garments/extraction_results.json` | Saved historical run reports 35.3 seconds, three garments and confidence values | Artifact only; not a current performance benchmark or F5 regression oracle |

## Existing F5 HTTP contracts — source verified, not runtime verified

This inventory documents older contracts, not promises for Android. Examples of proposed success/failure contracts are provided in the owning PRDs. Existing JSON error bodies generally use FastAPI `detail`; `/api/v1` will use the proposed structured error envelope.

| Existing route | Observed request/auth | Observed response and limitation |
|---|---|---|
| `POST /api/auth/register` | JSON username/password | `ok`, user integer ID/username, token; cookie also set |
| `POST /api/auth/login` | JSON username/password | Same response shape; separate unknown-user and wrong-password errors |
| `POST /api/auth/logout` | Bearer or cookie | `{"ok":true}`; clears user's single token |
| `GET /api/auth/me` | Optional bearer/cookie | `authenticated`, user or null |
| `POST /api/extract` | Authenticated multipart `file` | `garments` array; no durable job/status/stage-image contract |
| `POST /api/items` | Authenticated JSON category/path plus metadata | Integer `id`, supplied `path`; trusts client path/metadata |
| `GET /api/items` | Optional auth; category query | Owner's item array or empty array when unauthenticated |
| `PUT /api/items/{item_id}` | Authenticated category/label/color | `updated`; source does not verify row count before success |
| `DELETE /api/items/{item_id}` | Authenticated | `deleted`, or 404; file deletion and DB mutation are not an atomic transaction |
| `POST /api/items/manual` | Multipart file; category/label/color declared as simple route parameters | Integer ID/path; frontend submits those parameters in multipart, a contract mismatch to fix in the new API |
| `GET /api/suggest` | Optional auth | outfit/score/verdict/notes/palette plus all_suggestions when available |
| `POST /api/wear` | Authenticated JSON item_ids/score/verdict/palette/notes | `ok`; client score trusted, no business deduplication |
| `GET /storage/...` | Static files | Source mount is public; protecting item rows alone does not protect images |

## Important design and behavior corrections

1. Permanent UUIDs identify records; **authorization checks**, owner-scoped queries and constraints prevent cross-user access. UUIDs alone do not guarantee privacy.
2. Keep the F5 look but replace “100% On-Device & Private” with accurate laptop-processing and optional-analytics wording.
3. F5 filters use `upper/lower/footwear/bag/headwear/full`, not the root engine's topwear/bottomwear schema. Explicit adapters are mandatory.
4. F5 persisted `pattern_scale` must map to the scorer's `scale`. Preserve the as-is baseline and record any corrected scoring behavior separately.
5. Imported F5 `outfits` are wear-history records. They are not evidence of a favorites system.
6. Source startup's orphan cleanup deletes old originals. Migration must use an offline snapshot/read-only adapter and copy referenced media before new cleanup rules run.
7. Actual source data may predate the schema in source code. Inspect a backup with schema metadata and owner-count reconciliation before any import.
8. The PostHog wizard has not been executed. [Official wizard documentation](https://posthog.com/docs/ai-engineering/ai-wizard) lists Flutter and FastAPI support as of this review. Actual integration/configuration in this local project remains unverified. No wizard is necessary to finish the PRDs.

## Source file fingerprints

The final quality report records SHA-256 hashes of selected code and design files to make this inspection reproducible. Hashes identify inspected files, not model weights, databases or screenshots. Implementation must separately record model revisions and its own baseline fixtures.
