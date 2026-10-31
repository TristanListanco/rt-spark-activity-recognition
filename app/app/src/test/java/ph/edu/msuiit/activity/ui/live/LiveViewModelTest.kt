package ph.edu.msuiit.activity.ui.live

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import ph.edu.msuiit.activity.data.ActivitySource
import ph.edu.msuiit.activity.data.ApiException
import ph.edu.msuiit.activity.data.AppSettings
import ph.edu.msuiit.activity.data.DailySummary
import ph.edu.msuiit.activity.data.Prediction

/** Answers `latest` from a script, one entry per poll (the last entry repeats). */
private class FakeSource(vararg latest: () -> Prediction?) : ActivitySource {
    private val script = latest.toMutableList()
    var latestCalls = 0

    override suspend fun latest(settings: AppSettings): Prediction? {
        val answer = script[minOf(latestCalls, script.size - 1)]
        latestCalls++
        return answer()
    }

    override suspend fun history(settings: AppSettings, limit: Int, beforeMs: Long?) = emptyList<Prediction>()
    override suspend fun summary(settings: AppSettings) = DailySummary("2026-10-31", 60, 30)
    override suspend fun health(baseUrl: String) = Unit
}

@OptIn(ExperimentalCoroutinesApi::class)
class LiveViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    private val settings = flowOf(AppSettings("http://api", "rtspark-01"))
    private val running = Prediction("run", 0.97, 100_000)

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    @Test
    fun showsLatestPredictionAndSummary() = runTest(dispatcher) {
        val vm = LiveViewModel(FakeSource({ running }), settings, clock = { 101_000 })
        val state = vm.state.first { it.status != LiveStatus.Loading }
        assertEquals(LiveStatus.Ok, state.status)
        assertEquals(running, state.prediction)
        assertEquals(DailySummary("2026-10-31", 60, 30), state.summary)
        assertFalse(state.isStale)
    }

    @Test
    fun notFoundMeansNoDataYet() = runTest(dispatcher) {
        val vm = LiveViewModel(FakeSource({ null }), settings, clock = { 0 })
        assertEquals(LiveStatus.NoData, vm.state.first { it.status != LiveStatus.Loading }.status)
    }

    @Test
    fun errorKeepsTheLastPrediction() = runTest(dispatcher) {
        val source = FakeSource({ running }, { throw ApiException("Can't reach the server") })
        val vm = LiveViewModel(source, settings, clock = { 101_000 })
        val state = vm.state.first { it.status is LiveStatus.Error }
        assertEquals(LiveStatus.Error("Can't reach the server"), state.status)
        assertEquals(running, state.prediction)
        assertEquals(2, source.latestCalls) // polled again after the 1 s delay
    }

    @Test
    fun oldPredictionIsStale() = runTest(dispatcher) {
        val vm = LiveViewModel(
            FakeSource({ running }),
            settings,
            clock = { running.ts + LiveUiState.STALE_AFTER_MS + 1 },
        )
        assertTrue(vm.state.first { it.status == LiveStatus.Ok }.isStale)
    }
}
