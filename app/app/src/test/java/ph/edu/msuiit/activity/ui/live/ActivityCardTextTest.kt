package ph.edu.msuiit.activity.ui.live

import org.junit.Assert.assertEquals
import org.junit.Test
import ph.edu.msuiit.activity.data.Prediction

class ActivityCardTextTest {

    private val prediction = Prediction("idle", 0.97, 1_000_000)

    @Test
    fun livePrediction() {
        val state = LiveUiState(prediction = prediction, status = LiveStatus.Ok, now = 1_003_000)
        assertEquals("Idle" to "97% confident · updated 3 s ago", activityCardText(state))
    }

    @Test
    fun unreachableApiWithoutPredictionDoesNotBlameTheBoard() {
        val state = LiveUiState(status = LiveStatus.Error("Can't reach the server"))
        assertEquals("No connection", activityCardText(state).first)
    }

    @Test
    fun unreachableApiKeepsTheLastPrediction() {
        val state = LiveUiState(prediction = prediction, status = LiveStatus.Error("timeout"), now = 1_002_000)
        assertEquals("Idle", activityCardText(state).first)
    }

    @Test
    fun noPredictionsYet() {
        assertEquals("Waiting for data", activityCardText(LiveUiState(status = LiveStatus.NoData)).first)
    }

    @Test
    fun stalePrediction() {
        val state = LiveUiState(prediction = prediction, status = LiveStatus.Ok, now = 1_060_000)
        assertEquals("No new data" to "Last: Idle, 1 min ago. Is the board on?", activityCardText(state))
    }
}
