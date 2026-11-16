# Proposed API and dependency register

Version 1.0 · 20 October 2026. Coordination appendix only; each feature's requirements, examples, tests and acceptance remain in its own PRD.

Every route below is **proposed**. None was called or verified live in this documentation task. Existing F5 routes are separately inventoried in [SOURCE-EVIDENCE.md](SOURCE-EVIDENCE.md).

## API ownership

| Method | Proposed route | Owning PRD | Auth and mutation controls |
|---|---|---|---|
| GET | /api/v1/health | 02 | Public limited readiness; verified HTTPS |
| POST | /api/v1/auth/signup | 03 | Public, rate-limited, idempotency |
| POST | /api/v1/auth/login | 04 | Public, rate-limited |
| POST | /api/v1/auth/refresh | 04 | Hashed refresh token, atomic rotation |
| GET | /api/v1/auth/me | 04 | Bearer; shared profile DTO |
| POST | /api/v1/auth/logout | 04 | Bearer or refresh revocation; inherently repeatable |
| POST | /api/v1/photos | 07 | Bearer, multipart, idempotency |
| POST | /api/v1/extractions | 08 | Bearer, JSON, idempotency and photo/pipeline uniqueness |
| GET | /api/v1/extractions/{job_id} | 08 | Bearer/owner |
| POST | /api/v1/extractions/{job_id}/retry | 08 | Bearer, JSON, idempotency, failed-state guard |
| GET | /api/v1/extractions/{job_id}/result | 09 | Bearer/owner |
| GET | /api/v1/media/{media_id} | 09 | Bearer/owner, private bytes, no static storage route |
| POST | /api/v1/garments/batch | 09 | Bearer, idempotency, candidate versions, atomic batch |
| GET | /api/v1/garments | 10 | Bearer, owner/query-bound keyset cursor |
| GET | /api/v1/garments/{garment_id} | 11 | Bearer/owner |
| PATCH | /api/v1/garments/{garment_id} | 11 | Bearer, idempotency, If-Match |
| DELETE | /api/v1/garments/{garment_id} | 11 | Bearer, idempotency, If-Match |
| POST | /api/v1/garments/manual | 12 | Bearer, idempotency, durable manual operation |
| POST | /api/v1/outfits/score | 13 | Bearer, read-only computation, item versions |
| GET | /api/v1/outfits/recommendations | 14 | Bearer, bounded owner-only computation |
| POST | /api/v1/saved-outfits | 15 | Bearer, idempotency, item versions, unique composition |
| GET | /api/v1/saved-outfits | 15 | Bearer/owner, cursor |
| GET | /api/v1/saved-outfits/{saved_outfit_id} | 15 | Bearer/owner |
| DELETE | /api/v1/saved-outfits/{saved_outfit_id} | 15 | Bearer, idempotency, If-Match |
| POST | /api/v1/wear-events | 16 | Bearer, idempotency, daily composition uniqueness |
| GET | /api/v1/wear-events | 16 | Bearer/owner, cursor |
| DELETE | /api/v1/wear-events/{wear_event_id} | 16 | Bearer, idempotency, If-Match |
| PATCH | /api/v1/profile | 17 | Bearer, idempotency, If-Match |

Gallery and camera have native handoff contracts, no backend capture API. Migration has local operator contracts, no remote migration endpoint. APK delivery introduces no public installer API. PostHog transport uses tested SDKs, not an invented application ingestion endpoint.

## DTO reconciliation

- **Profile:** user_id UUID, username string, display_name string, version integer, analytics_consent boolean, consent_version integer, timezone IANA string or null. A legacy missing display name falls back to the username for the API/UI; no new user identity is created. Null timezone prompts a choice before wear recording.
- **Health:** server_id UUID, api_version string, status ready/degraded, ai_status ready/warming/unavailable. If DB/core service not usable return structured 503 instead of a misleading ready object.
- **Garment:** full detail shape in 11; list summaries explicitly in 10. `media_id` and confidence can be null for imported missing/unknown data. `pattern:"unknown"` is valid for failed manual analysis and is adapted to absent pattern for scoring with warning.
- **Palette:** full object includes palette array, dominant, accent, neutral_share, contrast, temperature and n_accent_colors. Display truncated top-five shares honestly; no claim the truncated list always sums to1.
- **Score:** integer0–100, verdict, notes, palette, algorithm_version; single-item wear history may have null score and no verdict.
- **Errors:** error.code/message/retryable and request_id. Optional error.fields (allowlisted field/code pairs), error.current_version. Never return raw exceptions/SQL/filesystem paths.
- **Examples:** synthetic fixtures are independent across PRDs. Reusing a sample UUID does not assert the same stored label/color in every example.

## Identity and consistency ownership

Database identities/migrations live in19. Session UUID is an authentication record; analytics session_id is a different random identifier. Analytics UUID is pseudonymous account correlation, not proof of ownership.

Canonical garment categories preserve F5. The API-facing `accessories` filter maps to stored bag/headwear. No silent mapping of `full` to generic topwear. Scoring adapter `f5-adapter-v1` explicitly corrects pattern_scale→scale; extraction `f5-baseline-v1` is separate. Version both source and model revisions.

Candidate-save operations are atomic. Favoriting never increments wear. Recording wear never creates a favorite. Migration of F5 outfits creates imported wear records and baseline counters only. A deleted garment remains a tombstone for historical integrity while active lists/score APIs exclude it.

## Cross-feature implementation checkpoints

1. **Foundation:** SQL schema and read-only F5 preflight; server readiness/HTTPS; login/session contracts; design tokens.
2. **First usable journey:** gallery → upload → durable extraction → review batch save → closet, with owner checks at every handoff.
3. **F5 interaction parity:** camera, manual add, garment corrections/deletion, recommendations and wear.
4. **Requested extensions:** outfit builder, saved favorites and profile preferences.
5. **Measurement:** typed events added alongside each feature; PostHog fixture validation after test-project configuration.
6. **Release:** concrete import report/cutover, actual phone/laptop parity tests, signed APK install/upgrade.

Implementation checkpoints are ordered milestones, not time estimates. Exact duration depends on toolchain, laptop model availability, existing data quality and target phone.

## Open decision register

| ID | Decision/input | Owner | Needed by | Current treatment |
|---|---|---|---|---|
| D01 | Phone model and Android version | User | Device/toolchain setup | No universal compatibility claim |
| D02 | Laptop RAM/CPU/GPU/free storage | Engineering + user | Worker limits/performance | One worker; targets provisional |
| D03 | Final app name/package ID | User | First distributable signing | OOTD working name |
| D04 | PostgreSQL installation/version | Engineering + user | Schema implementation | Proposed engine, no installation yet |
| D05 | F5 source schema and owner ambiguities | Data/operator | Import dry run | Quarantine; no guessed owner |
| D06 | F5 timestamp timezone | Operator | Historic timestamp conversion | Preserve raw/unresolved values |
| D07 | Missing-media import treatment | Operator | Import activation | Labelled metadata-only rows or quarantine, explicit decision |
| D08 | Local HTTPS trust bootstrap/library compatibility | Engineering | Physical connection test | Release requires verified TLS |
| D09 | PostHog project/region/retention | User | Enabling analytics | Off until configured and consented |
| D10 | Model revisions/licences and output tolerance | AI/QA | Parity acceptance | Pin and compare fixtures first |
| D11 | Signing-key custody/backup | User/release | Signed distribution | Private key outside source |

The user's selected **F5 light design** and **F5-only import** are resolved decisions, not open questions.
