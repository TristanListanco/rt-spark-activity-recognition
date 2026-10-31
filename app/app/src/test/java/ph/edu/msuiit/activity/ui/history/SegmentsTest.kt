package ph.edu.msuiit.activity.ui.history

import org.junit.Assert.assertEquals
import org.junit.Test
import ph.edu.msuiit.activity.data.Prediction

class SegmentsTest {

    /** One prediction per second, newest first, like the API. */
    private fun seconds(vararg activities: Pair<String, Long>): List<Prediction> =
        activities.map { (activity, t) -> Prediction(activity, 0.9, t * 1000) }.sortedByDescending { it.ts }

    @Test
    fun emptyInput() = assertEquals(emptyList<Segment>(), toSegments(emptyList()))

    @Test
    fun mergesConsecutiveSameActivity() {
        val input = seconds("walk" to 1, "walk" to 2, "walk" to 3, "run" to 4, "run" to 5)
        val segments = toSegments(input)
        assertEquals(listOf("run", "walk"), segments.map { it.activity }) // newest first
        assertEquals(Segment("run", 4000, 5000, 2, 0.9), segments[0])
        assertEquals(Segment("walk", 1000, 3000, 3, 0.9), segments[1])
    }

    @Test
    fun gapStartsANewSegment() {
        val input = seconds("walk" to 1, "walk" to 2, "walk" to 60, "walk" to 61)
        val segments = toSegments(input, maxGapMs = 3_000)
        assertEquals(2, segments.size)
        assertEquals(60_000, segments[0].startTs)
        assertEquals(2_000, segments[1].endTs)
    }

    @Test
    fun meanConfidence() {
        val input = listOf(Prediction("run", 1.0, 2000), Prediction("run", 0.5, 1000))
        assertEquals(0.75, toSegments(input).single().meanConfidence, 1e-9)
    }

    @Test
    fun singlePredictionIsOneSecondSegment() {
        val s = toSegments(listOf(Prediction("walk", 0.8, 5000))).single()
        assertEquals(1, s.seconds)
        assertEquals(s.startTs, s.endTs)
    }
}
