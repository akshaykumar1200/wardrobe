---
id: android-fix-ui
files: [android_app/app/**]
effort: medium
sandbox: full
network: true
timeout: 45
---
Two defects found by running the app on a real phone (Galaxy A31, Android 12).
Fix both. Add no features. Read `MainActivity.kt` first and match its style.
Do not touch `android_app/docs/`.

## 1. The auth screens cannot scroll, so controls become unreachable

Rotate the phone to landscape on the login screen and the "Laptop address"
field is cut off at the bottom edge; "Sign in" and "Create account" are off
screen with no way to reach them. The same will happen in portrait on a short
phone once the keyboard opens, and at large system font sizes.

This breaks the project's own accessibility requirement, PRD OOTD-01 FR6:
*"At 360/412/600 dp widths and 200% text scale, primary actions remain
reachable with no clipped text."*

Fix the **login screen and the registration screen**: make their content
scroll vertically (`Modifier.verticalScroll(rememberScrollState())` on the
column) and keep the existing 24.dp padding. Note that a column which both
scrolls and uses `Arrangement.Center` will not centre as before — content
should sit naturally from the top once it is taller than the screen, while
still looking balanced on a tall phone. Do not change any field, button,
label or colour while doing this.

Check your work at three sizes: 360 dp wide, landscape, and 200% font scale.

## 2. Filter chips use Material3's default purple, not the app palette

On the closet, the selected category chip renders light purple. Every other
accent in the app is sage `#3B5B4C` on sand `#F7F6F2`, so the chip row is the
one element that looks like a different product.

Set the selected chip container to the sage already defined in
`MainActivity.kt` as `Sage`, with a label colour that stays legible against
it. Leave unselected chips as they are. Do not restyle anything else, and do
not introduce a full custom `MaterialTheme` colour scheme for this — the app
passes explicit colours everywhere else, so stay consistent with that.

## Done when

- `cd android_app && set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr" && gradlew.bat assembleDebug lint`
  gives BUILD SUCCESSFUL with no lint errors.
- **Do not create a `lint-baseline.xml`.**
- Nothing outside `android_app/app/` changed.

Run the build yourself and quote the real Gradle output. If it fails, fix it
and build again. Do not report a guess.
