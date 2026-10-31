---
id: android-suggest-ui
files: [android_app/app/src/main/java/com/wardrobe/ootd/Api.kt, android_app/app/src/main/java/com/wardrobe/ootd/SuggestViewModel.kt, android_app/app/src/main/java/com/wardrobe/ootd/MainActivity.kt]
test: cd android_app && set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr" && .\gradlew.bat assembleDebug lintDebug
effort: high
sandbox: full
timeout: 45
---
What's missing: PRD 14's screen
(`../android_app/docs/prds/14-outfit-recommendations.md`). The backend landed
today and is proven against a real wardrobe; nothing in the app calls it.

## The endpoint

`GET /api/outfits/recommendations?limit=5` (cap 10). Verified live response:

```json
{"suggestions": [
  {"items": [{"id": 47, "name": "Top", "category": "topwear",
              "image_url": "/api/images/item/694d....png"}],
   "score": 63, "verdict": "solid",
   "notes": ["3 competing colours. Drop one to a neutral and the whole thing settles."],
   "palette": {"palette": [{"hex": "#243247", "name": "charcoal", "share": 0.319}]}}]}
```

Note the nesting: **`palette` is an object whose `palette` key holds the list.**
`score` is a number 0–100, `verdict` a short word such as "solid".
`image_url` may be **null** for a garment with no photo.

With no topwear or no bottomwear the response is
`{"suggestions": [], "guidance": "<what to add>"}` — **show that sentence**,
never an unexplained empty screen. A 400 means too many combinations; show its
`detail` text.

## 1. `Api.kt`

Add `@Serializable` models and one method, in the style of the existing
`outfits()` / `wears()`:

```kotlin
data class SuggestedPiece(id: Int, name: String, category: String, image_url: String? = null)
data class PaletteColor(hex: String, name: String? = null, share: Double = 0.0)
data class PaletteWrap(palette: List<PaletteColor> = emptyList())
data class Suggestion(items: List<SuggestedPiece>, score: Double, verdict: String,
                      notes: List<String> = emptyList(), palette: PaletteWrap? = null)
data class Suggestions(suggestions: List<Suggestion> = emptyList(), guidance: String? = null)
```

`fun suggestions(limit: Int = 5): Suggestions`. Throw `Unauthorized` on 401 as
the other methods do. Reuse the existing `client` and `json`; the `Json`
instance already ignores unknown keys, so extra palette fields are fine.

## 2. `SuggestViewModel.kt` — new file

Copy the shape of `WearViewModel.kt`: `var state by mutableStateOf(...)` with
`private set`, a `start()` that loads, `consumeUnauthorized()`, work in
`viewModelScope.launch { withContext(Dispatchers.IO) { ... } }`, a
`catch (e: Unauthorized)`, and a `SuggestViewModelFactory`.

**Never load from `init`** — that fires an unauthenticated request and signs
the user straight back out.

State: `suggestions: List<Suggestion>?` (null = loading), `guidance: String?`,
`index: Int`, `error: String?`, `unauthorized: Boolean`, `loading: Boolean`.

Methods: `start()`, `refresh()`, `next()`, `consumeUnauthorized()`.

`next()` moves to the following suggestion, wrapping to the first. **When there
is only one suggestion, do not pretend there is another** — expose that so the
screen can say "That's the only combination your wardrobe allows." PRD FR4 is
explicit about this.

## 3. `MainActivity.kt` — one screen

Add `showSuggest` beside the existing `showOutfits` / `showWears` booleans.
There is **no NavHost**; do not add a navigation library. Reach it from a
"Suggest" action on `OutfitsScreen`'s top row, next to "History".

`SuggestScreen(api, imageLoader, viewModel, onBack, onSignedOut)` shows one
suggestion at a time:

- The garment images in a row (reuse `OutfitPieceTile`'s look; a null
  `image_url` falls back to the name, as that tile already does).
- The **score and verdict**, e.g. "63 · solid".
- The **notes**, each on its own line — they are the useful part.
- The **palette** as small colour swatches from
  `palette?.palette`, each a filled rounded box of that `hex` with its `name`
  beneath. Parse with `android.graphics.Color.parseColor(hex)` wrapped in
  `runCatching` and skip any colour that fails, so one bad hex cannot crash
  the screen.
- A **Next** button, and a line saying which you are on ("2 of 5").
- **A line stating that ranking is by colour only.** The scorer does not use
  wear history, and PRD FR3 forbids implying otherwise.

Empty: show `guidance` when present, otherwise a short line. Error: show it
with a retry.

## Threading — this crashed the app once

**Never call an `api.*` method inside an `onClick`.** A bare `api.logout()` in
a click handler threw `NetworkOnMainThreadException` and killed the process; it
built clean and passed lint. Network calls go through the ViewModel.

## Done when

`.\gradlew.bat assembleDebug lintDebug` succeeds with **0 lint errors**.

## Do not

- Do not create or modify `lint-baseline.xml`.
- Do not touch `WearViewModel.kt`, `OutfitViewModel.kt`, `ClosetViewModel.kt`,
  `UploadViewModel.kt`, `SettingsViewModel.kt`, `Store.kt`, any Gradle file, or
  anything under `wardrobe/`.
- Do not change the `lightColorScheme` block or the `Sand`/`Sage`/`Ink`/`Muted`
  values. Use `MaterialTheme.colorScheme` — except for the palette swatches,
  which are the garment's real colours.
- Do not add a dependency.
- Do not add a "save as outfit" or "wear this" action here; those screens exist
  already and wiring them in is a separate change.
