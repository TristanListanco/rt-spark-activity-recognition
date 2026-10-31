package ph.edu.msuiit.activity.ui.history

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import ph.edu.msuiit.activity.data.ActivitySource
import ph.edu.msuiit.activity.data.ApiException
import ph.edu.msuiit.activity.data.AppSettings
import ph.edu.msuiit.activity.data.Prediction

data class HistoryUiState(
    val deviceId: String = "",
    val segments: List<Segment> = emptyList(),
    val loading: Boolean = false, // any request in flight
    val refreshing: Boolean = false, // pull-to-refresh in progress
    val endReached: Boolean = false,
    val error: String? = null,
)

/**
 * Pages through `/api/history` (newest first) and merges the per-second predictions into
 * [Segment]s. [loadMore] continues from the oldest row loaded so far using `before=`.
 */
class HistoryViewModel(
    private val repository: ActivitySource,
    settings: Flow<AppSettings>,
) : ViewModel() {

    private val _state = MutableStateFlow(HistoryUiState())
    val state: StateFlow<HistoryUiState> = _state.asStateFlow()

    private val rows = mutableListOf<Prediction>()
    private var current: AppSettings? = null
    private var job: Job? = null

    init {
        viewModelScope.launch {
            settings.collect { // first value, and again whenever the user saves new settings
                current = it
                refresh()
            }
        }
    }

    fun refresh() = load(reset = true)

    fun loadMore() {
        val s = _state.value
        if (s.endReached || s.loading || s.error != null) return
        load(reset = false)
    }

    private fun load(reset: Boolean) {
        val settings = current ?: return
        if (reset) job?.cancel()
        job = viewModelScope.launch {
            _state.update {
                it.copy(
                    deviceId = settings.deviceId,
                    loading = true,
                    refreshing = reset && rows.isNotEmpty(),
                    error = null,
                )
            }
            try {
                val before = if (reset) null else rows.lastOrNull()?.ts
                val page = repository.history(settings, PAGE_SIZE, before)
                if (reset) rows.clear()
                rows += page
                _state.update {
                    it.copy(
                        segments = toSegments(rows),
                        loading = false,
                        refreshing = false,
                        endReached = page.size < PAGE_SIZE,
                    )
                }
            } catch (e: ApiException) {
                _state.update { it.copy(loading = false, refreshing = false, error = e.message) }
            }
        }
    }

    companion object {
        const val PAGE_SIZE = 500 // the API's maximum
    }
}
