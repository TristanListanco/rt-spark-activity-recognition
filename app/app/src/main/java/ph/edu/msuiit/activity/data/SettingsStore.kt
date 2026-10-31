package ph.edu.msuiit.activity.data

import android.content.Context
import android.os.Build
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "settings")

/** API address and device ID, kept on the phone with DataStore. */
class SettingsStore(private val context: Context) {

    val settings: Flow<AppSettings> = context.dataStore.data.map { prefs ->
        AppSettings(
            baseUrl = prefs[BASE_URL] ?: defaultBaseUrl(),
            deviceId = prefs[DEVICE_ID] ?: DEFAULT_DEVICE_ID,
        )
    }

    suspend fun save(settings: AppSettings) {
        context.dataStore.edit { prefs ->
            prefs[BASE_URL] = settings.baseUrl
            prefs[DEVICE_ID] = settings.deviceId
        }
    }

    companion object {
        private val BASE_URL = stringPreferencesKey("base_url")
        private val DEVICE_ID = stringPreferencesKey("device_id")
        const val DEFAULT_DEVICE_ID = "rtspark-01"

        /**
         * The emulator reaches the computer running it at 10.0.2.2. A real phone joins the
         * iPhone hotspot, where the Mac running the API is 172.20.10.2 (firmware/README.md).
         */
        fun defaultBaseUrl(): String =
            if (isEmulator()) "http://10.0.2.2:8000" else "http://172.20.10.2:8000"

        private fun isEmulator(): Boolean =
            Build.FINGERPRINT.contains("generic") || Build.FINGERPRINT.contains("emulator") ||
                Build.HARDWARE.contains("ranchu") || Build.HARDWARE.contains("goldfish")
    }
}

/**
 * Cleans up a typed API address: adds `http://` if no scheme is given and drops trailing
 * slashes. Returns null if what's left isn't a usable http(s) address.
 */
fun normalizeBaseUrl(input: String): String? {
    var url = input.trim()
    if (url.isEmpty()) return null
    if (!url.contains("://")) url = "http://$url"
    url = url.trimEnd('/')
    val scheme = url.substringBefore("://").lowercase()
    val rest = url.substringAfter("://")
    if (scheme != "http" && scheme != "https") return null
    if (rest.isEmpty() || rest.any { it.isWhitespace() } || rest.contains('/')) return null
    return "$scheme://$rest"
}
