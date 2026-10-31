package ph.edu.msuiit.activity.data

import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

/** Parsing of the API's JSON responses (docs/CONTRACTS.md, section 4). */
object Json {

    fun prediction(obj: JSONObject): Prediction = Prediction(
        activity = obj.getString("activity"),
        confidence = obj.getDouble("confidence"),
        ts = obj.getLong("ts"),
    )

    /** `GET /api/latest` */
    fun latest(body: String): Prediction = parse(body) { prediction(JSONObject(it)) }

    /** `GET /api/history`: newest first */
    fun history(body: String): List<Prediction> = parse(body) {
        val array = JSONArray(it)
        List(array.length()) { i -> prediction(array.getJSONObject(i)) }
    }

    /** `GET /api/summary` */
    fun summary(body: String): DailySummary = parse(body) {
        val obj = JSONObject(it)
        val seconds = obj.getJSONObject("seconds")
        DailySummary(
            date = obj.getString("date"),
            walkSeconds = seconds.optInt("walk", 0),
            runSeconds = seconds.optInt("run", 0),
        )
    }

    /** The `error` field of an error response, if the body is one. */
    fun errorMessage(body: String?): String? = try {
        body?.let { JSONObject(it).optString("error").ifEmpty { null } }
    } catch (e: JSONException) {
        null
    }

    private inline fun <T> parse(body: String, block: (String) -> T): T = try {
        block(body)
    } catch (e: JSONException) {
        throw ApiException("Unexpected response from the server: ${e.message}")
    }
}
