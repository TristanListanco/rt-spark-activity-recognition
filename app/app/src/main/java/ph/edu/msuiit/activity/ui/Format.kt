package ph.edu.msuiit.activity.ui

import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/** "Walking" / "Running" / "Idle", or the raw label for anything else. */
fun activityName(activity: String): String = when (activity) {
    "walk" -> "Walking"
    "run" -> "Running"
    "idle" -> "Idle"
    else -> activity.replaceFirstChar { it.uppercase() }
}

/** "just now", "12 s ago", "3 min ago", "2 h ago" */
fun formatAgo(ageMs: Long): String {
    val s = (ageMs / 1000).coerceAtLeast(0)
    return when {
        s < 2 -> "just now"
        s < 60 -> "$s s ago"
        s < 3600 -> "${s / 60} min ago"
        else -> "${s / 3600} h ago"
    }
}

/** "45 s", "2 min 5 s", "1 h 3 min" */
fun formatDuration(seconds: Long): String = when {
    seconds < 60 -> "$seconds s"
    seconds < 3600 -> if (seconds % 60 == 0L) "${seconds / 60} min" else "${seconds / 60} min ${seconds % 60} s"
    else -> "${seconds / 3600} h ${seconds % 3600 / 60} min"
}

private val clockFormat = DateTimeFormatter.ofPattern("HH:mm:ss")

/** Local wall-clock time of a Unix-ms timestamp, e.g. "13:45:07". */
fun formatClock(ts: Long, zone: ZoneId = ZoneId.systemDefault()): String =
    clockFormat.format(Instant.ofEpochMilli(ts).atZone(zone))
