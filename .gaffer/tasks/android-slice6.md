---
id: android-slice6
files: [android_app/app/**]
effort: high
sandbox: full
network: true
timeout: 60
---
Finish the app: add a Settings screen, and make the whole app use one palette.
Slices 1-5 exist and build. Read `MainActivity.kt`, `Api.kt`, `Store.kt`,
`ClosetViewModel.kt` and `UploadViewModel.kt` first and match their style.
No navigation library, no new dependencies. Do not touch `android_app/docs/`.

## 1. Settings screen — PRD OOTD-17

Reachable from the closet (a "Settings" text action beside "Sign out", or
replacing it and moving Sign out inside — your call, but it must be one tap
from the closet).

It shows and lets the user change:

- **Display name.** `PATCH /api/auth/me` with `{"display_name": "..."}` and
  the Bearer header. The server now **validates it: 1-60 characters after
  trimming**, so blank or over-long returns **422**. It trims before saving,
  so show the trimmed value back. Returns the updated user object.
- **Laptop address.** Read and write `Store.baseUrl`. This fixes a real
  problem: today the login screen is the only place to change it, so if the
  laptop's DHCP address moves while the user is signed in, the closet just
  fails and they have to sign out to fix it. Changing it here must take effect
  immediately for subsequent requests.
- **Who is signed in** — show the account's email, read only.
- **Sign out**, behaving exactly as the closet's current one does.

Fetch the current user with `GET /api/auth/me`, which returns
`{id, email, display_name, is_admin, created_at}`. Handle a 401 there the same
way the closet does.

## 2. One palette — no stray Material3 purple

The app defines `Sand #F7F6F2`, `Sage #3B5B4C`, `Ink #1C1D1F`, `Muted`. The
filter chips were fixed to use them, but other Material3 components still fall
back to the library's default purple. Confirmed on a real device:

- The **"Add a piece"** dialog — title, "Take photo", "Choose photo",
  "Enter details" and "Cancel" all render purple on lavender.
- The **manual entry sheet**: its category dropdown trigger and menu items.
- **Outlined text fields** show a purple focus ring and purple label when
  focused, on every screen.

Fix these properly rather than one component at a time: define a
`MaterialTheme` `colorScheme` built from the existing constants (`primary` =
Sage, `surface`/`background` = Sand, `onSurface` = Ink, and the matching
`on*` colours so text stays legible), and apply it in the existing
`MaterialTheme { }` call in `App`. Then remove any now-redundant per-component
colour overrides you find, so there is one source of truth. Do not change any
layout, label, size or spacing — colour only.

Check it on: the Add a piece dialog, the manual entry sheet and its dropdown,
a focused text field on login, and the closet chips.

## Done when

- `cd android_app && set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr" && gradlew.bat assembleDebug lint`
  gives BUILD SUCCESSFUL with no lint errors.
- **Do not create a `lint-baseline.xml`.**
- Nothing outside `android_app/app/` changed.

Run the build yourself and quote the real Gradle output. If it fails, fix it
and build again. Do not report a guess.
