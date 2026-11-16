# OOTD-09 — Extraction result review and wardrobe save

Version 1.0 · 20 October 2026 · Owner: Mobile/Backend · Status: proposed.

## 1. Overview and scope

Objective: inspect detected cutouts, correct labels/categories/colors, exclude unwanted candidates and save selected garments reliably. Persona: owner reviewing imperfect AI results. Pain: wrong classifications, partial saves and duplicate wardrobe entries.

Verified: F5 Review Detected Items modal supports label/category/color edits and exclusion; `saveAllReviewedItems` sends separate `/api/items` writes. Proposed mobile batch save is atomic. Diagnostic original/matte/segmentation views are additions based on root scripts, not existing F5 API fields.

In scope: result/optional stage display, candidate editing and batch save. Out: pixel mask editing, model rerun and editing already saved garments (11).

## 2. Requirements and acceptance

| Requirement | Acceptance criterion |
|---|---|
| FR1 Display real results | Every candidate shows contained cutout, label, category, color swatch/name, pattern/scale and nullable confidence. Missing confidence displays “Not available,” never 100%. |
| FR2 Preserve F5 review actions | User edits label/category/primary color, deselects candidates and sees selected count; flat-lay category review is explicit. |
| FR3 Save selected batch once | All valid selected candidates commit together; repeated request returns same garment IDs; no partial success masked as complete. |
| FR4 Keep metadata consistent | User color correction updates effective color/palette used by scoring while retaining original analysis separately. |
| FR5 Respect retention and owner | Foreign/expired candidates return 404/410; results survive app restart until expiry; saved candidates remain identifiable as saved. |
| FR6 Handle diagnostic absence | Stage images shown only when actually produced; missing matte/fallback is labelled and does not block saving garments. |

## 3. Flow

Completed job → GET result → authenticated media loads → review edits → submit selected candidates with version/key → transaction validates all → create garments/links → success → closet.

```mermaid
sequenceDiagram
  participant P as Phone
  participant A as API
  participant D as SQL
  P->>A: GET extraction result + media
  A-->>P: Candidates, saved state, optional diagnostics
  P->>A: POST /api/v1/garments/batch
  A->>D: Lock and validate all candidate owners/versions
  alt Any invalid candidate
    A-->>P: 409/410; no new garments
  else Valid
    A->>D: Commit all garment rows and candidate links
    A-->>P: Saved IDs
    P->>P: Open Closet
  end
```

## 4. Frontend

Light F5 sheet on large screens, full scrollable review screen on phone; no dark results redesign. Header and save action remain reachable. Labels 1–80 characters; category stored as `upper/lower/footwear/bag/headwear/full`; color `#RRGGBB`. Preserve headwear subtype when user does not change the accessories filter.

State: loading skeleton, populated, zero candidates, failed media tile, saving, saved, conflict and expired. Disable save with zero selection or invalid fields. Draft edits are local and owner/job-scoped; process death restores edits if candidate version matches. Save buttons disabled while pending. Retry reuses key/body; changing edits requires a new key only after resolving previous outcome.

## 5. Proposed API contracts

All HTTPS/bearer. JSON for writes; `Idempotency-Key` required for batch. UUID examples synthetic.

| API/request | Success example | Failure example |
|---|---|---|
| `GET /api/v1/extractions/50000000-0000-4000-8000-000000000001/result` | `200 {"job_id":"50000000-0000-4000-8000-000000000001","candidates":[{"candidate_id":"60000000-0000-4000-8000-000000000001","version":1,"label":"Top","category":"upper","media_id":"80000000-0000-4000-8000-000000000002","color_hex":"#2c524a","color_name":"pine","colors":[{"hex":"#2c524a","name":"pine","share":1.0}],"pattern":"solid","pattern_scale":"none","area":74448,"confidence":0.982,"category_needs_review":false,"saved_garment_id":null}],"diagnostics":{"original_media_id":"80000000-0000-4000-8000-000000000001","matte_media_id":null,"segmentation_media_id":null},"expires_at":"2026-10-21T10:00:00Z"}` | `409 {"error":{"code":"RESULT_NOT_READY","message":"Extraction is still processing.","retryable":true},"request_id":"r-90"}` |
| `GET /api/v1/media/80000000-0000-4000-8000-000000000002` bearer; no body | `200 Content-Type: image/png`, binary PNG, `Cache-Control: private, max-age=300` | `404 {"error":{"code":"MEDIA_NOT_FOUND","message":"Image unavailable.","retryable":false},"request_id":"r-91"}` |
| `POST /api/v1/garments/batch` `{"items":[{"candidate_id":"60000000-0000-4000-8000-000000000001","version":1,"label":"Green tee","category":"upper","color_hex":"#2c524a"}]}` | `201 {"items":[{"candidate_id":"60000000-0000-4000-8000-000000000001","garment_id":"70000000-0000-4000-8000-000000000001","version":1}],"saved_count":1}` | `409 {"error":{"code":"CANDIDATE_CHANGED","message":"Reload the review before saving.","retryable":false},"request_id":"r-92"}` |

Other errors: 401 auth, 404 absent/foreign job/candidate, 410 CANDIDATE_EXPIRED, 422 invalid fields/empty/duplicate candidate IDs, 429 limit, 503 DB/storage unavailable. Proposed batch maximum 20 candidates, ten save calls/minute/account.

Workflow: authenticated owner → validate complete payload → lock selected candidates in stable ID order → verify expiry/version/media readiness → find existing saved links → create only unsaved garments → persist overrides and associations → commit outbox and response. Re-saving an already-saved candidate with identical fields returns existing ID; changed fields returns 409 ALREADY_SAVED_USE_EDIT. Do not trust paths/confidence/analysis from clients.

Media API resolves DB media UUID to server-generated private path under owner root; checks live ownership and reference status; no arbitrary path request or public storage route. Error codes conceal other owners' existence.

## 6. Data, security and operations

Proposed `garments(garment_id,user_id,candidate_id UNIQUE nullable,photo_id nullable,media_id,label,category,color_hex,color_name,colors jsonb,analysis_original jsonb,pattern,pattern_scale,area,confidence,source,version,created_at,deleted_at)`; `candidates.saved_garment_id`. Candidate expiry proposed 24h after result, paused/locked during save.

Color override: if unchanged retain extracted palette; if changed set effective palette to one named color at share 1.0 and retain extracted values in `analysis_original`. Never silently show an edited color while scoring old colors.

Cleanup checks references and candidate save locks; never unlink shared media until no live references remain. SQL mutations and event outbox are transactional; disk cleanup is recoverable. Logs: IDs/status/selection count, no labels or media paths. Targets: result p95 ≤500ms; batch ≤1s for 20 rows excluding media downloads; thumbnail lazy loading. Alert operator for missing referenced media.

## 7. Analytics

Consented envelope: event UUID/version/time, distinct ID/user UUID, app session UUID, platform/app version/screen/source. Server emits durable save outcomes; client emits view/edit intent.

| Event | Trigger | Typed properties |
|---|---|---|
| `extraction_results_viewed` | Result first rendered | `operation_id:uuid`, `candidate_count:int`, `empty:bool` |
| `garment_review_changed` | Field changed | `field:enum(label,category,color,selection)`, `candidate_index:int` |
| `save_garment_tapped` | Batch submitted | `operation_id:uuid`, `selected_count:int` |
| `garment_saved` | Per garment committed once | `operation_id:uuid`, `source:"extracted"` |
| `review_save_failed` / `review_save_retried` | Terminal error / retry | `error_code:enum`, `attempt:int` |
| `review_abandoned` | Explicit discard/exit | `selected_count:int`, `edited:bool` |

Example: `{"selected_count":3,"attempt":1,"source":"extracted"}`. Do not send edited text/colors/photos. Use event ID per persisted garment to dedupe; batch completion KPI uses operation ID and expected count, not number of garment events.

KPI: jobs with ≥1 saved garment / nonempty results viewed within 24h. No-save after expiry is inferred abandonment; partial attempts tracked distinctly.

## 8. Tests

| ID | Preconditions/data | Steps | Expected | Priority/type |
|---|---|---|---|---|
| T01 | Job with 3 candidates | Edit one, deselect one, save | Exactly 2 owned garments | P0 functional |
| T02 | Flat-lay/null confidence/matte absent | Open review | Honest missing values and category prompt | P0 UI/regression |
| T03 | Edit primary color | Save; request outfit score | Effective palette matches override | P0 integration |
| T04 | One invalid/expired candidate in batch | Save | Whole batch rejected; edits retained | P0 negative/transaction |
| T05 | Double tap/response loss | Replay same key | Same IDs; no duplicate rows/events | P0 idempotency |
| T06 | Foreign candidate/media UUID | Read/save | 404; no data disclosure | P0 security/API |
| T07 | Two devices save same candidate | Submit concurrently | One garment, consistent existing result | P0 concurrency |
| T08 | Cleanup races save | Run expiry/save together | Saved media retained; no broken success | P0 recovery |
| T09 | Process death/media download error | Restore review; retry tile | Draft preserved, image error isolated | P1 lifecycle/UI |
| T10 | 20 candidates, large text, consent off/on | Save/measure/inspect | Performance/accessibility; counts deduped | P1 performance/analytics |

FR1/2→T01/02/09; FR3→T04/05/07; FR4→T03; FR5→T06/08; FR6→T02/09.

## 9. Implementation and dependencies

Mobile: candidate edit state, diagnostics, authenticated image loader, atomic save UX. Backend: result DTO, private media serving, batch locks/idempotency, consistent overrides. SQL: 19 candidate/garment/media schema. QA: batch failure and cleanup race tests. Depends on 08, 10 refresh and 18.

Open: exact diagnostic capture adapter and fixture tolerance; diagnostic images may be unavailable in v1 but must never be fabricated. Default 24h candidate retention needs operational review against laptop storage.

## 10. Release readiness

- [ ] Batch atomicity and duplicates tests pass.
- [ ] Color edits affect scoring consistently.
- [ ] Flat-lay/null confidence/missing stage UI verified.
- [ ] Media/candidate ownership and expiry races pass.
- [ ] Result-to-save funnel reconciles with SQL outcomes.
