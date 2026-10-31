package ph.edu.msuiit.activity.ui.history

import ph.edu.msuiit.activity.data.Prediction

/**
 * A stretch of consecutive seconds with the same activity, e.g. "Running 12:01:05–12:03:10".
 * The API returns one prediction per second, which is too fine-grained to list one by one.
 */
data class Segment(
    val activity: String,
    val startTs: Long,
    val endTs: Long,
    val seconds: Int, // number of predictions (one per second)
    val meanConfidence: Double,
)

/**
 * Merges predictions (newest first, as the API returns them) into segments, newest first.
 * A new segment starts when the activity changes or when more than [maxGapMs] passed
 * between two predictions (the board was off or offline).
 */
fun toSegments(predictions: List<Prediction>, maxGapMs: Long = 3_000): List<Segment> {
    val segments = mutableListOf<Segment>()
    var current: MutableList<Prediction>? = null

    fun close() {
        val group = current ?: return
        segments += Segment(
            activity = group.first().activity,
            startTs = group.last().ts, // oldest
            endTs = group.first().ts, // newest
            seconds = group.size,
            meanConfidence = group.sumOf { it.confidence } / group.size,
        )
        current = null
    }

    for (p in predictions) {
        val group = current
        if (group != null && (p.activity != group.last().activity || group.last().ts - p.ts > maxGapMs)) {
            close()
        }
        (current ?: mutableListOf<Prediction>().also { current = it }).add(p)
    }
    close()
    return segments
}
