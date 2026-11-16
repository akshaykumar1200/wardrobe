---
id: android-slice3
files: [android_app/app/**]
effort: high
sandbox: full
network: true
timeout: 60
---
Add browsing and management to the closet screen of the Android app in
`android_app/`. Slices 1 and 2 exist and build: read `MainActivity.kt`,
`Api.kt`, `Store.kt` and `UploadViewModel.kt` first and match their style.
Do not restructure them. Do not add a navigation library. Do not touch
`android_app/docs/`.

## What the user must be able to do

1. **Filter by category** from a row of chips above the grid: All, Topwear,
   Bottomwear, Shoes, Accessories, Other. The selected chip is visually clear.
2. **Search by name** from a text field. Searching and filtering combine.
3. **Tap a garment** to open a detail sheet showing the cutout larger, with:
   - an editable name
   - a category picker
   - Save, and Delete (with a confirmation step, because it cannot be undone)
4. After a save or delete the grid reflects the change without a full reload
   flicker.
5. An empty result reads differently from an empty closet: "No pieces match"
   versus the existing "Nothing here yet".

## Use the server's own filtering — do not filter in the app

`GET /api/items` already takes query parameters, so do not pull everything and
filter client side:

- `category` — one of `topwear`, `bottomwear`, `shoes`, `accessories`, `other`,
  or `all` (or omit it) for everything.
- `q` — case-insensitive substring match on the name.
- `sort` — `newest` (default) or `oldest`.

**Debounce the search** by about 300 ms. A request per keystroke will hit the
rate limiter and waste the laptop's CPU.

Other endpoints, both needing the `Authorization: Bearer` header the OkHttp
interceptor already adds:

- `PATCH /api/items/{id}` with any of `{"name", "category", "color"}`. Returns
  the updated item. Sending a field as null leaves it unchanged.
- `DELETE /api/items/{id}` returns `{"deleted": <id>}`.

Both return **404** when the item is not yours or does not exist — treat that
as "it is gone" and drop it from the grid rather than showing an error.

## Things that will bite

- An item whose image file is missing on the server returns **404 for the
  image** while the row itself still lists fine. Show a quiet placeholder in
  that tile, not a crash and not an infinite spinner. This is real: there are
  currently rows in the database in exactly that state.
- `color` is a `#rrggbb` string and can be null. Do not parse it without a
  null check; a malformed value must not crash the screen.
- Keep the transparent-PNG-on-white treatment from `GarmentCard`.
- The detail sheet must survive rotation, like the upload flow does. Hold its
  state where `UploadViewModel` holds its own, not in a composable that dies.
- Deleting the last item in a filtered view should land on the "No pieces
  match" state, not an empty white screen.

## Keep it small

No new dependencies beyond what the project already declares. No Room, no
Paging, no Hilt. Server-side filtering means you need no local cache.

## Done when

- `cd android_app && set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr" && gradlew.bat assembleDebug lint`
  gives BUILD SUCCESSFUL with no lint errors.
- **Do not create a `lint-baseline.xml`.** If lint reports something, fix it.
  A baseline was added in the previous slice and deleted; do not reintroduce it.
- Nothing outside `android_app/app/` changed.

Run the build yourself and quote the real Gradle output in your summary. If it
fails, fix it and build again. Do not report a guess.
