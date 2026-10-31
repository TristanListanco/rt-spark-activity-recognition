package ph.edu.msuiit.activity.ui.live

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.stateIn
import ph.edu.msuiit.activity.data.ActivitySource
import ph.edu.msuiit.activity.data.ApiException
import ph.edu.msuiit.activity.data.AppSettings
import ph.edu.msuiit.activity.data.DailySummary
import ph.edu.msuiit.activity.data.Prediction

sealed interface LiveStatus {
    data object Loading : LiveStatus
    data object Ok : LiveStatus
    data object NoData : LiveStatus // the API is up but has nothing for this device yet
    data class Error(val message: String) : LiveStatus
}

data class LiveUiState(
    val settings: AppSettings? = null,
    val prediction: Prediction? = null, // kept during errors so the last value stays visible
    val summary: DailySummary? = null,
    val status: LiveStatus = LiveStatus.Loading,
    val now: Long = 0, // when this state was produced, for "updated N s ago"
) {
    /** True when the newest prediction is too old to call "live" (board off or offline). */
    val isStale: Boolean
        get() = prediction != null && now - prediction.ts > STALE_AFTER_MS

    companion object {
        const val STALE_AFTER_MS = 10_000L
    }
}

/**
 * Polls `/api/latest` every second (and today's summary every 10 s) while the Live screen
 * is visible: the flow only runs while collected, and stops 5 s after the app goes to the
 * background. A settings change restarts polling with the new address and device.
 */
class LiveViewModel(
    private val repository: ActivitySource,
    settings: Flow<AppSettings>,
    private val clock: () -> Long = System::currentTimeMillis,
    private val pollMs: Long = 1_000,
) : ViewModel() {

    @OptIn(ExperimentalCoroutinesApi::class)
    val state: StateFlow<LiveUiState> = settings
        .flatMapLatest { poll(it) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), LiveUiState())

    private fun poll(settings: AppSettings): Flow<LiveUiState> = flow {
        var state = LiveUiState(settings = settings, now = clock())
        emit(state)
        var tick = 0
        while (true) {
            state = try {
                val prediction = repository.latest(settings)
                val summary = if (tick % SUMMARY_EVERY == 0 || state.summary == null) {
                    fetchSummary(settings) ?: state.summary
                } else {
                    state.summary
                }
                state.copy(
                    prediction = prediction,
                    summary = summary,
                    status = if (prediction == null) LiveStatus.NoData else LiveStatus.Ok,
                    now = clock(),
                )
            } catch (e: ApiException) {
                state.copy(status = LiveStatus.Error(e.message ?: "Request failed"), now = clock())
            }
            emit(state)
            tick++
            delay(pollMs)
        }
    }

    private suspend fun fetchSummary(settings: AppSettings): DailySummary? = try {
        repository.summary(settings)
    } catch (e: ApiException) {
        null // the summary is secondary; keep the last one rather than failing the screen
    }

    private companion object {
        const val SUMMARY_EVERY = 10
    }
}
