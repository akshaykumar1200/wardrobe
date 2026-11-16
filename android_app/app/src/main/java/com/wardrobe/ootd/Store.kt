package com.wardrobe.ootd

import android.content.Context

/** The two things that have to survive the app being closed. */
class Store(context: Context) {

    private val prefs = context.getSharedPreferences("ootd", Context.MODE_PRIVATE)

    /** The laptop's address. Editable because DHCP reassigns it. */
    var baseUrl: String
        get() = prefs.getString(KEY_BASE, DEFAULT_BASE) ?: DEFAULT_BASE
        set(value) {
            val cleaned = value.trim().trimEnd('/')
            prefs.edit().putString(KEY_BASE, cleaned).apply()
        }

    /** Optional cloud fallback, empty until the user configures it. */
    var cloudUrl: String
        get() = prefs.getString(KEY_CLOUD, "") ?: ""
        set(value) {
            val cleaned = value.trim().trimEnd('/')
            prefs.edit().putString(KEY_CLOUD, cleaned).apply()
        }

    // shortcut: app-private SharedPreferences, not EncryptedSharedPreferences.
    // Unreadable by other apps on a non-rooted device, which is enough for a
    // session token; upgrade if this ever holds anything longer-lived.
    var token: String?
        get() = prefs.getString(KEY_TOKEN, null)
        set(value) {
            prefs.edit().apply {
                if (value == null) remove(KEY_TOKEN) else putString(KEY_TOKEN, value)
            }.apply()
        }

    companion object {
        const val DEFAULT_BASE = "http://192.168.29.222:8000"
        private const val KEY_BASE = "base_url"
        private const val KEY_CLOUD = "cloud_url"
        private const val KEY_TOKEN = "token"
    }
}
