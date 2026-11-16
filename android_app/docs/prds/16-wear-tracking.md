# OOTD-16 — Wear tracking

Version 1.0 · 20 October 2026 · Owner: Product/Backend · Status: proposed F5 parity feature.

## 1. Overview and scope

Objective: record “Wear This Today” once, update garment wear counts and retain a readable history. Persona: owner tracking clothing use. Pain: double-tap inflation, missing timezone semantics and confusing saved favorites with actual wear.

Verified F5 `POST /api/wear` increments item counts and stores outfits/history using supplied scores and current server timestamp. Proposed contract validates every owner and recomputes score; migration preserves F5 history separately from favorites.

In scope: today wear recording, recent history and undo a newly recorded wear event. Out: calendar planning, reminders, historical backfill editor and changing recommendation ranking.

## 2. Requirements and acceptance

| Requirement | Acceptance criterion |
|---|---|
| FR1 Record owned composition | 1–5 distinct active owned garments; versions checked; a single full-body garment may be worn even though its score is null. |
| FR2 One daily record | Unique owner+local date+canonical item set prevents duplicate wear increments across keys/devices; same set can be worn next day. |
| FR3 Correct counts/time | Commit event, links and increments atomically; dates use profile IANA timezone and server-validated today; timestamps stored UTC. |
| FR4 Preserve history | Readable owned history survives garment deletion; deleted item is labelled unavailable; imported records retain provenance. |
| FR5 Undo safely | User may undo a new event once; counters never go below imported baseline; recompute last_worn from remaining history/baseline. |
| FR6 Honest feedback | “Recorded for today” only after commit; retry/timeout reconciles without a second increment. |

## 3. Flow

Recommendation/builder/favorite → Wear Today → submit IDs/versions/date → validate local today/owner → unique transaction → show confirmation/history → optional Undo.

```mermaid
sequenceDiagram
  participant P as Phone
  participant A as Wear API
  participant D as SQL
  P->>A: Wear items for local date
  A->>D: Lock garments; find same-day composition
  alt Already recorded
    A-->>P: Existing event, no increment
  else New
    A->>D: Insert wear event/links and increment counts
    A-->>P: Recorded
  end
```

## 4. Frontend

Keep F5 Wear This Today control with pending/recorded states. Show local date and garment summary before submission; no calendar manipulation required in v1. A late retry near midnight preserves original requested date and either reconciles known event or explains date conflict, never silently records a different day.

History is a simple dated list, not a wardrobe analytics dashboard. Undo confirmation explains it removes the wear record, not the clothes. Imported history may be read-only where source count reconciliation is uncertain. Unknown historical timestamps are labelled.

Network/session errors keep selection and operation key. Accessible status/Undo labels, 48 dp controls and 200% text. Targets: record/undo p95 ≤1s, history ≤500ms.

## 5. Proposed API contracts

HTTPS/bearer; POST JSON + key; DELETE If-Match + key; GET no body.

| API/request | Success | Failure |
|---|---|---|
| `POST /api/v1/wear-events` `{"items":[{"garment_id":"70000000-0000-4000-8000-000000000001","version":1},{"garment_id":"70000000-0000-4000-8000-000000000002","version":1}],"local_date":"2026-10-20","timezone":"Asia/Kolkata"}` | `201 {"wear_event_id":"c0000000-0000-4000-8000-000000000001","version":1,"local_date":"2026-10-20","already_recorded":false}`; duplicate 200/already_recorded true | `409 {"error":{"code":"WEAR_DATE_MISMATCH","message":"Review today's date before recording.","retryable":false},"request_id":"r-160"}` |
| `GET /api/v1/wear-events?limit=20` | `200 {"items":[{"wear_event_id":"c0000000-0000-4000-8000-000000000001","version":1,"local_date":"2026-10-20","timezone":"Asia/Kolkata","item_count":2,"source":"native","can_undo":true}],"next_cursor":null}` | `422 {"error":{"code":"INVALID_CURSOR","message":"Refresh wear history.","retryable":false},"request_id":"r-161"}` |
| `DELETE /api/v1/wear-events/c0000000-0000-4000-8000-000000000001`; `If-Match:"1"` | `200 {"undone":true}` | `409 {"error":{"code":"IMPORTED_HISTORY_READ_ONLY","message":"This imported record cannot be undone here.","retryable":false},"request_id":"r-162"}` |

Other errors: 401 auth, 404 missing/foreign item/event, 409 GARMENT_VERSION_CHANGED/VERSION_CONFLICT, 422 invalid/duplicate IDs/timezone or TIMEZONE_REQUIRED if profile timezone is null, 428 version missing, 429 WEAR_LIMIT, 503 DB. A missing profile timezone opens Settings for an explicit choice; do not silently use laptop timezone.

Backend locks garments in UUID order, validates count/owner/status/version and profile timezone. Accepts local_date matching today except same-key/existing-composition replay returns original event across midnight. Canonical signature from sorted IDs; unique transaction prevents race. Score stored as server-calculated snapshot when eligible; else null plus reason, never client-supplied score.

Undo locks event and affected rows, records undone_at, reverses only native event increments, recomputes last_worn from active native events plus imported baseline, and writes outbox. Idempotent replay returns original success. No filesystem changes.

## 6. Data/security/operations

Proposed `wear_events(wear_event_id,user_id,local_date,timezone,occurred_at,composition_hash,score_snapshot,source,version,undone_at)`; `wear_event_items(wear_event_id,user_id,garment_id,item_snapshot)`; garments retain `imported_wear_count`, `imported_last_worn_at` plus current totals.

Import uses F5 saved wear_count as baseline; imported history is informational and **not counted again**. Any mismatch between source history and count is reported in migration. Owner-aware FKs; no query accepts a user ID override.

30 writes/minute/account, list default20/max50. Metrics: duplicates avoided, count reconciliation errors, transaction time and midnight conflicts. Audit event/action/UUID only. Alert on negative counter attempts or failed reconciliation; no analytics counts used as the database source of truth.

## 7. Analytics

Consented envelope: UUID event/version/time, distinct/user ID, app session UUID, platform/app version/screen/source.

| Event | Trigger | Properties |
|---|---|---|
| `wear_outfit_tapped` | Client action | `operation_id:uuid`, `origin:enum`, `item_count:int` |
| `outfit_worn_recorded` | First server event commit | `operation_id:uuid`, `item_count:int`, `origin:enum` |
| `wear_record_failed` / `wear_record_retried` | Error/retry | `error_code:enum`, `attempt:int` |
| `wear_record_undone` | Server undo commit | `operation_id:uuid` |
| `wear_confirmation_cancelled` | Explicit cancel before submit | `origin:enum` |

Example: `{"origin":"recommendation","item_count":3,"attempt":1}`. Omit outfit contents and exact dates from product analytics unless justified separately. One commit event per durable wear entry; duplicate daily submissions do not increase analytics successes.

KPI: distinct valid wear records after suggestion / suggestion-viewed users within 24h; count correctness target zero duplicate increments. Cancellation distinguished from failure and inferred no-action.

## 8. Tests

| ID | Preconditions/data | Steps | Expected | Priority/type |
|---|---|---|---|---|
| T01 | Valid owned set | Wear today → history | One event, each count +1 | P0 functional |
| T02 | Same set, two devices/different keys | Concurrent submit | One daily increment | P0 concurrency |
| T03 | Same set next day | Submit next date on simulated clock | New valid wear | P0 regression |
| T04 | Foreign/missing/stale items | Submit | Whole transaction rejected | P0 security/API |
| T05 | Local midnight/timezone change | Submit/retry | Explicit date policy, no silent shift | P0 edge |
| T06 | Single full garment | Wear | Valid record, null score, no fake verdict | P1 functional |
| T07 | Imported baseline10 plus native1 | Undo native event | Count10, imported history unchanged | P0 migration |
| T08 | Failure between event and counter writes | Inject rollback; retry | Atomic state, one outbox event | P0 recovery |
| T09 | Garment deleted after wear | Read history | Historical record retained, media unavailable | P0 consistency/UI |
| T10 | Throttle, latency, consent/accessibility | Record/undo under test | Limits/targets; accessible private-safe events | P1 performance/analytics |

FR1→T01/04/06; FR2→T02/03; FR3→T05/08; FR4→T09; FR5→T07; FR6→T08/10.

## 9. Tasks/dependencies

Backend: unique daily composition, atomic counters, timezone validation, undo and history. Mobile: wear confirmation/state/history. SQL: 19 baseline import; scoring13; favorite15 and recommendation14 are entry points. Analytics18.

Open: imported F5 timestamps have no explicit timezone; 19 must record operator-selected source timezone, not assume UTC. Preserve ambiguity until resolved.

## 10. Release readiness

- [ ] Duplicate/concurrency/midnight tests pass.
- [ ] Imported baselines are not double-counted.
- [ ] History and undo are owner-safe and transactional.
- [ ] Scoring nullability and confirmation copy verified.
- [ ] Server outcomes and analytics dedupe agree.
