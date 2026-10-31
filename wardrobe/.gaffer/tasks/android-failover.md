---
id: android-failover
files: [android_app/app/src/main/java/com/wardrobe/ootd/Store.kt, android_app/app/src/main/java/com/wardrobe/ootd/Api.kt, android_app/app/src/main/java/com/wardrobe/ootd/MainActivity.kt, android_app/app/src/main/java/com/wardrobe/ootd/SettingsViewModel.kt]
test: cd android_app && set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr" && .\gradlew.bat assembleDebug lintDebug
effort: high
sandbox: full
timeout: 45
---
Two defects found by running the app on a real phone (Galaxy A31, Android 12)
against the live backend. Read `Api.kt`, `Store.kt` and `MainActivity.kt` first.

## 1. The app dies when the laptop is off

`Store.baseUrl` holds one address, typed by hand, and all ~25 calls in `Api.kt`
build their URL from `"${store.baseUrl}/api/..."`. When the laptop is asleep
every call throws `"Cannot reach the laptop at ..."` and the app is unusable.

The backend is now also deployed as a Hugging Face Space. **Both servers talk to
the same Postgres database**, so a session token minted by one is accepted by
the other. That is what makes this cheap: switching servers needs no re-login,
no re-sync and no merge. Do not build any of those.

### What to add

- `Store`: a second stored address, `cloudUrl`, beside `baseUrl`. Same
  read/write/trim treatment as `baseUrl`. Default it to empty string; an empty
  `cloudUrl` must behave exactly like today (laptop only, same error).

- `Api`: one private `base()` that every request URL goes through, replacing
  every `${store.baseUrl}` in the file. It returns the laptop address when the
  laptop answers, otherwise the cloud address.

  - Reachability is `GET <laptop>/healthz`, which exists and deliberately does
    not touch the database, so it stays fast when the database is asleep.
  - Probe with a **separate OkHttpClient whose connect and read timeouts are 2
    seconds**. The shared client's timeouts are tuned for a 40-second upload; a
    sleeping laptop must not stall the UI for that long.
  - Cache the choice for **30 seconds** so a screen that fires four requests
    probes once, not four times.
  - Expose `fun forgetServer()` that clears the cache. `Api` must call it
    whenever a request fails with `IOException`, so the next call re-probes
    instead of hammering a server that just went away. This is what moves the
    app back to the laptop when it wakes up.

- `base()` does network I/O, so it must never run on the main thread. Every
  `Api` method is already called inside `withContext(Dispatchers.IO)` by the
  ViewModels — keep it that way and do not add a coroutine launch inside `Api`.

- The error copy says "Cannot reach the laptop at X" in about eight places.
  When a cloud address is set that sentence is wrong. Make it name what was
  actually tried, e.g. "Cannot reach your laptop or the cloud server."

- `SettingsViewModel` and the Settings screen in `MainActivity`: a "Cloud
  address" field beside the existing "Laptop address", saved the same way, plus
  one line of text naming which server answered the last request. Match the
  surrounding style exactly — same `OutlinedTextField`, same Button, same
  palette colours. Do not restyle the screen.

## 2. The system back button quits the app

From any inner screen, one press of Android's back button finishes the Activity
instead of going up a level. Confirmed on the device: from Suggestions, one
press lands on the launcher. The screens are plain booleans (`showOutfits`,
`showWears`, `showSuggest`, `showSettings`) with no back handling at all.

Add `androidx.activity.compose.BackHandler` so back does this:

| From | Goes to |
|---|---|
| Wear history | Outfits |
| Suggestions | Outfits |
| Outfits | Closet |
| Settings | Closet |
| Closet | leaves the app, as now |

Wear history and Suggestions are opened *from* Outfits, so both booleans are
true at once. Back must close only the inner one and land on Outfits, not jump
to the closet. Get the handler ordering right for that.

`androidx.activity:activity-compose` is already a dependency; do not add one.

## Done when

`cd android_app && .\gradlew.bat assembleDebug lintDebug` succeeds with **0 lint
errors**, every request URL in `Api.kt` goes through `base()`, and no
`${store.baseUrl}` remains in a request URL.

## Do not

- Do not add a NavHost or any navigation library. The booleans stay.
- Do not add any dependency.
- Do not change anything under `wardrobe/` — the backend is finished and tested.
- Do not change the colour palette or restyle existing screens.
- Do not cache, queue or sync data between the two servers. They share one
  database; there is nothing to reconcile.
- Do not probe the cloud server to decide. The laptop is preferred whenever it
  answers; the cloud is simply the fallback.
