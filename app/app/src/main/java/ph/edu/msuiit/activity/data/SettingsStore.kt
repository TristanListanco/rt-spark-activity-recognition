package ph.edu.msuiit.activity.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import ph.edu.msuiit.activity.BuildConfig

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

        /** The deployed cloud API (set in app/build.gradle.kts), reachable from any network. */
        fun defaultBaseUrl(): String = BuildConfig.DEFAULT_API_URL
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
