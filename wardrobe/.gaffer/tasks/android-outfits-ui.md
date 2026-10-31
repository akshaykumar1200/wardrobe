---
id: android-outfits-ui
files: [android_app/app/src/main/java/com/wardrobe/ootd/Api.kt, android_app/app/src/main/java/com/wardrobe/ootd/OutfitViewModel.kt, android_app/app/src/main/java/com/wardrobe/ootd/MainActivity.kt]
test: cd android_app && set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr" && .\gradlew.bat assembleDebug lintDebug
effort: high
sandbox: full
timeout: 45
---
What's missing: the backend gained outfit and wear-tracking endpoints today and
**nothing in the Android app calls them**. Build the data layer plus two
screens: a saved-outfits list and an outfit builder. Wear-tracking UI is a
separate task — add its API methods here, but no wear screens.

## The endpoints that now exist

All take the Bearer token the existing `Api` interceptor already attaches.

- `POST /api/outfits` body `{"name": str, "item_ids": [int]}` (1–8 distinct) →
  `OutfitOut`
- `GET /api/outfits` → `[OutfitOut]`, newest first
- `GET /api/outfits/{id}` → `OutfitOut`, 404 if not yours
- `DELETE /api/outfits/{id}` → `{"deleted": id}`
- `POST /api/wears` body `{"item_ids": [int], "worn_on": "YYYY-MM-DD"|null, "outfit_id": int|null}` → `WearOut`
- `GET /api/wears?limit=50` → `[WearOut]`
- `GET /api/wears/stats` → `{"counts": {"<item_id>": int}, "last_worn": {"<item_id>": "YYYY-MM-DD"}}`
- `DELETE /api/wears/{id}` → `{"deleted": id}`

`OutfitOut` is `{id, name, created_at, items: [OutfitItemOut]}`.
`WearOut` is `{id, worn_on, outfit_id, created_at, items: [OutfitItemOut], already_recorded: bool}`.
`OutfitItemOut` is `{item_id: int|null, name: str, available: bool, image_url: str|null}`.

`available: false` means the garment was deleted but the record kept its name.
**Render those as a placeholder tile with the name and the word "unavailable"
— never hide them and never crash on the null `item_id`/`image_url`.**

## 1. `Api.kt` — add models and methods, match the existing style

Add `@Serializable data class Outfit(id, name, created_at, items)`,
`OutfitPiece(item_id: Int? = null, name: String, available: Boolean = true, image_url: String? = null)`,
`WearEvent(id, worn_on, outfit_id: Int? = null, created_at, items, already_recorded: Boolean = false)`
and `WearStats(counts: Map<String, Int> = emptyMap(), last_worn: Map<String, String> = emptyMap())`.

Add suspend-free blocking methods in the same shape as the existing
`items()` / `updateItem()` / `deleteItem()` — they are called from
`Dispatchers.IO` by the ViewModel, so do **not** add coroutine machinery:
`outfits()`, `createOutfit(name, itemIds)`, `outfit(id)`, `deleteOutfit(id)`,
`recordWear(itemIds, outfitId, wornOn)`, `wears(limit)`, `wearStats()`,
`deleteWear(id)`.

Throw `Unauthorized` on 401 exactly as the existing methods do — that is what
drives the sign-out path. Reuse the existing `client`, `json` and
`imageUrl(path: String)`; add nothing new.

## 2. `OutfitViewModel.kt` — new file, copy the shape of `ClosetViewModel.kt`

Read `ClosetViewModel.kt` first and follow it exactly: `var state by
mutableStateOf(...)` with `private set`, a `start()` that loads (**never load
from `init` —** that fired an unauthenticated request before login and bounced
the user straight back out), `consumeUnauthorized()`, work in
`viewModelScope.launch { withContext(Dispatchers.IO) { ... } }`, a
`catch (e: Unauthorized)` that sets an `unauthorized` flag, and an
`OutfitViewModelFactory`.

State needs: `outfits: List<Outfit>?` (null = still loading), `error`,
`unauthorized`, `selected: Outfit?`, `confirmDelete: Boolean`,
`saving: Boolean`, `detailError: String?`, and for the builder
`building: Boolean`, `pickable: List<Item>`, `picked: Set<Int>`,
`builderName: String`, `builderError: String?`.

Methods: `start()`, `open(outfit)`, `close()`, `askDelete()`, `cancelDelete()`,
`delete()`, `openBuilder()`, `cancelBuilder()`, `toggle(itemId)`,
`editBuilderName(value)`, `save()`, `consumeUnauthorized()`.

`openBuilder()` loads the garments to choose from via `api.items("all", "")`.
`toggle` must refuse a 9th pick and set `builderError` to
"Pick up to 8 pieces." — the server rejects more than 8, so stop it here.
`save()` validates a non-blank name and at least one pick before calling.
Guard every save and delete with the `saving` flag so a double tap cannot
fire two requests.

## 3. `MainActivity.kt` — two screens, keep the existing navigation style

There is **no NavHost**; `App()` switches on plain `var showSettings by
remember { mutableStateOf(false) }` booleans. Add `showOutfits` the same way.
Do not introduce a navigation library.

- Create the `OutfitViewModel` in `onCreate` beside the others and pass it
  down, so it survives rotation.
- `ClosetScreen` gets an `onOutfits: () -> Unit` and a way to reach it next to
  the existing Settings action.
- `OutfitsScreen(api, imageLoader, viewModel, onBack, onSignedOut)`: a back
  action, a "New outfit" button, then the list. Each row shows the outfit name
  and a row of small garment thumbnails. Empty state: a short line telling the
  user to create one. Tapping a row opens a detail sheet with the full piece
  list and a Delete that asks first. Follow `GarmentDetailSheet` for the sheet
  pattern and `GarmentCard` for thumbnails.
- `OutfitBuilderSheet`: a name field, a selectable grid of garments, and Save.
  A picked garment must be **visibly** picked — a border or check overlay in
  `Sage`, not colour alone. Show the count as "3 of 8 picked". Disable Save
  while `saving` is true.
- Wire `unauthorized` to the same sign-out path `ClosetScreen` already uses,
  calling `consumeUnauthorized()` in the effect so a later sign-in is not
  bounced.

Every screen must scroll: the login and registration screens both needed
`verticalScroll` added after text fields pushed content off a small phone.

## Done when

`gradlew.bat assembleDebug lintDebug` succeeds with **0 lint errors**. Warnings
are acceptable; there are 17 today.

## Do not

- Do not create or modify `lint-baseline.xml`. A baseline hid a real bug once.
- Do not touch `ClosetViewModel.kt`, `UploadViewModel.kt`, `SettingsViewModel.kt`,
  `Store.kt`, any Gradle file, or anything under `wardrobe/`.
- Do not change the `lightColorScheme` block or the `Sand`/`Sage`/`Ink`/`Muted`
  colour values. Use `MaterialTheme.colorScheme`.
- Do not add a dependency. Compose, Coil, OkHttp and kotlinx.serialization are
  already there.
- Do not build wear-tracking screens, outfit scoring, or recommendations.
