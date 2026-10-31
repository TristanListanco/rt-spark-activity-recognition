package ph.edu.msuiit.activity.ui.history

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ph.edu.msuiit.activity.ui.activityName
import ph.edu.msuiit.activity.ui.formatClock
import ph.edu.msuiit.activity.ui.formatDuration
import ph.edu.msuiit.activity.ui.theme.LocalActivityColors

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HistoryScreen(viewModel: HistoryViewModel, modifier: Modifier = Modifier) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val listState = rememberLazyListState()

    // Load the next page when the user scrolls near the end of what's loaded.
    val nearEnd by remember {
        derivedStateOf {
            val last = listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0
            last >= listState.layoutInfo.totalItemsCount - 3
        }
    }
    LaunchedEffect(nearEnd, state.segments.size) {
        if (nearEnd && state.segments.isNotEmpty()) viewModel.loadMore()
    }

    PullToRefreshBox(
        isRefreshing = state.refreshing,
        onRefresh = viewModel::refresh,
        modifier = modifier.fillMaxSize(),
    ) {
        LazyColumn(state = listState, contentPadding = PaddingValues(16.dp)) {
            item {
                Text("History", style = MaterialTheme.typography.headlineSmall)
                Text(
                    "${state.deviceId} · newest first · pull down to refresh",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(12.dp))
            }
            items(state.segments, key = { it.endTs }) { segment ->
                SegmentRow(segment)
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            }
            item { Footer(state, onRetry = viewModel::loadMore, onRefresh = viewModel::refresh) }
        }
    }
}

@Composable
private fun SegmentRow(segment: Segment) {
    val color = LocalActivityColors.current.of(segment.activity)
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.width(6.dp).height(40.dp).background(color, RoundedCornerShape(3.dp)))
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(activityName(segment.activity), style = MaterialTheme.typography.titleMedium)
            val range = if (segment.seconds == 1) {
                formatClock(segment.endTs)
            } else {
                "${formatClock(segment.startTs)} – ${formatClock(segment.endTs)}"
            }
            Text(
                "$range · ${formatDuration(segment.seconds.toLong())}",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Text(
            "${(segment.meanConfidence * 100).toInt()}%",
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun Footer(state: HistoryUiState, onRetry: () -> Unit, onRefresh: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxWidth().padding(vertical = 16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        when {
            state.error != null -> {
                Text(state.error, color = MaterialTheme.colorScheme.error)
                TextButton(onClick = if (state.segments.isEmpty()) onRefresh else onRetry) { Text("Try again") }
            }
            state.loading && !state.refreshing -> CircularProgressIndicator()
            state.segments.isEmpty() -> Text(
                "No activity recorded for this device yet.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            state.endReached -> Text(
                "That's everything.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
