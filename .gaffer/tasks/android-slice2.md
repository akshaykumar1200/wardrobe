---
id: android-slice2
files: [android_app/app/**]
effort: high
sandbox: full
network: true
timeout: 60
---
Add photo capture, upload and extraction review to the Android app in
`android_app/`. Slice 1 (login + closet grid) already exists and builds — read
`MainActivity.kt`, `Api.kt` and `Store.kt` first and follow their style. Do not
restructure them, do not introduce a navigation library, and do not touch
`android_app/docs/`.

## What the user must be able to do when you are done

1. From the closet, tap an "Add piece" button.
2. Choose **Take photo** (camera) or **Choose photo** (gallery).
3. The photo uploads to the laptop. **Extraction takes 35 to 50 seconds** on
   CPU, so this needs a real progress state that survives a screen rotation and
   does not look frozen. Say what is happening ("Finding your clothes...").
4. The server returns candidate garments. Show each with its cutout image,
   an editable name, and a category picker
   (`topwear`, `bottomwear`, `shoes`, `accessories`, `other`).
5. The user removes the ones they do not want and taps Save.
6. Saved pieces appear in the closet.

## The API

**Upload** — `POST /api/uploads`, `multipart/form-data`, one part named `file`.
Needs the `Authorization: Bearer` header (the OkHttp interceptor in `Api.kt`
already adds it). Response:

```json
{ "upload_id": 12,
  "original_stored_name": "<hash>.jpg",
  "duplicate_of_existing": false,
  "notice": "string or null",
  "candidates": [
    { "name": "Topwear", "category": "topwear",
      "stored_name": "<hash>.png", "color": "#3b5b4c",
      "bytes": 48213, "confidence": 0.97,
      "image_url": "/api/images/item/<hash>.png" } ] }
```

- `candidates` can be **empty** — the model found nothing it trusts. Show the
  `notice` text when present; it explains why. Do not show an empty review
  screen with a Save button.
- `confidence` is `null` for flat-lay photos (a garment photographed on its own
  rather than worn). Do not render "null%".
- `notice` is also set for flat-lays, where the server returns one unnamed
  piece in category `other` and expects the user to name it.
- **A 429 is expected**: uploads are rate limited to 5 per minute. Say so
  plainly rather than showing a generic failure.
- Timeouts: the OkHttp client in `Api.kt` uses a 30 second read timeout, which
  is **shorter than extraction takes**. Raise the read timeout for this one
  call to at least 120 seconds. Leave the other calls as they are.

**Save a reviewed piece** — `POST /api/items` with
`{"name", "category", "stored_name", "color", "bytes", "upload_id", "is_manual"}`
and the Bearer header. One call per kept candidate. `is_manual` is `false` for
anything the model produced. Returns the created item.

Crops are written to disk during extraction, before this call. Candidates the
user removes need no delete call — the server sweeps unreferenced crops on the
next upload.

## Android specifics that will cost you a rebuild if missed

- Camera: use `ActivityResultContracts.TakePicture`, which needs a
  `FileProvider` so the camera app can write into your app's storage. That
  means a `<provider>` in `AndroidManifest.xml`, a
  `res/xml/file_paths.xml`, and a cache directory for the capture. Declare
  `<uses-permission android:name="android.permission.CAMERA" />` and request it
  at runtime — on Android 6+ a manifest entry alone is not enough.
- Gallery: use `ActivityResultContracts.PickVisualMedia`. It needs **no**
  storage permission. Do not add `READ_EXTERNAL_STORAGE` or
  `READ_MEDIA_IMAGES`.
- The server rejects anything over **10 MB** with a 413, and accepts only
  JPEG, PNG and WebP. Modern phone cameras exceed 10 MB. Downscale and
  re-encode as JPEG before uploading — longest side 2048 px is plenty, since
  the server works at 1280 px internally. Do this off the main thread.
- Upload must survive the screen turning off for a minute. Run it from a
  `ViewModel` scope, not from a `LaunchedEffect` tied to the composable, or a
  rotation restarts a 40 second job.
- Item images are **transparent PNGs**. Draw them on white, as `GarmentCard`
  already does.

## Keep it small

No new dependencies. No Hilt, no Room, no WorkManager, no navigation library.
`androidx.lifecycle:lifecycle-viewmodel-compose` is acceptable if the ViewModel
needs it; add nothing else. Screen state can stay a sealed class plus
`mutableStateOf`, matching slice 1.

## Done when

- `cd android_app && set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr" && gradlew.bat assembleDebug`
  gives BUILD SUCCESSFUL.
- `gradlew.bat lint` has no errors.
- Nothing outside `android_app/app/` changed.

Run the build yourself and quote the real Gradle output in your summary. If it
fails, fix it and build again. Do not report a guess.
