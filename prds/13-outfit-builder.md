# OOTD-13 — Outfit builder and color-harmony scoring

Version 1.0 · 20 October 2026 · Owner: Product/AI/Backend · Status: proposed UI/API over F5 scoring.

## 1. Overview and scope

Objective: let the owner choose garments and receive the F5-style harmony score, palette and explanatory notes. Persona: owner comparing clothes for today. Pain: opaque suggestions, invalid combinations and scores that disagree with edited colors.

Verified `F5/outfit_color.py` defines `score_outfit`, palette merging and verdict thresholds (strong ≥78, solid ≥62, workable ≥45, otherwise off); fewer than two items yields no score. No independent score HTTP endpoint was found. In scope: selection/eligibility and authoritative server scoring. Out: personal taste prediction, body analysis, weather and fashion-quality guarantees.

## 2. Requirements and acceptance

| Requirement | Acceptance criterion |
|---|---|
| FR1 Select eligible owned items | 2–5 distinct active garments; either upper+lower or full plus another item; no full mixed with upper/lower; at most one of each stored category. |
| FR2 Score server data | Client sends UUID/version only; server loads owned current metadata and computes score; posted fake scores/colors are rejected. |
| FR3 Preserve documented algorithm | Fixed fixtures reproduce pinned scorer outputs; adapter maps `pattern_scale→scale`; this correction is explicitly versioned `f5-adapter-v1`, not claimed identical to F5's mis-mapped HTTP path. |
| FR4 Explain uncertainty | Unknown pattern/missing analysis is identified; no score for insufficient data; zero is displayed as 0/100, not hidden. |
| FR5 Prevent stale display | A result is bound to ordered item IDs/versions; editing/removing an item invalidates it; stale responses cannot overwrite newer selections. |
| FR6 Show F5 result hierarchy | Score/verdict, palette ribbon, styling notes and cutout cards are visible in the light OOTD style and accessible as text. |

## 3. Flow

Outfits → Build outfit → choose closet items → eligibility validation → score request → snapshot/version verification → pure scoring → display result → optional Save (15) or Wear (16).

```mermaid
sequenceDiagram
  participant P as Builder
  participant A as Score API
  participant D as SQL
  P->>A: POST item UUID/version selection
  A->>D: Fetch all owned active garments
  A->>A: Validate slots and metadata; run pinned scorer
  A-->>P: Score, palette, notes, versions
  P->>P: Match response to current selection
```

## 4. Frontend

F5 white cards/sage score badge; item picker shows thumbnails/categories and selected state. State controller maintains one selection generation. Disable score until eligible; describe missing upper/lower/full requirements. Score button may be tapped again after a terminal error; debounce repeated requests.

Loading replaces only score panel, not selection. On 409 show “An item changed; refresh before scoring.” On 404 remove/unavailable-mark the missing item and preserve others. Offline retain selection but label last result stale and disable save/wear unless server validates. Explain that score is a color/pattern heuristic, not an objective judgement of the person.

Use text labels for palette colors/shares and verdict; no color-only feedback. Target visible selection feedback ≤100ms, score response ≤500ms p95 on warm laptop.

## 5. Proposed API and backend

`POST /api/v1/outfits/score`, HTTPS/bearer, JSON; computation is read-only and does not need mutation idempotency. Use `X-Request-ID` for attempt correlation.

```json
{"items":[{"garment_id":"70000000-0000-4000-8000-000000000001","version":1},{"garment_id":"70000000-0000-4000-8000-000000000002","version":1}]}
```

Illustrative `200` contract example for an equal-area white top and black bottom with solid patterns and no footwear (synthetic fixture, not a live execution):

```json
{"items":[{"garment_id":"70000000-0000-4000-8000-000000000001","version":1},{"garment_id":"70000000-0000-4000-8000-000000000002","version":1}],"score":88,"verdict":"strong","notes":["All-neutral palette. Safe, polished, and hard to get wrong."],"palette":{"palette":[{"hex":"#ffffff","name":"white","share":0.5},{"hex":"#111111","name":"black","share":0.5}],"dominant":{"hex":"#ffffff","name":"white","share":0.5},"accent":null,"neutral_share":1.0,"contrast":"high","temperature":"neutral","n_accent_colors":0},"algorithm_version":"f5-adapter-v1","warnings":[]}
```

Failure (`422`):

```json
{"error":{"code":"INCOMPLETE_OUTFIT","message":"Choose a top and bottom, or a full outfit with another item.","retryable":false},"request_id":"r-130"}
```

Other failures: 404 GARMENT_NOT_FOUND including any foreign item, 409 GARMENT_VERSION_CHANGED, 422 DUPLICATE_ITEM/INVALID_COMBINATION/UNSCORABLE_METADATA, 429 SCORE_LIMIT, 503 DB unavailable.

Workflow: validate bounded UUID/version list → owner-scoped fetch in a consistent transaction → ensure count matches and each item active/version correct → adapt F5 names/area/colors/pattern scale → run pure scorer with validated finite shares/hex → ensure finite score 0–100 and known verdict → return exact used versions. Server ignores no unknown fields silently; reject client-provided score.

Unknown pattern maps to omitted pattern for this heuristic and warning `PATTERN_UNKNOWN`; empty/unusable palette is a validation issue unless a known user-chosen primary color can form an explicit fallback. Display palette shares as source proportions; any visual renormalization of shown segments must not rewrite original scoring data.

## 6. Data, consistency, security and observability

Read garments, original/effective analysis and owner revision. No saved outfit row until 15. Cache optional in process by owner UUID + sorted garment UUID/versions + algorithm revision for five minutes, invalidated by edits/deletion. Never share caches across users.

Scorer versions and adapter corrections recorded in DB/config, including source hash. F5 bugs such as footwear matching its own aggregate palette or unused adjusted ranking must be documented, not silently “improved” in a parity release.

Proposed limit 30 score calls/minute/account. Metrics: score latency, eligibility errors, nonfinite-data errors and cache hit rate; logs use operation/item counts, not names. Alert local operator if deterministic scoring errors occur; no model download is required to score already analyzed clothes.

## 7. Analytics

Consented envelope: UUID event/version/time, distinct/user ID, app session UUID, Android/app version/screen/source.

| Event | Trigger | Typed properties |
|---|---|---|
| `outfit_item_selected` / `outfit_item_removed` | Selection changes | `category:enum`, `selected_count:int` |
| `outfit_score_requested` | Client request | `operation_id:uuid`, `selected_count:int`, `attempt:int` |
| `outfit_score_received` | Current result rendered | `operation_id:uuid`, `score_bucket:enum`, `verdict:enum`, `duration_ms:int` |
| `outfit_score_failed` / `outfit_score_retried` | Error/retry | `error_code:enum`, `attempt:int` |
| `outfit_builder_abandoned` | Explicit discard of selection | `selected_count:int`, `had_score:bool` |

Example: `{"selected_count":3,"verdict":"strong","score_bucket":"80_100","attempt":1}`. No raw clothing labels/colors/IDs required. One result event per displayed request generation, not every render. KPI: rendered scores / submitted eligible score operations within 5 minutes; next-action save/wear rate within 24h.

## 8. Tests

| ID | Preconditions/data | Steps | Expected | Priority/type |
|---|---|---|---|---|
| T01 | Upper/lower; full+shoes fixtures | Select and score | Valid authoritative result | P0 functional |
| T02 | One item, duplicate, incompatible slots | Submit | 422 with useful reason | P0 negative/API |
| T03 | Foreign UUID, forged score/color | Submit | Rejected; no private metadata | P0 security |
| T04 | Garment edited after selection | Score old version | 409, no stale score | P0 concurrency |
| T05 | Fixed neutral/accent/pattern fixtures | Compare direct scorer/adapter | Expected versioned outputs; scale mapping explicit | P0 regression |
| T06 | Score 0; unknown/null/nonfinite metadata | Render or reject | 0 shown, uncertainty or clear validation | P0 edge/UI |
| T07 | Request A slow, then selection B | Return B then A | A discarded | P1 concurrency |
| T08 | Network/auth timeout | Retry/refresh | Same selection, bounded retry | P0 integration/recovery |
| T09 | Repeat benchmark/cache cross users | Score load | Latency/limits, owner-safe cache | P1 performance |
| T10 | TalkBack/large text, consent off/on | Read score/palette | Accessible result; deduped private-safe events | P1 UI/analytics |

FR1→T01/02; FR2→T03; FR3→T05; FR4→T06; FR5→T04/07/08; FR6→T10.

## 9. Tasks/dependencies/open decisions

Mobile: selection, eligibility, score panel, stale response guards. Backend: owned snapshot loader, pure adapter, cache and score API. QA: documented golden fixtures and metadata edge cases. Analytics: 18. Dependencies: 10/11 wardrobe, 19 schema; save/wear delegate to 15/16.

Open: whether to adopt further F5 algorithm fixes after parity tests; requires a new algorithm version and explicit product decision. No claims of validated fashion taste accuracy.

## 10. Release readiness

- [ ] Selection/owner/version validations pass.
- [ ] Pinned scorer and explicit adapter correction tested.
- [ ] Null/zero/unknown outputs handled truthfully.
- [ ] UI matches F5 score hierarchy.
- [ ] Latency/cache/privacy/event checks complete.
