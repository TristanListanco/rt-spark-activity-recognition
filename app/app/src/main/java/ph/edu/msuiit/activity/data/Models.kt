package ph.edu.msuiit.activity.data

/** One classified second (docs/CONTRACTS.md, section 4). */
data class Prediction(
    val activity: String, // "walk" or "run"
    val confidence: Double, // 0..1
    val ts: Long, // Unix ms of the newest sample in the classified window
)

/** Seconds spent per activity on one calendar day. */
data class DailySummary(
    val date: String,
    val walkSeconds: Int,
    val runSeconds: Int,
)

/** Where the API lives and which board to show. */
data class AppSettings(
    val baseUrl: String,
    val deviceId: String,
)

/** A failed API call. [status] is the HTTP status, or null if the server couldn't be reached. */
class ApiException(message: String, val status: Int? = null) : Exception(message)
