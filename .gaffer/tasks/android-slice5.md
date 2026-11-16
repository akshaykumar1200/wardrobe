---
id: android-slice5
files: [android_app/app/**]
effort: high
sandbox: full
network: true
timeout: 60
---
Add manual garment entry to the Android app in `android_app/` — PRD OOTD-12.
Slices 1-4 exist and build: read `MainActivity.kt`, `Api.kt`, `Store.kt`,
`ClosetViewModel.kt` and `UploadViewModel.kt` first and match their style. No
navigation library, no new dependencies. Do not touch `android_app/docs/`.

## What this is for

A garment you own but have not photographed — "black jeans", "grey wool
scarf". It goes in the closet as a real item with **no image at all**, so it
can be found by search and counted in the wardrobe.

## What the user must be able to do

1. On the closet, the existing "Add piece" control currently goes straight to
   the camera/gallery chooser. Add a third option to that chooser:
   **"Enter details"** alongside Take photo and Choose photo.
2. That opens a small form: name (required) and category (the same picker the
   garment detail sheet already uses). Nothing else — no colour picker, no
   brand, no size.
3. Save adds it to the closet immediately and the grid reflects it.
4. Cancel returns without creating anything.

## The API — the backend was changed for this, read carefully

`POST /api/items` with the `Authorization: Bearer` header.

```json
{ "name": "Black jeans", "category": "bottomwear", "is_manual": 1 }
```

- **`stored_name` is now optional and must be omitted** for a manual garment.
  The server stores an empty string and the item has no image.
- **Do not send `bytes`.** The server now derives size from the file on disk
  and ignores anything the client sends. `Api.saveCandidate` currently sends
  `bytes`; that is harmless but should be dropped while you are in there.
- **`category` is now validated server side** against exactly
  `topwear`, `bottomwear`, `shoes`, `accessories`, `other`. Anything else gets
  a **422**. The same validation now applies to `PATCH /api/items/{id}`.
- **`name` must be 1-120 characters** after trimming, or **422**.
- A manual item comes back with `"stored_name": ""` and `"bytes": 0`. Its
  `image_url` will be `/api/images/item/` which does not resolve.

## The part most likely to go wrong

`GarmentCard` builds its image URL from `item.image_url`. For a manual item
that URL is a dead end, and Coil will fire a pointless request that 404s on
every grid pass. **Detect the empty `stored_name` and skip the image load
entirely**, showing the same quiet placeholder the closet already uses for a
missing file — but ideally distinguishable, since "no photo by choice" is not
the same as "photo is missing". A small neutral label is enough; do not invent
an icon set.

## Keep it small

Reuse the category picker from the detail sheet rather than writing a second
one. Hold the form state where the other screens hold theirs. A manual item is
created, listed, renamed and deleted through the endpoints that already exist,
so no other API work is needed.

## Done when

- `cd android_app && set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr" && gradlew.bat assembleDebug lint`
  gives BUILD SUCCESSFUL with no lint errors.
- **Do not create a `lint-baseline.xml`.**
- Nothing outside `android_app/app/` changed.

Run the build yourself and quote the real Gradle output. If it fails, fix it
and build again. Do not report a guess.
