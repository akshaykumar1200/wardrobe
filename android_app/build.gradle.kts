// Versions match the toolchain already proven on this machine (Android Studio
// 2026.1.2, Gradle 9.1.0 cached, bundled JDK 21).
plugins {
    id("com.android.application") version "8.13.0" apply false
    id("org.jetbrains.kotlin.android") version "2.2.20" apply false
    id("org.jetbrains.kotlin.plugin.compose") version "2.2.20" apply false
    id("org.jetbrains.kotlin.plugin.serialization") version "2.2.20" apply false
}
