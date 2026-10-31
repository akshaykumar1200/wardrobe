---
id: android-wear-ui
files: [android_app/app/src/main/java/com/wardrobe/ootd/WearViewModel.kt, android_app/app/src/main/java/com/wardrobe/ootd/OutfitViewModel.kt, android_app/app/src/main/java/com/wardrobe/ootd/MainActivity.kt]
test: cd android_app && set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr" && .\gradlew.bat assembleDebug lintDebug
effort: high
sandbox: full
timeout: 45
---
What's missing: PRD 16 (wear tracking) at
`../android_app/docs/prds/16-wear-tracking.md`. The backend endpoints exist and
are tested; `Api.kt` already has `recordWear`, `wears`, `wearStats` and
`deleteWear`, with the `WearEvent`, `OutfitPiece` and `WearStats` models.
**Do not change `Api.kt`** — everything needed is there.

Build: a "Wore this today" action, a wear history screen with undo, and wear
counts on a garment.

## 1. `WearViewModel.kt` — new file

Copy the shape of `OutfitViewModel.kt` exactly: `var state by
mutableStateOf(...)` with `private set`, a `start()` that loads (**never from
`init`** — loading at construction fires an unauthenticated request and signs
the user straight back out), `consumeUnauthorized()`, work inside
`viewModelScope.launch { withContext(Dispatchers.IO) { ... } }`, a
`catch (e: Unauthorized)` setting an `unauthorized` flag, and a
`WearViewModelFactory`.

State: `events: List<WearEvent>?` (null = loading), `stats: WearStats?`,
`error`, `unauthorized`, `saving: Boolean`, `confirmUndo: Int?` (the event id
awaiting confirmation), `notice: String?`.

Methods: `start()` (loads both the history and the stats),
`recordWear(itemIds: List<Int>, outfitId: Int?)`, `askUndo(id)`,
`cancelUndo()`, `undo()`, `consumeNotice()`, `consumeUnauthorized()`.

`recordWear` must send **the phone's own local date**, not null:
`java.time.LocalDate.now().toString()`. The server falls back to its own
`date.today()`, which is the laptop's date and can be a day off from the
user's. `minSdk` is 26, so `java.time` is available without desugaring.

After a successful record, set `notice` to `"Recorded for today"` when the
response has `already_recorded == false`, and `"Already recorded today"` when
it is true — the server returns the existing event rather than counting twice,
and the user must be told which happened. Reload the history and stats after
recording and after an undo. Guard every write with `saving`.

## 2. `OutfitViewModel.kt` — one addition only

Add `wearNotice: String?` to the state plus `fun setWearNotice(value: String?)`
so the outfit detail sheet can show the result. Change nothing else in
this file.

## 3. `MainActivity.kt`

**a. `OutfitDetailSheet` (line ~751)** gets a **"Wore this today"** button
below the piece list and above Delete. It records the outfit's live pieces:
the `item_id` of every piece where `available` is true. If none are available
(every garment was deleted), disable the button and show
"No garments left in this outfit." Show `wearNotice` under the button.

**b. A wear history screen.** Add a `showWears` boolean in `App()` beside the
existing `showOutfits` — there is **no NavHost**, do not add a navigation
library. Reach it from a "History" action on `OutfitsScreen`'s top row.
`WearHistoryScreen(api, imageLoader, viewModel, onBack, onSignedOut)` lists
each event newest first: the date, the piece tiles (reuse
`OutfitPieceTile`), and an **Undo** that asks for confirmation before
deleting. Empty state: a short line saying nothing has been recorded yet.

**c. `GarmentDetailSheet` (line ~936)** shows that garment's wear count and
last-worn date from `WearStats`, looked up by `stats.counts[item.id.toString()]`
— the maps are keyed by **string** ids. Never worn: show "Not worn yet."
Worn once: "Worn 1 time" must read **"Worn once"**; otherwise "Worn N times".
Pass the stats in; do not make the sheet fetch them itself.

**d.** Create the `WearViewModel` in `onCreate` beside the others so it
survives rotation, and wire `unauthorized` to the same sign-out path the other
screens use, calling `consumeUnauthorized()` inside the effect.

## Threading — this crashed the app once already

**Never call an `api.*` method directly inside an `onClick`.** A bare
`api.logout()` in a click handler threw `NetworkOnMainThreadException` and
killed the process; it built clean and passed lint. Every network call goes
through the ViewModel, or through `scope.launch { withContext(Dispatchers.IO) { ... } }`
with a `rememberCoroutineScope()`.

## Done when

`.\gradlew.bat assembleDebug lintDebug` succeeds with **0 lint errors**.

## Do not

- Do not create or modify `lint-baseline.xml`.
- Do not touch `Api.kt`, `ClosetViewModel.kt`, `UploadViewModel.kt`,
  `SettingsViewModel.kt`, `Store.kt`, any Gradle file, or anything under
  `wardrobe/`.
- Do not change the `lightColorScheme` block or the `Sand`/`Sage`/`Ink`/`Muted`
  values. Use `MaterialTheme.colorScheme`.
- Do not add a dependency.
- Do not build outfit scoring or recommendations (PRD 14).
