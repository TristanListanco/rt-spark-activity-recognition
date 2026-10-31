package ph.edu.msuiit.activity.ui.live

import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ph.edu.msuiit.activity.data.DailySummary
import ph.edu.msuiit.activity.ui.activityName
import ph.edu.msuiit.activity.ui.formatAgo
import ph.edu.msuiit.activity.ui.formatDuration
import ph.edu.msuiit.activity.ui.theme.LocalActivityColors

@Composable
fun LiveScreen(viewModel: LiveViewModel, modifier: Modifier = Modifier) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    Column(
        modifier = modifier
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(
            text = state.settings?.deviceId ?: "",
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        (state.status as? LiveStatus.Error)?.let { ErrorBanner(it.message, state.settings?.baseUrl) }
        ActivityCard(state)
        SummaryCard(state.summary)
    }
}

@Composable
private fun ErrorBanner(message: String, baseUrl: String?) {
    Surface(
        color = MaterialTheme.colorScheme.errorContainer,
        contentColor = MaterialTheme.colorScheme.onErrorContainer,
        shape = RoundedCornerShape(12.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(Modifier.padding(12.dp)) {
            Text(message, style = MaterialTheme.typography.titleSmall)
            Text(
                "API: ${baseUrl ?: "?"}. Check the address in Settings and that you're on the same network.",
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}

/** The big coloured card: what the cloud says the wearer is doing right now. */
@Composable
private fun ActivityCard(state: LiveUiState) {
    val colors = LocalActivityColors.current
    val prediction = state.prediction
    val live = prediction != null && !state.isStale && state.status != LiveStatus.NoData

    val (title, subtitle) = when {
        state.status == LiveStatus.Loading -> "Connecting…" to "Asking the API for the latest prediction"
        prediction == null -> "Waiting for data" to "No predictions for this device yet. Is the board on?"
        state.isStale -> "No new data" to
            "Last: ${activityName(prediction.activity)}, ${formatAgo(state.now - prediction.ts)}. Is the board on?"
        else -> activityName(prediction.activity) to
            "${(prediction.confidence * 100).toInt()}% confident · updated ${formatAgo(state.now - prediction.ts)}"
    }
    val background by animateColorAsState(
        targetValue = if (live) colors.of(prediction.activity) else colors.idle, // live ⇒ prediction != null
        label = "activity colour",
    )

    Card(
        colors = CardDefaults.cardColors(containerColor = background, contentColor = Color.White),
        shape = RoundedCornerShape(24.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(Modifier.padding(horizontal = 24.dp, vertical = 32.dp)) {
            // Only the title is a live region: screen readers announce "Running" once when it
            // changes, not the "updated N s ago" text that changes every second.
            Text(
                title,
                style = MaterialTheme.typography.displaySmall,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
            )
            Spacer(Modifier.height(8.dp))
            Text(subtitle, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        }
    }
}

/** Today's walking vs running time as two labelled numbers and one proportional bar. */
@Composable
private fun SummaryCard(summary: DailySummary?) {
    val colors = LocalActivityColors.current
    Card(
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = RoundedCornerShape(16.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Today", style = MaterialTheme.typography.titleMedium)
            if (summary == null) {
                Text("—", color = MaterialTheme.colorScheme.onSurfaceVariant)
                return@Column
            }
            Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
                Total("Walking", summary.walkSeconds, colors.walk)
                Total("Running", summary.runSeconds, colors.run)
            }
            val total = summary.walkSeconds + summary.runSeconds
            if (total == 0) {
                Text(
                    "Nothing recorded today yet",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                Row(Modifier.fillMaxWidth().height(12.dp)) {
                    if (summary.walkSeconds > 0) {
                        Box(
                            Modifier
                                .weight(summary.walkSeconds.toFloat())
                                .height(12.dp)
                                .background(colors.walk, RoundedCornerShape(4.dp)),
                        )
                    }
                    if (summary.walkSeconds > 0 && summary.runSeconds > 0) Spacer(Modifier.width(2.dp))
                    if (summary.runSeconds > 0) {
                        Box(
                            Modifier
                                .weight(summary.runSeconds.toFloat())
                                .height(12.dp)
                                .background(colors.run, RoundedCornerShape(4.dp)),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun Total(label: String, seconds: Int, color: Color) {
    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(10.dp).background(color, CircleShape))
            Spacer(Modifier.width(6.dp))
            Text(label, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Text(formatDuration(seconds.toLong()), style = MaterialTheme.typography.headlineSmall)
    }
}
