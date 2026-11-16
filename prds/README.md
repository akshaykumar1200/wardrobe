# OOTD Android — feature PRD library

Date: 20 October 2026 (Asia/Kolkata). Version: 1.0.
Status: requirements drafted; implementation and release validation pending.

This is a documentation deliverable, not an implemented Android application. Each numbered file is a standalone feature PRD. This index coordinates dependencies without combining the features into one PRD.

Supporting documents: [source evidence](SOURCE-EVIDENCE.md), [API ownership and open decisions](API-AND-DEPENDENCY-REGISTER.md), and [documentation quality report](QUALITY-REPORT.md).

## Confirmed product decisions

- Installable Android application, with the existing Python AI pipeline running on the user's Windows laptop.
- Work under `C:\Users\Lenovo\Desktop\fasion\android_app`.
- Match the **light OOTD design in F5**, as explicitly selected by the user. Earlier dark AURA/showcase assumptions are superseded.
- Import **F5 data only**, following the user's final clarification after initially selecting multiple prototypes.
- Use SQL, permanent record identities, account ownership, and PostHog feature/funnel analytics.
- Finish the PRDs before writing implementation code.

## Proposed implementation decisions

Flutter mobile app, FastAPI service, PostgreSQL on the laptop, UUID primary keys, username/password login compatible with F5, and private authenticated media delivery. These are target designs, not claims that the components are already installed or implemented. PostgreSQL is a proposed SQL engine, not a user-selected vendor requirement.

The v1 baseline is same-Wi-Fi use. The laptop must be awake and the service running. Internet is needed for initial dependency/model acquisition and for optional PostHog Cloud delivery; cached models should process photos without internet. Photos stay on the laptop; opted-in analytics leave the laptop/phone for the selected PostHog host. Never describe the mobile architecture as “100% on-device.”

## Documents and delivery sequence

| ID | Standalone feature | Depends on | Delivery |
|---|---|---|---|
| OOTD-01 | [App entry, navigation and F5 visual parity](01-app-entry-and-design.md) | 02, 04 | Foundation |
| OOTD-02 | [Laptop connection and pairing](02-laptop-connection.md) | 19 infrastructure | Foundation |
| OOTD-03 | [Account registration](03-account-registration.md) | 02, 19 | Foundation |
| OOTD-04 | [Login, session lifecycle and logout](04-login-and-sessions.md) | 02, 19 | Foundation |
| OOTD-05 | [Gallery photo selection](05-gallery-selection.md) | 01 | First vertical flow |
| OOTD-06 | [Camera capture](06-camera-capture.md) | 01, 05 handoff | Separate increment |
| OOTD-07 | [Photo upload](07-photo-upload.md) | 02, 04, 05 or 06 | First vertical flow |
| OOTD-08 | [AI extraction jobs](08-ai-extraction.md) | 07, 19 | First vertical flow |
| OOTD-09 | [Extraction review and wardrobe save](09-extraction-review.md) | 08, 19 | First vertical flow |
| OOTD-10 | [Wardrobe browsing and filtering](10-wardrobe-browsing.md) | 04, 19 | First vertical flow |
| OOTD-11 | [Garment detail, editing and deletion](11-garment-management.md) | 10 | Core |
| OOTD-12 | [Manual garment addition](12-manual-garment-addition.md) | 07, 19 | F5 parity |
| OOTD-13 | [Outfit builder and scoring](13-outfit-builder.md) | 10 | Core |
| OOTD-14 | [Outfit recommendations](14-outfit-recommendations.md) | 10, 13 scoring | F5 parity |
| OOTD-15 | [Saved outfits](15-saved-outfits.md) | 13 or 14 | Core |
| OOTD-16 | [Wear tracking](16-wear-tracking.md) | 10, 13 scoring | F5 parity |
| OOTD-17 | [Profile preferences](17-profile-preferences.md) | 04 | Core |
| OOTD-18 | [PostHog analytics and funnels](18-analytics-and-funnels.md) | feature event producers | Throughout |
| OOTD-19 | [SQL identities and F5 data migration](19-sql-identities-and-migration.md) | operator preflight | Foundation |
| OOTD-20 | [Signed Android installation and upgrades](20-android-installation.md) | core acceptance | Release |

Camera, manual addition and wear tracking already appear in F5 and have independent requirements. Password recovery, email verification, administration, iOS, cloud hosting, social sharing and wardrobe statistics dashboards are outside this release. PostHog is a product-team dashboard, not a user-facing wardrobe-statistics screen.

## Evidence and verification boundary

Read [SOURCE-EVIDENCE.md](SOURCE-EVIDENCE.md) for source locations and discrepancies. “Verified existing” means directly inspected source code or saved image, **not** successful execution. No application server, model inference, database import, existing tests or PostHog wizard was run for these PRDs. User databases and `.env` secrets were not opened. Actual database schemas, contents, ownership and source file availability need read-only preflight against a consistent backup before migration.

All `/api/v1/...` endpoints and PostgreSQL schemas in these PRDs are **proposed**, even where an older `/api/...` counterpart exists. Example UUIDs, credentials and measurements are synthetic. Performance values are targets to validate on the user's hardware, not measured results.

## Common contract conventions

Each PRD repeats the conventions it needs; these are the cross-feature reconciliation rules.

- HTTPS base address paired to a laptop `server_id`. Never send credentials to a newly discovered host before verifying its identity. Network clients must not bypass certificate validation.
- `Authorization: Bearer <access_token>` on protected routes; UUID subject resolved by the server. Never trust a client `user_id` to decide ownership.
- JSON unless multipart is explicitly specified. UTC RFC 3339 timestamps in storage and APIs; display local time. All IDs are UUID strings.
- Errors: `{"error":{"code":"...","message":"...","retryable":false},"request_id":"..."}`. No stack traces, SQL, tokens, personal paths or raw filenames.
- `401` invalid/expired credentials; `403` known account permission problem; `404` missing **or foreign-owned** resource; `409` state/version/idempotency conflict; `413` size; `415` format; `422` validation; `429` throttled with `Retry-After`; `503` temporary dependency outage.
- Mutations declared idempotent require `Idempotency-Key` UUID. Store owner, operation, key, body hash and result for 24 hours. Same key/body replays the original result; changed body returns `409 IDEMPOTENCY_CONFLICT`. Creation also uses durable business uniqueness so a late retry cannot create a second saved candidate or wear entry.
- Editable records expose integer `version`; send `If-Match: "n"` on PATCH/DELETE. Stale writes return `409 VERSION_CONFLICT` with the current version. No silent overwrite.
- Five public wardrobe filters: `all`, `upper`, `lower`, `footwear`, `accessories`, `full` (all plus five categories). Stored categories preserve F5: `upper`, `lower`, `footwear`, `bag`, `headwear`, `full`; `accessories` is a filter for bag/headwear.
- A complete proposed garment DTO: `garment_id`, `version`, `label`, `category`, nullable `media_id` (imported missing image only), `color_hex`, `color_name`, `colors:[{hex,name,share}]`, `pattern`, `pattern_scale`, `area`, nullable `confidence`, `source` (`extracted|manual|imported`), `wear_count`, nullable `last_worn_at`, `created_at`. Lists may explicitly return only card fields.
- Common score DTO: `score` integer 0–100, `verdict` (`strong|solid|workable|off`), `notes` string array, `palette` object from F5, `algorithm_version`. No client-supplied score is authoritative.
- Every private file is served via ownership-checked `GET /api/v1/media/{media_id}`; no public `/storage` mount in the new service.
- No blanket event for every progress poll. Track actual state transitions, intent, confirmed outcomes and retries.

## Analytics identity and measurement conventions

The proposed logical envelope is `event_id` UUID, `event_version:1`, UTC `occurred_at`, `distinct_id` (consented anonymous ID before authentication; account UUID after authentication), nullable `user_id`, app `session_id` UUID, `platform:"android"`, `app_version`, `screen_name`, `source:"client"|"server"`, and feature-specific properties. Analytics session IDs are unrelated to bearer/refresh tokens.

All event tables describe logical names. The analytics adapter maps fields into PostHog's SDK capture/identify calls; it does not transmit a custom envelope blindly. Use one canonical `screen_viewed` event with `screen_name`, not a second independent page-view count for every named screen. Earlier `login_viewed`, `wardrobe_viewed`, etc. are aliases mapped into that event. Capture an event once per screen visit, not every rebuild.

Use client success events only for successful presentation of data; durable business outcomes originate from the server transaction outbox. Dedupe by `event_id`, correlate attempts with `operation_id`, and never identify a failed login as the account it tried to access. Reset identity and caches on logout.

Optional analytics are off until consent. Passwords, auth tokens, emails, usernames, labels/search text, photo bytes, file paths/URLs, laptop addresses and QR secrets are excluded. Session replay is off in v1. No personal PostHog API key belongs in the APK.

## Cross-feature acceptance and open decisions

- Match F5 colors, type, card imagery and control hierarchy at 360/412/600 logical-pixel widths, allowing mobile layouts. `F5/static/index.html` is authoritative if old screenshots differ.
- Freeze F5 source/model revisions and baseline inputs/outputs before asserting matching extraction/scoring. Fixing F5 bugs must be documented, not silently change the baseline.
- First release test: pair → imported/new login → gallery → upload → extract → review/save → closet → recommendation → save/wear → logout. Confirm a second user cannot access the first user's rows or media.
- Actual import: F5 source only. Explicit operator decision required for demo/default-owner records whose ownership cannot be proven. Never merge accounts by matching label or username across unrelated sources.
- Remaining user inputs: phone model/Android version; laptop hardware and available storage; preferred app/package name; PostHog project/region (later, through configuration); ownership of ambiguous demo data. None prevents drafting these documents.
- Engineering decisions still to validate: Android SDK/plugin compatibility; trusted local HTTPS bootstrap on the test phone; model availability/licences; legacy password upgrade UX; bounded recommendation workload and measured extraction runtime.

## Release gate

- [ ] Every functional requirement's acceptance criterion and linked tests pass.
- [ ] F5 import dry run reconciles counts, media hashes and owner mappings; backup restore tested.
- [ ] Identity isolation includes media, jobs, idempotency, recommendations and analytics queues.
- [ ] F5 design and AI baseline reviewed on the actual phone/laptop.
- [ ] PostHog test events, funnel denominators, consent and deduplication verified.
- [ ] Signed APK installs/upgrades; keys remain private; server/database backup instructions work.
- [ ] All unresolved release blockers have an owner and decision recorded in the relevant PRD.

## Reference documentation

- [Flutter Android release guide](https://docs.flutter.dev/deployment/android): signing, APK generation and installation workflow.
- [PostHog Flutter SDK](https://posthog.com/docs/libraries/flutter): explicit events, identity, opt-out and offline queue integration.
- [Android network security configuration](https://developer.android.com/privacy-and-security/security-config): HTTPS trust configuration and debug-only exceptions.

These were consulted on 20 October 2026. Pin tested dependency versions during implementation; these PRDs intentionally do not prescribe an unverified “latest” version.
