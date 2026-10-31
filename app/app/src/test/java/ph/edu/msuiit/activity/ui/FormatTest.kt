package ph.edu.msuiit.activity.ui

import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.ZoneId

class FormatTest {

    @Test
    fun ago() {
        assertEquals("just now", formatAgo(900))
        assertEquals("just now", formatAgo(-500)) // phone clock slightly behind the board's
        assertEquals("12 s ago", formatAgo(12_400))
        assertEquals("3 min ago", formatAgo(185_000))
        assertEquals("2 h ago", formatAgo(7_300_000))
    }

    @Test
    fun duration() {
        assertEquals("45 s", formatDuration(45))
        assertEquals("2 min", formatDuration(120))
        assertEquals("2 min 5 s", formatDuration(125))
        assertEquals("1 h 3 min", formatDuration(3_790))
    }

    @Test
    fun clockInManila() {
        // 2026-10-31T04:53:20Z = 12:53:20 in Manila (UTC+8)
        assertEquals("12:53:20", formatClock(1_793_422_400_000, ZoneId.of("Asia/Manila")))
    }

    @Test
    fun names() {
        assertEquals("Walking", activityName("walk"))
        assertEquals("Running", activityName("run"))
        assertEquals("Idle", activityName("idle"))
    }
}
