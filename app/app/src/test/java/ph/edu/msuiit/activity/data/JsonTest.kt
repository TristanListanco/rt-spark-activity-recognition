package ph.edu.msuiit.activity.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test

/** The examples are the response bodies from docs/CONTRACTS.md, section 4. */
class JsonTest {

    @Test
    fun latest() {
        val p = Json.latest("""{ "device_id": "rtspark-01", "activity": "walk", "confidence": 0.93, "ts": 1760000000000 }""")
        assertEquals(Prediction("walk", 0.93, 1_760_000_000_000), p)
    }

    @Test
    fun historyKeepsOrder() {
        val rows = Json.history(
            """[
              { "activity": "run",  "confidence": 0.88, "ts": 1760000005000 },
              { "activity": "walk", "confidence": 0.91, "ts": 1760000004000 }
            ]""",
        )
        assertEquals(listOf("run", "walk"), rows.map { it.activity })
        assertEquals(1_760_000_005_000, rows.first().ts)
    }

    @Test
    fun emptyHistory() = assertEquals(emptyList<Prediction>(), Json.history("[]"))

    @Test
    fun summary() {
        val s = Json.summary("""{ "date": "2026-10-30", "seconds": { "walk": 1240, "run": 315, "idle": 90 } }""")
        assertEquals(DailySummary("2026-10-30", 1240, 315, 90), s)
    }

    @Test
    fun summaryWithMissingActivityCountsZero() {
        val s = Json.summary("""{ "date": "2026-10-30", "seconds": { "walk": 12 } }""")
        assertEquals(0, s.runSeconds)
        assertEquals(0, s.idleSeconds)
    }

    @Test
    fun errorMessage() {
        assertEquals("no data", Json.errorMessage("""{ "error": "no data" }"""))
        assertNull(Json.errorMessage("<html>gateway timeout</html>"))
        assertNull(Json.errorMessage(null))
    }

    @Test
    fun malformedBodyBecomesApiException() {
        assertThrows(ApiException::class.java) { Json.latest("""{ "activity": "walk" }""") }
        assertThrows(ApiException::class.java) { Json.history("not json") }
    }
}
