package ph.edu.msuiit.activity.data

import androidx.core.net.toUri

/** What the screens need from the API; an interface so ViewModels can be tested with a fake. */
interface ActivitySource {
    /** The newest prediction, or null if the device has none yet (HTTP 404). */
    suspend fun latest(settings: AppSettings): Prediction?

    /** Up to [limit] predictions older than [beforeMs] (or the newest), newest first. */
    suspend fun history(settings: AppSettings, limit: Int, beforeMs: Long? = null): List<Prediction>

    /** Today's totals (in the server's time zone). */
    suspend fun summary(settings: AppSettings): DailySummary

    /** Throws [ApiException] unless the API and its database are up. */
    suspend fun health(baseUrl: String)
}

class ActivityRepository(private val api: ApiClient) : ActivitySource {

    override suspend fun latest(settings: AppSettings): Prediction? = try {
        Json.latest(api.get(url(settings, "latest")))
    } catch (e: ApiException) {
        if (e.status == 404) null else throw e
    }

    override suspend fun history(
        settings: AppSettings,
        limit: Int,
        beforeMs: Long?,
    ): List<Prediction> {
        val extra = buildMap {
            put("limit", limit.toString())
            beforeMs?.let { put("before", it.toString()) }
        }
        return Json.history(api.get(url(settings, "history", extra)))
    }

    override suspend fun summary(settings: AppSettings): DailySummary =
        Json.summary(api.get(url(settings, "summary")))

    override suspend fun health(baseUrl: String) {
        api.get("$baseUrl/api/health")
    }

    private fun url(settings: AppSettings, endpoint: String, extra: Map<String, String> = emptyMap()): String {
        val builder = "${settings.baseUrl}/api/$endpoint".toUri().buildUpon()
            .appendQueryParameter("device_id", settings.deviceId)
        extra.forEach { (key, value) -> builder.appendQueryParameter(key, value) }
        return builder.build().toString()
    }
}
