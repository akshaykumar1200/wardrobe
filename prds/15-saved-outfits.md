# OOTD-15 — Saved outfits

Version 1.0 · 20 October 2026 · Owner: Product/Backend/Mobile · Status: new proposed feature.

## 1. Overview and scope

Objective: keep a reusable combination separate from the act of wearing it. Persona: owner saving a useful recommendation or custom selection. Pain: rebuilding combinations and confusing favorites with wear history.

Verified F5 `outfits` stores `/api/wear` history; no favorites/list-favorites contract was found. All functionality here is proposed. In scope: save, list, detail, remove favorite and incomplete/stale state. Out: sharing, collaborative outfits, renaming after creation and automatic import of wear history as favorites.

## 2. Requirements and acceptance

| Requirement | Acceptance criterion |
|---|---|
| FR1 Save authoritative composition | 2–5 owned eligible item UUID/versions accepted; server recomputes score, never trusts client score/notes. |
| FR2 Avoid duplicate favorites | Same active owner+sorted item set creates one favorite, even with different request keys; resave returns existing UUID. |
| FR3 Persist and browse | Saved outfits survive app/laptop restart; list is owner-filtered and cursor-paginated; detail includes score snapshot and current item availability. |
| FR4 Handle item changes | Edits mark saved score stale; deletion marks outfit incomplete; user can inspect/remove but cannot wear an invalid composition without review. |
| FR5 Remove only favorite | Unsave does not delete garments or wear history; versioned/idempotent deletion is recoverable. |
| FR6 Reflect committed outcomes | Saved icon/count updates only after confirmation or reconciliation; failed save does not imply favorite exists. |

## 3. Flow

Builder/recommendation Save → optional title → POST item versions → owner/eligibility/scoring → favorite transaction → saved state. Saved Outfits → list → detail → use current items in builder or remove favorite.

```mermaid
sequenceDiagram
  participant P as Phone
  participant A as Favorites API
  participant D as SQL
  P->>A: POST owned item IDs/versions + key
  A->>D: Lock/validate items; check unique composition
  A->>A: Compute authoritative score snapshot
  A->>D: Commit favorite and links
  A-->>P: saved_outfit_id
  P->>A: GET saved outfits
  A-->>P: Owned favorites with freshness state
```

## 4. Frontend

Extend F5 light recommendation cards with a labelled Save control. Title 1–80 characters, default “Saved outfit”; no title analytics. Save button disabled while pending. Render saved badge only when operation confirmed. Offline show retry and retain selection/key; no hidden queue of new favorites.

List states: loading, no saved outfits with Generate CTA, populated, offline stale, service error. Detail flags “Garment changed” or “Item removed,” shows remaining metadata and offers Open in builder. Missing private image is a placeholder; do not resurrect deleted images from cache. Accessible count/title and icon labels, 48 dp actions, large-text support.

## 5. Proposed API contracts

HTTPS/bearer; POST JSON/key, DELETE key/If-Match, GETs no body. Snapshot examples below are minimal list/detail DTOs; score/palette/notes are returned by detail as defined by OOTD-13.

| API/request | Success example | Failure example |
|---|---|---|
| `POST /api/v1/saved-outfits` `{"title":"Friday outfit","items":[{"garment_id":"70000000-0000-4000-8000-000000000001","version":1},{"garment_id":"70000000-0000-4000-8000-000000000002","version":1}]}` | `201 {"saved_outfit_id":"a0000000-0000-4000-8000-000000000001","version":1,"already_saved":false}`; existing composition returns 200/already_saved true | `409 {"error":{"code":"GARMENT_VERSION_CHANGED","message":"Refresh this outfit before saving.","retryable":false},"request_id":"r-150"}` |
| `GET /api/v1/saved-outfits?limit=20` | `200 {"items":[{"saved_outfit_id":"a0000000-0000-4000-8000-000000000001","version":1,"title":"Friday outfit","score":72,"verdict":"solid","state":"current","item_count":2}],"next_cursor":null}` | `422 {"error":{"code":"INVALID_CURSOR","message":"Refresh your saved outfits.","retryable":false},"request_id":"r-151"}` |
| `GET /api/v1/saved-outfits/a0000000-0000-4000-8000-000000000001` | `200 {"saved_outfit_id":"a0000000-0000-4000-8000-000000000001","version":1,"title":"Friday outfit","state":"stale","items":[{"garment_id":"70000000-0000-4000-8000-000000000001","saved_version":1,"current_version":2,"available":true},{"garment_id":"70000000-0000-4000-8000-000000000002","saved_version":1,"current_version":1,"available":true}],"score":72,"verdict":"solid","notes":["All-neutral palette. Safe, polished, and hard to get wrong.","Everything sits at a similar lightness, so the outfit reads flat. Swap one piece lighter or darker."],"palette":{"palette":[{"hex":"#111111","name":"black","share":1.0}],"dominant":{"hex":"#111111","name":"black","share":1.0},"accent":null,"neutral_share":1.0,"contrast":"low","temperature":"neutral","n_accent_colors":0},"algorithm_version":"f5-adapter-v1"}` | `404 {"error":{"code":"SAVED_OUTFIT_NOT_FOUND","message":"Saved outfit not found.","retryable":false},"request_id":"r-152"}` |
| `DELETE /api/v1/saved-outfits/a0000000-0000-4000-8000-000000000001`; `If-Match:"1"` | `200 {"removed":true}` | `409 {"error":{"code":"VERSION_CONFLICT","message":"Reload this saved outfit.","retryable":false,"current_version":2},"request_id":"r-153"}` |

Other errors: 401 auth, 404 foreign/removed item/favorite, 422 invalid title/composition, 428 missing version, 429 throttled, 503 DB unavailable. Schema examples are illustrative, not observed scores.

Workflow: validate all item ownership/versions under transaction snapshot → apply 13 eligibility → compute server score → reserve unique canonical item-set hash scoped to owner → insert favorite/links/snapshot/outbox. Concurrent identical saves return the winner's UUID. Unsave tombstones only favorite/links; repeated same-key delete returns stored success. Physical garment media is not modified.

## 6. Database and operations

Proposed `saved_outfits(saved_outfit_id,user_id,title,composition_hash,score_snapshot jsonb,algorithm_version,version,created_at,deleted_at)`; `saved_outfit_items(saved_outfit_id,user_id,garment_id,garment_version,position)` with owner-preserving FKs. Unique active `(user_id,composition_hash)`; links unique per outfit/garment.

Item mutation increments owner revision and invalidates detail freshness. Derive `current|stale|incomplete` by comparing live items/version; historical score remains labelled as saved snapshot. Cache lists privately ≤30s, invalidate on mutation.

Targets: list/detail ≤500ms p95; save ≤1s; 30 writes/minute/account, page default20/max50. Metrics: save conflicts, duplicate resolutions, incomplete favorites and DB latency. Audit IDs/action only; titles and palettes stay private. No admin cross-owner read through this API.

## 7. Analytics

Consented envelope: event UUID/version/time, distinct/user ID, app session UUID, Android/app version/screen/source.

| Event | Trigger | Typed properties |
|---|---|---|
| `outfit_save_tapped` | Save intent | `operation_id:uuid`, `origin:enum(builder,recommendation)`, `item_count:int` |
| `outfit_saved` | Server first favorite commit | `operation_id:uuid`, `origin:enum`, `item_count:int` |
| `saved_outfit_opened` | Detail displayed | `state:enum(current,stale,incomplete)` |
| `outfit_unsaved` | Server favorite removal | `operation_id:uuid` |
| `outfit_save_failed` / `outfit_save_retried` | Error/retry | `error_code:enum`, `attempt:int` |
| `outfit_save_abandoned` | Explicit title/save cancellation | `origin:enum` |

Example: `{"origin":"recommendation","item_count":3,"attempt":1}`. Exclude title/item IDs/images. One event per real create/remove, not per same-composition replay. KPI: distinct saved combinations / consented scored-view sessions within 24h; seven-day favorite reopen rate.

## 8. Tests

| ID | Preconditions/data | Steps | Expected | Priority/type |
|---|---|---|---|---|
| T01 | Valid owned selection | Save/list/detail | Durable correct favorite | P0 functional |
| T02 | Duplicate reordered items, two devices | Save concurrently | One active composition UUID | P0 concurrency |
| T03 | Fake score or foreign item UUID | Submit | Rejected, no private leak | P0 security/API |
| T04 | Garment changed before save | Submit old version | 409, no stale new favorite | P0 integration |
| T05 | Edit/delete after save | Open detail | Stale/incomplete explicit | P0 regression |
| T06 | Unsave favorite with wear history | Delete | Garments/wear history intact | P0 consistency |
| T07 | Lost save/delete response | Replay key | Same result, one event | P0 recovery |
| T08 | Empty/list >20/corrupt cursor | Browse | Empty state/stable pagination/422 | P1 API/UI |
| T09 | Expired session/offline; large text | Save/read/retry | Correct auth/recovery/accessibility | P1 integration/UI |
| T10 | Performance fixture, consent off/on | Measure/inspect | Target/limits, no title leakage | P1 performance/analytics |

FR1→T01/03/04; FR2→T02; FR3→T08; FR4→T05; FR5→T06/07; FR6→T07/09/10.

## 9. Tasks/dependencies/risks

Mobile: saved badge, list/detail, stale/incomplete presentation. Backend: canonical composition, transactions, scoring snapshot, versioned remove. SQL: 19 tables; garments 11; score 13; recommendation 14; wear 16 is separate. Analytics:18.

Open: future rename/edit-favorite UI; explicitly out of v1. Risk: treating imported F5 history as favorites; migration must not do that.

## 10. Release readiness

- [ ] Save/list/detail/remove contracts and uniqueness verified.
- [ ] Item mutation and history boundaries pass.
- [ ] No client score trusted.
- [ ] Failure reconciliation and consented events agree with DB.
- [ ] User sees snapshot freshness before reuse.
