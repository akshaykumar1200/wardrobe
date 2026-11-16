---
id: android-slice4
files: [android_app/app/**]
effort: high
sandbox: full
network: true
timeout: 60
---
Add account registration to the Android app in `android_app/`. Slices 1-3
exist and build: read `MainActivity.kt`, `Api.kt`, `Store.kt`,
`ClosetViewModel.kt` and `UploadViewModel.kt` first and match their style.
Do not restructure them. No navigation library. Do not touch
`android_app/docs/`.

This implements PRD OOTD-03, but **that document was written against a
different backend** (F5: usernames, UUID primary keys, idempotency keys,
`/api/auth/register`). The real server uses email, integer ids and
`/api/auth/signup`. Follow this brief, not the PRD. Do not invent usernames,
UUIDs or idempotency keys.

## What the user must be able to do

1. From the login screen, tap "Create account" to reach a registration screen.
2. Enter email, password, confirm password, and an optional display name.
3. On success they are **signed straight in** and land on the closet — not
   returned to the login screen to type everything again.
4. From registration, get back to login without losing the laptop address.

## The API

**`POST /api/auth/signup`** — no auth header needed.
Body: `{"email": "...", "password": "...", "display_name": "..."}`
`display_name` may be omitted or null; the server then uses the part of the
email before the `@`.

Returns the created user: `{id, email, display_name, is_admin, created_at}`.
**It does not return a token and does not sign anyone in.** After a successful
signup, call the existing `Api.login(email, password)` to get a token and store
it exactly as `LoginScreen` already does.

Failures that must read clearly:
- **400** — the email is already registered. Say so and point at signing in.
- **422** — validation failed. The server requires a valid email address and a
  password of **at least 10 characters**. Mirror both rules in the app so the
  user is told before a round trip, but still handle a 422 arriving anyway.
- **429** — signup is rate limited to **3 per minute** per IP, which is easy to
  hit while testing. Say "Too many attempts. Wait a minute." as the login
  screen already does for its own limit.

## Requirements worth keeping from the PRD

- Confirm-password is checked **on the device only** and never sent.
- Errors attach to the field they belong to, not one generic banner.
- Display name is trimmed; 1-60 characters if given.
- No email verification, no social login, no password reset. Out of scope.
- Do not collect a phone number or anything else. Email and password only.

## Watch out for

- The **laptop address** must be editable from the registration screen too, or
  a brand new user cannot reach a server at all. Share `Store.baseUrl` as the
  login screen does, and write it before the signup call.
- Signup followed by login is **two requests against two different rate
  limits** (3/min and 5/min). Do not retry either automatically.
- Keep the sand/sage palette. Note that the Material3 filter chips on the
  closet currently render with the default purple selection colour; if you
  touch shared theming, fix that to use the sage `#3B5B4C`, otherwise leave it.
- `signedIn` state lives in `App`. Registration succeeding must flip it the
  same way login does, so the closet's `start()` runs normally.

## Done when

- `cd android_app && set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr" && gradlew.bat assembleDebug lint`
  gives BUILD SUCCESSFUL with no lint errors.
- **Do not create a `lint-baseline.xml`.**
- Nothing outside `android_app/app/` changed.

Run the build yourself and quote the real Gradle output. If it fails, fix it
and build again. Do not report a guess.
