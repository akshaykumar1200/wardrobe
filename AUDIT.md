# OOTD Android: repository audit and readiness assessment

Date: 21 October 2026 · Scope: `C:\Users\Lenovo\Desktop\fasion` · Read-only audit

**What was and wasn't done.** I read the source and documents, compared file hashes, listed which packages are installed and checked the toolchain. I did **not** start any server, run any test, run AI inference, or open any database or `.env` file. "Implemented" below means *the code is there*. It does not mean the code was seen working: **no feature has been verified at runtime.**

The only files changed during the audit: `git init` at the root, a new root `.gitignore`, `.gaffer/` (the audit task briefs and logs), and this file.

Detailed evidence logs, with file and line references:
- `.gaffer/logs/audit-f5-vs-prd.last.md`: F5 routes, schema, frontend, a check of each PRD against F5, and security notes.
- `.gaffer/logs/audit-prototypes.last.md`: `wardrobe`, `f6`, `F3`, `f1`, `f2`, `f4`, `q2` and the root scripts, plus what can be reused.
- `.gaffer/logs/audit-inventory.last.md`: the folder tree, duplicate files and fingerprint checks.

---

## 1. Repository overview

| Path | What it is | Role for the Android app |
|---|---|---|
| `F5/` | FastAPI and a single-page HTML app ("OOTD"). Username/password auth, SQLite, SegFormer extraction, optional BiRefNet background removal, colour/pattern analysis, outfit scoring, wear tracking. Has its own **empty** git repo (no commits). | **The selected base**: its design, AI pipeline and data source |
| `F5/static/index.html` | The whole F5 front end: upload, camera, closet tabs, review/manual/edit/outfit modals, sign-in | The visual reference to match (OOTD-01) |
| `F5/wardrobe.db` (40 KB), `F5/storage/` (4 files, 2.2 MB) | F5's live data. Not opened. | Source for the migration (OOTD-19). The data volume is very small. |
| `wardrobe/` | FastAPI + SQLAlchemy + React/Vite. Email/cookie auth with Argon2, upload validation, owner-checked images, admin. Has `.env`, `.env.example` and 7 DB backups. | Code to borrow from (upload validation, private media, profile editing, ORM layout). **Not** an import source. |
| `q2/` | pytest suite aimed at `wardrobe/` (auth, IDOR, EXIF, CRUD) | A reference for designing tests |
| `f6/` | Single-user, dark-themed "AURA" FastAPI prototype with no auth | Reference only. Not the design baseline and not an import source. |
| `F3/`, `f1/`, `f2/`, `f4/` | Segmentation experiments (U2NET, SegFormer demos, DeepLabV3) | Not needed |
| Root `*.py` | Older, better-commented versions of `colors.py`, `outfit_color.py` and `pattern.py`, plus extraction scripts | F5's copies are newer and use F5's categories. The root copies are reference only. |
| `prds/` = `android_app/docs/prds/` | 20 feature PRDs plus README, SOURCE-EVIDENCE, API register and QUALITY-REPORT (24 files) | The requirements. The two folders are **byte-identical duplicates**. |
| `android_app/` | Contains only `docs/prds/` | No Android code exists |

**Environment found on this laptop**

| Item | Status |
|---|---|
| Hardware | i5-8250U (4 cores / 8 threads), 19.9 GB RAM, 86 GB free on C:, Intel UHD 620 + AMD Radeon 530. **No NVIDIA/CUDA**, so the AI runs on the CPU. |
| Android | Android Studio installed, SDK platforms 35 and 36.1, build-tools 35/36, `adb` present but not on PATH. **No phone connected.** |
| Flutter / Dart | **Not installed** |
| Java | Only Android Studio's bundled JBR. No `JAVA_HOME`, and `java` is not on PATH. |
| PostgreSQL / Docker | **Not installed** |
| Python | No global Python (`python` is the Microsoft Store stub). `F5\venv` is Python 3.11.15 with torch 2.0.1+cpu, transformers 4.44.2, fastapi 0.141.1. `wardrobe\venv` additionally has SQLAlchemy, argon2-cffi, timm, einops and kornia. |
| AI models in HF cache | `mattmdjaga/segformer_b2_clothes` @ `584abc1e…` (104 MB) and `ZhengPeng7/BiRefNet` @ `e2bf8e44…` (424 MB). Both are cached. |
| Node | v24.21.0, npm 11.19 |
| Network | Laptop has a private LAN IPv4, but the **Wi-Fi profile is "Public"**, which normally blocks the phone from reaching the laptop. Nothing is listening on 8000, 8443 or 5432. |
| Git | Root repo just created (no commits). `F3`, `f4` and `F5` are separate nested repos. |

## 2. PRD inventory

All 20 PRDs are dated 20 Oct 2026, v1.0, status "proposed". The eight F5 source fingerprints in `QUALITY-REPORT.md` **still match** the current files, so the PRDs describe today's F5.

| ID | Feature | F5 today (source only, not run) |
|---|---|---|
| 01 | App entry, navigation, F5 visual parity | Web UI with tokens `#F7F6F2`/`#3B5B4C`, Plus Jakarta Sans (`index.html:16–48`) |
| 02 | Laptop connection and pairing | Only `start_f5_with_tunnel.bat` (a public tunnel) |
| 03 | Account registration | `POST /api/auth/register` (`main.py:125`) |
| 04 | Login, sessions, logout | Login/logout/me (`main.py:145–185`). One reusable token per user that never expires. |
| 05 | Gallery selection | Browser file input |
| 06 | Camera capture | Browser camera input |
| 07 | Photo upload | Inside `/api/extract`. No size, MIME or decode checks (`main.py:190–208`). |
| 08 | AI extraction jobs | Runs synchronously inside the request (`segmenter.py:344–450`). No job queue. |
| 09 | Extraction review and save | Review modal, then separate `POST /api/items` calls (`index.html:1258–1333`) |
| 10 | Wardrobe browsing | `GET /api/items?category=` and tabs (`main.py:243`, `index.html:1336–1442`) |
| 11 | Garment edit/delete | `PUT`/`DELETE /api/items/{id}` (`main.py:274–357`) |
| 12 | Manual garment add | `POST /api/items/manual` (`main.py:286–332`) |
| 13 | Outfit builder and scoring | `score_outfit` exists (`outfit_color.py:142`). No builder UI. |
| 14 | Outfit recommendations | `GET /api/suggest` + `rank_combinations` (`main.py:359`, `outfit_color.py:244`) |
| 15 | Saved outfits (favourites) | **None.** The `outfits` table is wear history. |
| 16 | Wear tracking | `POST /api/wear` (`main.py:397–424`) |
| 17 | Profile preferences | **None** |
| 18 | PostHog analytics | **None** |
| 19 | SQL identities and F5 migration | SQLite with integer IDs and ad-hoc column migrations (`db.py:23–120`) |
| 20 | Signed Android install | **None** |

Supporting documents: README (index and conventions), SOURCE-EVIDENCE, API-AND-DEPENDENCY-REGISTER (28 proposed `/api/v1` routes), QUALITY-REPORT.

## 3. Implementation assessment

Legend: **Implemented-web** = the F5 web code covers the core behaviour · **Partial** = some behaviour exists but the PRD requirements are not met · **Missing** = nothing exists · **Verify** = needs a runtime check · **Blocked** = waiting on a decision or input from you.

- **Nothing is verified at runtime.** F5's two test scripts exist but need a live server and they write to the real `wardrobe.db` and `storage` (`test_multiuser_isolation.py`, `test_polish_features.py`). They were not run.
- **Android: completely missing.** There is no Flutter or Android project, no build config and no signing.
- **F5 backend is partial for every server-side PRD.** The core actions exist (auth, extract, CRUD, suggest, wear). None of the PRD's `/api/v1` contracts exist: UUIDs, idempotency keys, versions and `If-Match`, the error envelope, private media, jobs, cursor pagination.
- **Verify: BiRefNet probably never runs in F5.** It loads with `trust_remote_code=True` and silently falls back on any error (`matting.py:35–45`). BiRefNet's remote code normally needs `timm`/`einops`/`kornia`, which are **not installed in `F5\venv`** (they are in `wardrobe\venv`). So today's F5 baseline is likely the "colour heuristic" fallback.
- **Known F5 bugs the PRDs already address:**
  - Persisted `pattern_scale` is never read by the scorer, which reads `scale` (`outfit_color.py:193`).
  - `adjusted_score` is computed but ranking uses the raw score (`outfit_color.py:269–276`).
  - `PUT` doesn't check whether a row was actually updated.
  - Deleting an item isn't atomic: the file and the DB row are removed in separate steps.

## 4. Gap analysis

**Frontend.** Everything is missing for Android: the Flutter/Android project, design tokens and bundled font, router and session guard, every screen (welcome, pairing, signup, login, home, preview, processing, review, closet, detail, manual add, builder, recommendations, saved, wear history, profile), offline/stale/empty/error states, and accessibility (TalkBack, 48 dp touch targets, 200 % text). The F5 HTML/CSS is a design reference only and can't be reused in Flutter.

**Backend / API.** All 28 `/api/v1` routes are missing. What's needed:
- Bearer access + refresh tokens with per-device sessions.
- Argon2id hashing, plus a legacy PBKDF2 check so existing F5 users can still sign in.
- Rate limits and idempotency keys.
- `If-Match` versioning.
- The structured error envelope.
- Streaming upload validation.
- A durable extraction queue with a worker process.
- Batch save, cursor pagination, the score endpoint, bounded recommendations, saved outfits, daily-unique wear events with undo, and profile with consent.

**Pieces that can be adapted:**
- `wardrobe/backend/storage.py:27` for upload validation.
- `wardrobe/backend/routers/images.py:14` for owner-checked media.
- `wardrobe/backend/routers/auth_routes.py:76` for profile PATCH.
- `wardrobe/backend/models.py` for the ORM layout.

**Database.** Missing:
- The UUID schema of 18 tables (OOTD-19 §6), versioned migrations (no Alembic anywhere) and owner-safe composite foreign keys.
- The idempotency, outbox and audit tables.
- The migration tool (preflight, dry run, apply, verify) with an ID map and quarantine.
- A PostgreSQL install, if that's the engine you choose.

**Security gaps in F5 that the new service must not carry over:**
- `/storage` is served publicly with no owner check (`main.py:426`).
- CORS is `*` with credentials (`main.py:21–27`).
- Tokens never expire.
- There are no rate limits.
- Login reveals whether a username exists.
- Clients can supply the image path (`main.py:213–241`).
- A `demo`/`demo123` account is seeded (`db.py:108–119`).
- Records default to `user_id = 1`.

**Config / secrets.** There's no `.env.example` for F5 or for the new service. These will be needed: JWT signing key, DB URL, TLS certificate and key, PostHog project key and host. `wardrobe/.env` exists and was not read. Note that the root `.gitignore` pattern `.env.*` also hides `wardrobe/.env.example`.

**Analytics.** All missing: no SDK, adapter, consent gate, outbox or dashboards. There is no PostHog project yet, and the wizard hasn't been run.

**Testing.** No automated tests exist for the new app. The PRDs specify 206 test cases. `q2/` has reusable patterns for auth, IDOR and EXIF tests. F5's tests touch the live data and must be isolated before anyone runs them.

**Deployment.** There's no CI, Dockerfile or build scripts. There's also no Windows service or start script for the new server, no TLS bootstrap, no firewall rule, and no signing key or release manifest.

**PRD inconsistencies to resolve:**
1. The README says "Five public wardrobe filters" but lists six values (`all` plus five). OOTD-10 names the filters "Topwear/Bottomwear/Shoes/Accessories/**Other**", while the stored categories are `upper/lower/footwear/bag/headwear/full`. "Other" has no defined mapping.
2. `SOURCE-EVIDENCE.md:43` lists `/storage` as a route. It's actually a static mount.
3. `QUALITY-REPORT.md` cites screenshots (`f5_webview_*.png`) that can't be found anywhere under `C:\Users\Lenovo`.
4. The PRDs assume Flutter and PostgreSQL; neither is installed. OOTD-02 assumes HTTPS on the LAN, but the Wi-Fi profile is Public and F5's own launcher uses a public tunnel instead.

## 5. What I need from you

No passwords or keys in chat, please. Secrets will go in a local `.env` file (git-ignored) or the Windows Credential Manager. I'll create a `.env.example` showing the variable names.

### A. Blocking: needed before development starts

1. **Mobile tech: Flutter or a wrapper around the F5 web UI?** The PRDs propose Flutter, which isn't installed (it's about 2–3 GB plus learning Dart) and means rebuilding every screen. The alternative is to wrap a mobile-tuned F5 web UI in an Android shell (Capacitor or a Trusted Web Activity). That reuses `index.html` but goes against the PRDs' "native" requirements for the camera, secure storage and lifecycle. *Affects: 01, 05, 06, 20 and every screen. If undecided, no front-end work can start.*
2. **Database: PostgreSQL, as the PRDs propose, or keep SQLite?** The PRDs say PostgreSQL is "not a user-selected vendor requirement". SQLite with WAL is already in use, needs nothing installed, and handles one laptop and a few users. PostgreSQL needs installing and running as a service. *Affects: 19 and every backend feature.*
3. **Should the F5 web app keep working?** Either the new `/api/v1` service runs **next to** F5 (a new `android_app/server/` that reuses F5's AI modules, so F5 stays as it is), or F5 itself is extended and changes. *Affects: the backend layout and migration. If undecided, I can't choose where the code goes.*
4. **How does the phone reach the laptop?**
   - (a) Same Wi-Fi with a self-signed HTTPS certificate and QR pairing, as the PRD proposes. This needs the Wi-Fi switched to **Private** and a firewall rule, which you'd need to approve.
   - (b) The Cloudflare tunnel that F5 already uses. That gives real HTTPS from anywhere, but the photos then pass through Cloudflare.

   *Affects: 02 and every networked feature.*
5. **Is the existing F5 data worth migrating?** It's only 40 KB of database and 4 files. If it's just test or demo data, the 12-step migration tool (OOTD-19) can drop to "start fresh" for the MVP. If it's real, I need to know who owns the records and confirm that the `demo` account should be disabled. *Affects: 19, 04, 16.*
6. **What's in the MVP?** I'd suggest: 01, 02, 03, 04, 05, 07, 08, 09, 10, 11, 14, 16, 19 (the F5-parity journey). Later: 06 (camera), 12 (manual add), 13 (builder), 15 (saved outfits), 17 (profile), 18 (analytics), 20 (signed release). Do you agree, or should something move?
7. **Your test phone:** the model and Android version, and whether you can enable USB debugging. *Affects: the minimum SDK, plugin choices and every device test. Without it I can only test on an emulator.*

### B. Important: can be settled during development

8. **Wardrobe filter labels:** choose the visible names and say whether the "Other" PRD label should exist at all. My suggestion: All · Tops (`upper`) · Bottoms (`lower`) · Shoes (`footwear`) · Accessories (`bag`+`headwear`) · Full outfits (`full`).
9. **BiRefNet:** once I've confirmed it currently falls back, should the new service install `timm`/`einops`/`kornia` so real background removal runs? That changes the output compared with F5 as it is today. It also needs your OK to run Hugging Face remote code from the pinned revision `e2bf8e44…`.
10. **PostHog** (only needed when 18 is in scope): your project, either US or EU Cloud. Put the project key into `.env` yourself, not in chat. If it's unavailable, analytics stays off and the app still works.
11. **App name and package ID** (the working name is "OOTD"), and a **logo or icon**. None was found in the repo. Without one I'll use a text-based placeholder icon.
12. **Source timezone for F5 timestamps** (probably Asia/Kolkata?). This only matters if you migrate (item 5).
13. **Laptop always-on:** confirm it's acceptable that the app only works while the laptop is awake and the server is running. Should the server start at login?

### C. Optional: not needed for the first release

14. Where the signing key is kept (needed only for the signed release, OOTD-20).
15. Whether to fold the nested `F3`/`f4`/`F5` git repos into the root repo, or exclude the unused prototypes from it.
16. Whether to add CI (GitHub Actions) later. That needs a GitHub repo, and `gh` isn't installed.
17. Deleting the duplicate `android_app/docs/prds` or `prds`. I'll leave both until you decide.

## 6. Readiness matrix

"Blocked: A1" means waiting on item A1 above.

| Feature | PRD | Frontend | Backend | API/Data | Testing | Missing requirements | Readiness |
|---|---|---|---|---|---|---|---|
| 01 Entry/navigation/design | Yes | Missing (F5 web ref `index.html:16–48`) | N/A | Needs `/health`, `/auth/me` | None | Mobile stack; logo; final screenshots | Blocked: A1 |
| 02 Laptop connection | Yes | Missing | Missing (tunnel `.bat` only) | `/health` missing | None | Transport choice; Wi-Fi profile; TLS bootstrap | Blocked: A4 |
| 03 Registration | Yes | Missing (F5 modal ref) | Partial (`main.py:125`) | Missing UUID/idempotency/Argon2 | None (q2 pattern) | DB choice | Blocked: A2, A3 |
| 04 Login/sessions | Yes | Missing | Partial (`main.py:145–185`, `db.py:154–197`) | No refresh/per-device sessions | None | DB; legacy-hash policy | Blocked: A2, A3 |
| 05 Gallery selection | Yes | Missing (browser input only) | N/A | Native handoff only | None | Mobile stack; phone | Blocked: A1, A7 |
| 06 Camera | Yes | Missing (browser input) | N/A | Native handoff only | None | Mobile stack; phone | Later; Blocked: A1 |
| 07 Upload | Yes | Missing | Partial (`main.py:190`) + `wardrobe/backend/storage.py:27` | `photos`/`media` missing | None (q2 EXIF tests ref) | Storage layout | Blocked: A2, A3 |
| 08 AI extraction | Yes | Missing (spinner ref) | Partial, synchronous (`segmenter.py:344`) | Jobs/candidates missing | None; no golden fixtures | BiRefNet decision; CPU runtime benchmark | Blocked: A3; Verify B9 |
| 09 Review/save | Yes | Missing (F5 modal ref) | Partial (`main.py:213`) | Batch/candidates/media missing | None | — | After 08 |
| 10 Wardrobe browsing | Yes | Missing (F5 grid ref) | Partial (`main.py:243`) | Cursor/counts/search missing | None | Filter labels (B8) | After 04, 09 |
| 11 Garment edit/delete | Yes | Missing | Partial (`main.py:274–357`) | Versions/tombstones missing | None | — | After 10 |
| 12 Manual add | Yes | Missing | Partial (`main.py:286`) | Contract mismatch to fix | None | — | Later |
| 13 Outfit builder | Yes | Missing | Scorer exists (`outfit_color.py:142`) | `/outfits/score` missing | None (root `test_outfit_color.py` not run) | Golden fixtures | Later |
| 14 Recommendations | Yes | Missing (F5 modal ref) | Partial (`main.py:359`, `outfit_color.py:244`) | Bounded API missing | None | CPU cap benchmark | After 10 |
| 15 Saved outfits | Yes | Missing | Missing | Missing | None | — | Later |
| 16 Wear tracking | Yes | Missing | Partial (`main.py:397`) | Daily uniqueness/undo/timezone missing | None | Timezone source (B12) | After 14 |
| 17 Profile | Yes | Missing | Missing (`wardrobe` ref) | Missing | None | — | Later |
| 18 Analytics | Yes | Missing | Missing | Outbox missing | None | PostHog project (B10) | Later; Blocked: B10 |
| 19 SQL + migration | Yes | N/A | Partial (`db.py` SQLite) | UUID schema/migrations missing | None | DB engine; data worth migrating? | Blocked: A2, A5 |
| 20 Android install | Yes | Missing | N/A | N/A | None | Package ID, signing, phone | Later; Blocked: A7, B11 |

## 7. Technical plan (recommendation; final once section 5A is answered)

- **Current stack:** FastAPI + raw SQLite + PyTorch on CPU + a single HTML page (F5). FastAPI + SQLAlchemy + React (`wardrobe`).
- **Recommended backend:** a **new FastAPI service** in `android_app/server/`, running on F5's Python 3.11 setup.
  - It imports F5's `segmenter`, `matting`, `pattern`, `colors` and `outfit_color` **unchanged**, through an adapter. It must not import `F5/main.py`, which runs cleanup on startup.
  - Reasons: F5 stays as the untouched baseline and fallback, and the PRDs require new contracts anyway.
  - Uses SQLAlchemy 2 + Alembic. Only Alembic is new, and it's needed because the PRDs require versioned migrations.
  - Argon2 (already used in `wardrobe`) for new passwords, plus a legacy PBKDF2 verifier.
  - PyJWT for access tokens.
  - Extraction runs in **one separate worker process** fed by a DB-table queue. That's enough for one laptop with no GPU, so no Redis or Celery.
- **Database:** use whatever you choose in A2. With SQLAlchemy the schema is the same either way, so switching later is cheap. My recommendation for the MVP is SQLite, because nothing needs installing.
- **Mobile:** use whatever you choose in A1. If Flutter: Riverpod or a plain `ChangeNotifier` for state, `go_router`, `dio`, `flutter_secure_storage`, `image_picker`, and the PostHog Flutter SDK. If a wrapper: Capacitor around a mobile-tuned copy of the F5 UI.
- **Auth:** username/password, a 15-minute access token, a rotating 30-day refresh token, and per-device sessions (OOTD-04).
- **Networking:** use whatever you choose in A4. All media goes through the owner-checked `GET /api/v1/media/{id}`, never a public `/storage` mount.
- **Analytics:** off until consent. One adapter, and an outbox table on the server (OOTD-18). Deferred unless it's in the MVP.
- **Deployment:** a laptop start script plus a `.env`, and a signed APK sideloaded onto the phone. No cloud hosting.
- **Main technical risks:**
  - CPU-only extraction time on an i5-8250U is unknown. The only data point is an old 35 s artefact.
  - A local TLS trust bootstrap on Android.
  - BiRefNet's remote code and dependencies.
  - Flutter/Gradle/JDK setup on Windows.
  - Recommendation combinatorics on the CPU.

## 8. Roadmap (in dependency order; no time estimates)

| Phase | Deliverables | Exit tests |
|---|---|---|
| 0 Decisions and setup | Answers to 5A. Toolchain installed (Flutter/JDK on PATH, DB if PostgreSQL). Phone connected. Repo layout `android_app/{mobile,server,docs}`. `.env.example`. First commit. | `flutter doctor` (if Flutter) clean, `adb devices` shows the phone, server skeleton starts |
| 1 Foundation (02, 03, 04, 19-schema, 01-shell) | DB schema and migrations, `/health`, signup/login/refresh/me/logout, error envelope, rate limits. App shell with F5 theme, pairing and login. | PRD tests 02-T01–T08, 03-T01–T07, 04-T01–T08; cross-user isolation |
| 2 First vertical flow (05, 07, 08, 09, 10) | Gallery, then upload, extraction job, review/batch save, closet with private media | 05/07/08/09/10 P0 tests; golden fixtures for F5 extraction parity; CPU extraction benchmark |
| 3 F5 parity (11, 14, 16, 12, 06) | Edit/delete, recommendations, wear tracking with undo, manual add, camera | P0 tests for those PRDs; scorer parity fixtures |
| 4 Extensions (13, 15, 17) | Builder, saved outfits, profile and consent | Their P0 tests |
| 5 Migration (19) | Preflight, dry run, apply, verify on a copy of F5 data | 19-T01–T14 on synthetic data, then on a real snapshot |
| 6 Analytics (18) | Adapter, consent, outbox, dashboards | The 18-T04 funnel fixture counts exactly |
| 7 Release (20) | Signed APK, install/upgrade, laptop runbook | Full LAN journey on the real phone |

## 9. Development checklist

**Setup**
- [ ] Answers to 5A recorded in `prds/README.md` as decisions (all)
- [ ] Toolchain installed and on PATH: Flutter if chosen, JDK, `adb` (01, 20)
- [ ] `android_app/server` skeleton, `.env.example`, root `.gitignore` fix for `.env.example`, first commit (gap: config)
- [ ] Isolate F5 tests so they never touch `F5/wardrobe.db` (gap: testing)

**Backend**
- [ ] Error envelope, request IDs, rate limiter, idempotency middleware, `If-Match` helper (README conventions)
- [ ] Auth: Argon2id, legacy PBKDF2 verifier with rehash, JWT, refresh rotation, per-device sessions (03, 04)
- [ ] Upload: streaming limits, decode, EXIF strip, lossless storage, owner-scoped media (07, adapted from `wardrobe/backend/storage.py`)
- [ ] Media endpoint with an owner check (09, adapted from `wardrobe/backend/routers/images.py`)
- [ ] Extraction: queue table, worker process with lease and heartbeat, F5 adapter, stage reporting (08)
- [ ] Batch save, garments list/detail/patch/delete, manual add (09–12)
- [ ] Score, recommendations with a cap, saved outfits, wear events with undo, profile (13–17)

**Database**
- [ ] Alembic migrations for the 18 tables in OOTD-19 §6, owner-safe foreign keys, indexes (19)
- [ ] Migration CLI (preflight, dry run, apply, verify) with ID map and quarantine (19, if A5 = migrate)

**Mobile**
- [ ] Theme tokens and bundled Plus Jakarta Sans, router and session guard (01)
- [ ] Pairing (02), signup and login (03, 04), gallery (05), upload progress (07), processing (08), review (09), closet (10), detail and edit (11), recommendations and wear (14, 16)
- [ ] Offline, stale, empty and error states; TalkBack, 48 dp touch targets, 200 % text (all)

**Analytics**
- [ ] Consent-first adapter, event allowlist, identify/reset, outbox dispatcher, dashboards (18)

**Testing**
- [ ] pytest suite per PRD test table (P0 first), adapting patterns from `q2/`
- [ ] Golden fixtures for extraction and scoring parity (08, 13, 14)
- [ ] Cross-user IDOR suite covering media, jobs, idempotency and caches (README release gate)
- [ ] Device tests on the real phone (05, 06, 20)

**Security and performance**
- [ ] No public storage, no wildcard CORS, generic auth errors, demo account disabled (gap list §4)
- [ ] CPU extraction and recommendation benchmarks on this laptop; set the timeouts and caps from them (08, 14)

**Release**
- [ ] Signing key generated and stored outside the repo; signed APK; checksum; upgrade test (20)
- [ ] Laptop runbook covering start, stop, backup and the firewall (02, 20)

## 10. Risks and blockers

1. **The seven decisions in 5A.** Development can't start correctly without them.
2. **CPU-only inference.** Extraction speed and memory on this laptop are unmeasured. If it's too slow, the PRD's 300 s timeout or the user experience may not hold.
3. **The BiRefNet baseline is probably the fallback today.** "Parity with F5" needs pinning down before any golden fixtures are written.
4. **Phone ↔ laptop networking.** The Public Wi-Fi profile, client isolation on some routers, laptop sleep, and Android's TLS trust rules.
5. **Flutter on Windows** (if chosen): a first-time install of the SDK, Gradle and JDK, plus license acceptance.
6. **Live-data side effects.** F5 startup deletes old files, and F5's tests write to the live DB. Nobody should run F5 against real data during development without a backup.
7. **Scope.** 20 PRDs with 123 requirements and 206 test cases is a large build. Without the MVP cut in A6, the first usable app is far away.

## 11. Next steps

1. You answer 5A (items 1–7), and 5B where you can.
2. I record the decisions in `prds/README.md` and adjust any PRD contradictions (the filter labels, and the DB/stack lines).
3. With your OK I install or put on PATH the toolchain you chose, then connect your phone and confirm `adb devices`.
4. A read-only check of BiRefNet in a **copy** of the environment, plus a timed extraction on a sample image from `extracted_garments`, to establish the CPU baseline.
5. Scaffold `android_app/server` and `android_app/mobile`, then make the first commit, which you approve.
6. Build Phase 1 (foundation), with tests for each PRD as it goes.
