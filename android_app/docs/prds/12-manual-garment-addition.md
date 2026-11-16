# OOTD-12 — Manual garment addition

Version 1.0 · 20 October 2026 · Owner: Mobile/Backend · Status: proposed F5 parity feature.

## 1. Overview and scope

Objective: add a garment when segmentation fails or the owner already has a useful product/cutout image. Persona: owner adding a bag, unusual garment or missed item. Pain: AI failure blocking wardrobe use.

Verified F5 has Add Custom Item and `POST /api/items/manual`; frontend sends form values while backend declares non-file values as ordinary query parameters. New contract below removes that mismatch. Scope: upload reuse, manual label/category/color and optional color/pattern analysis. No automatic background removal or promise of transparent cutout.

## 2. Requirements and acceptance

| Requirement | Acceptance criterion |
|---|---|
| FR1 Add without segmentation | Valid image+label+category+color can create an item even if SegFormer/BiRefNet are unavailable. |
| FR2 Use explicit inputs | Label 1–80 chars; F5 category enum; valid hex color; missing fields rejected, never silently defaulted to upper. |
| FR3 Preserve source identity | `source:"manual"`, confidence null, source photo/media owner-linked; do not fabricate AI confidence. |
| FR4 Safe analysis fallback | Optional palette/pattern estimation can fail; preserve chosen color, mark unknown pattern, return an explicit warning. |
| FR5 Exactly-once save | Same owner/photo/manual operation replay returns original garment; concurrent duplicate submits do not add two items. |
| FR6 Recover drafts | Network/session failures keep local non-secret form state and uploaded photo ID for same account; success refreshes closet. |

## 3. Flow

Add Custom Item → gallery/camera selection → label/category/color → upload via 07 (`source=manual`) → create manual garment from owned photo → analysis/fallback → commit → closet.

```mermaid
sequenceDiagram
  participant P as Phone
  participant A as API
  participant D as SQL
  P->>A: Upload selected image through photo feature
  A-->>P: photo_id
  P->>A: POST /api/v1/garments/manual
  A->>A: Validate fields; bounded optional analysis
  A->>D: Commit manual garment and outbox
  A-->>P: garment_id and warnings
  P->>P: Refresh Closet
```

## 4. Frontend

Light F5 manual form, image preview, label/category/primary color. Explain “Saved as provided; background removal is not applied.” Category includes headwear subtype so import/extraction distinctions are preserved.

States: empty form, draft valid, photo uploading, saving, success, analysis warning, failure. Submit disabled while pending. A color selected by the user remains authoritative even when optional analysis differs. Show textual color name/code for accessibility. Back warns before discarding unsaved form.

If upload succeeded but garment creation failed, retry creation with same photo/key; do not reupload unnecessarily. No automatic save from picker callback.

## 5. Proposed API and workflow

HTTPS/bearer JSON and `Idempotency-Key`. Input references owned ready photo; never filesystem path or client confidence.

```http
POST /api/v1/garments/manual
Authorization: Bearer <access_token>
Idempotency-Key: 90000000-0000-4000-8000-000000000012
Content-Type: application/json

{"photo_id":"40000000-0000-4000-8000-000000000012","label":"Canvas tote","category":"bag","color_hex":"#c2b280"}

201 Created
{"garment_id":"70000000-0000-4000-8000-000000000012","version":1,"source":"manual","confidence":null,"warnings":[]}
```

Failure (`422`):

```json
{"error":{"code":"INVALID_CATEGORY","message":"Choose a garment category.","retryable":false},"request_id":"r-120"}
```

Other errors: 404 PHOTO_NOT_FOUND including foreign owner; 409 PHOTO_NOT_READY/IDEMPOTENCY_CONFLICT; 401 auth; 429 MANUAL_SAVE_LIMIT; 503 STORAGE_UNAVAILABLE/DB. Analysis failure alone returns 201 with `warnings:["ANALYSIS_UNAVAILABLE"]`, not a fake inference success.

Consumed upload API: `POST /api/v1/photos`, bearer/key multipart `file` and `source:manual`; success `201 {"photo_id":"40000000-0000-4000-8000-000000000012","media_id":"80000000-0000-4000-8000-000000000012","status":"ready","width":800,"height":1000,"duplicate":false}`; failure 415 UNSUPPORTED_IMAGE structured as above. Upload byte/decode/metadata limits remain 15MiB/50MP.

Backend validates ready photo and owner, reserves idempotent manual operation, loads sanitized media through server storage, optionally analyzes resized RGB/RGBA in a bounded thread/process, stores original analysis separately and chosen effective color palette. Confidence null; fallback `pattern:"unknown"`, `pattern_scale:"none"`. Scoring adapter treats unknown pattern as absent metadata and adds an uncertainty note.

Create garment/media reference plus owner wardrobe revision and outbox in one transaction. A durable unique manual operation UUID prevents duplication beyond the 24h idempotency cache. Do not globally dedupe by identical image: two deliberate garments may share a photo; creating another requires a new explicit operation.

## 6. Data/security/operations

Write `garments` with photo/media FK, `source=manual`, `manual_operation_id UNIQUE`, `analysis_original`, effective colors, nullable confidence. Reuse protected media; hold reference before staging cleanup can expire it. No new user table.

Rate proposed 10/minute/account, optional analysis deadline 3s; response target ≤5s p95. Analysis is local and independent of heavy ML model readiness. Audit source/action/status, not labels/images. Metrics: manual-save latency, analysis fallback, duplicate replay and cleanup conflicts. Alert only on sustained storage/DB failure.

## 7. Analytics

Consented envelope: event UUID/version/time, distinct/user ID, app session UUID, platform/app version/screen/source.

| Event | Trigger | Typed properties |
|---|---|---|
| `manual_item_started` | Form opened | `entry_point:enum(closet,empty_extraction)` |
| `manual_item_submitted` | Valid save intent | `operation_id:uuid`, `category:enum`, `attempt:int` |
| `garment_saved` | Server manual item committed | `source:"manual"`, `operation_id:uuid`, `analysis_available:bool` |
| `manual_item_failed` / `manual_item_retried` | Error/retry | `error_code:enum`, `attempt:int` |
| `manual_item_abandoned` | Explicit form discard | `photo_uploaded:bool` |

Example: `{"source":"manual","category":"bag","analysis_available":false,"attempt":1}`. No labels, image IDs or color values. Dedupe one outcome per manual operation. KPI: manual saves / valid manual submissions within 30 minutes, and successful recovery after empty extraction.

## 8. Tests

| ID | Preconditions/data | Steps | Expected | Priority/type |
|---|---|---|---|---|
| T01 | Valid photo/form; AI models off | Upload/manual save | Manual item succeeds | P0 functional |
| T02 | Category/label/color omitted/invalid | Submit | 422; no silent default | P0 negative/API |
| T03 | Foreign photo UUID | Create manual item | 404, no reference created | P0 security |
| T04 | Optional analyzer fails/times out | Save valid form | 201 warning, unknown pattern, chosen color | P0 integration |
| T05 | Selected color differs from analysis | Save then score | Chosen effective color used | P0 regression |
| T06 | Double submit/lost response | Retry same operation/key | One garment and event | P0 concurrency |
| T07 | Upload ready; DB save fails | Retry without upload | Same photo reused, successful save | P0 recovery |
| T08 | Cleanup races creation | Run expiry and save | Reference protected or clear expired error | P0 consistency |
| T09 | Large text/TalkBack/form Back | Edit/discard | Accessible validation and draft rules | P1 UI |
| T10 | 10 repeated saves, consent off/on | Measure and inspect | Limits/target, no label/image leakage | P1 performance/analytics |

FR1→T01; FR2→T02; FR3→T03/04; FR4→T04/05; FR5→T06; FR6→T07–09.

## 9. Tasks/dependencies

Mobile: form and upload-to-save continuation. Backend: manual operation service, optional bounded analyzer, effective palette, outbox. SQL: unique operation and media ownership constraints in 19. QA: model-down fallback.

Depends on 05/06, 07, 10, 13 unknown-pattern handling and 18. Open: optional analysis library timeout/memory benchmark. This feature can ship alongside gallery before camera.

## 10. Release readiness

- [ ] Model-down path succeeds without fabricated confidence.
- [ ] Multipart-to-JSON handoff fields match contract.
- [ ] Ownership, retries and cleanup races pass.
- [ ] Chosen color consistently affects scoring.
- [ ] Closet refresh and analytics verified.
