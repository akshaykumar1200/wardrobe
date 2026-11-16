---
id: android-slice1
files: [android_app/**]
effort: high
sandbox: full
network: true
timeout: 60
---
Build the first working slice of a native Android client for the wardrobe
backend that already runs in `wardrobe/`. Kotlin + Jetpack Compose. Android
only — no iOS, no cross-platform framework, no Flutter.

Scope of THIS task, and nothing more: the phone can sign in to the laptop and
see its wardrobe. Login, the closet grid, logout. Do NOT build photo upload,
camera, the extraction review screen, outfits, wear tracking or a settings
screen. Those are later slices. A smaller app that builds and runs beats a
bigger one that does not.

## Where

New Gradle project at `android_app/`. That folder currently contains only
`docs/prds/` — 24 product specs. **Read none of them and change none of them**;
they describe a much larger Flutter app and are out of date. Put the project
files alongside `docs/`, leaving it untouched.

Package: `com.wardrobe.ootd`. App label: `OOTD`.

## Machine facts — get these wrong and nothing builds

- **There is no system JDK.** `java` is not on PATH and `JAVA_HOME` is unset.
  Use the JDK bundled with Android Studio:
  `C:\Program Files\Android\Android Studio\jbr`
  Set `JAVA_HOME` to it in the shell before invoking Gradle, e.g. in cmd.exe:
  `set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"`
- SDK is at `C:\Users\Lenovo\AppData\Local\Android\Sdk`. `ANDROID_HOME` is
  unset, so write `android_app/local.properties` with
  `sdk.dir=C\:\Users\Lenovo\AppData\Local\Android\Sdk`
  (escaped exactly like that — it is a Java properties file). This file is
  machine-specific: add it to `android_app/.gitignore`, never commit it.
- Installed SDK platforms are **android-35** and android-36.1; build-tools
  **35.0.0** and 36.0.0. Use `compileSdk = 35` and `targetSdk = 35`; both are
  present, so no download is needed for them.
- `minSdk = 26`. The target phone's Android version is unknown, so pick a floor
  that covers essentially every live device.
- Generate the Gradle wrapper and commit `gradlew`, `gradlew.bat` and
  `gradle/wrapper/`. Network is available, so Gradle and the dependencies will
  download on first build. Expect that first build to be slow.

## The API you are talking to

Base URL default: `http://192.168.29.222:8000` (the laptop on the same Wi-Fi).
Put it in a constant that is easy to change, and let the login screen edit it
and remember it — the laptop's DHCP address can change. Do not build QR pairing
or certificate verification.

1. **Login** — `POST /api/auth/login?client=mobile`
   Body: `{"email": "...", "password": "..."}`
   200 response: `{"ok": true, "user": {...}, "token": "<session token>"}`
   The `client=mobile` query parameter is required. Without it the server sets
   an httponly cookie and returns no token, which a native client cannot use.
2. **Every other call** must send `Authorization: Bearer <token>`.
3. **Items** — `GET /api/items` → a JSON array of
   `{id, user_id, name, category, stored_name, color, bytes, upload_id,
   is_manual, created_at, image_url}`.
   `category` is one of `topwear`, `bottomwear`, `shoes`, `accessories`,
   `other`. `color` is a `#rrggbb` string. `image_url` is a path like
   `/api/images/item/<hash>.png` — join it to the base URL.
4. **Images** — the `image_url` path. **Requires the same Bearer header**; an
   unauthenticated request returns 404, so Coil must be given an OkHttp client
   that attaches the token, or every tile will show a broken image.
5. **Logout** — `POST /api/auth/logout` with the Bearer header. The server
   deletes the session, so also clear the stored token locally.

A 401 from any call means the session is gone: drop the stored token and return
to the login screen.

## Things that will silently break if you skip them

- **Cleartext HTTP.** The laptop serves plain `http://`, and Android 9+ blocks
  that by default. Add a `res/xml/network_security_config.xml` permitting
  cleartext, reference it from `AndroidManifest.xml`, and keep it scoped to
  local addresses rather than turning cleartext on globally.
- `<uses-permission android:name="android.permission.INTERNET" />`.
- The item images are **PNG cutouts with a transparent background**. Draw each
  tile on a light surface, or the garments vanish. The backend's web UI uses
  background `#F7F6F2`, primary `#3B5B4C`, text `#1C1D1F`, white cards — match
  those so the phone app looks like the same product.

## Dependencies — keep this list short

Compose (via the BOM), `kotlinx-serialization-json`, OkHttp, and Coil for
Compose. **Do not add Retrofit**: there are three endpoints here and OkHttp
calls them with less machinery. Do not add Hilt, Dagger, Room or a navigation
library — two screens do not need one; a state value in a top-level composable
is enough. Do not add any dependency not on this list.

Store the token in app-private `SharedPreferences`.
`shortcut: app-private prefs, not EncryptedSharedPreferences — readable only
with root or a debug build; upgrade if the app ever holds more than a session
token.` Put that comment in the code where the token is written.

## Done when

- `cd android_app && set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr" && gradlew.bat assembleDebug`
  completes with BUILD SUCCESSFUL and produces
  `android_app/app/build/outputs/apk/debug/app-debug.apk`.
- `gradlew.bat lint` reports no errors (warnings are fine).
- `android_app/.gitignore` covers `build/`, `.gradle/`, `local.properties` and
  `*.apk`.
- Nothing outside `android_app/` is modified, and `android_app/docs/` is
  byte-identical to how you found it.

Run the build yourself and state in your summary whether it succeeded, with the
real Gradle output. If it fails, fix it and build again — do not report a
guess.
