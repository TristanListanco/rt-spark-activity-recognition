package ph.edu.msuiit.activity.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

/*
 * The project's palette, shared with the charts (docs/ml), the web page and the board's
 * LCD: blue = walking, orange = running, green = idle, neutral surfaces and inks. Grey
 * means no live prediction (connecting, no data, stale). Dark mode uses the
 * palette's own dark steps rather than inverted colours.
 */

private val LightScheme = lightColorScheme(
    primary = Color(0xFF2A78D6),
    onPrimary = Color.White,
    background = Color(0xFFF9F9F7),
    onBackground = Color(0xFF0B0B0B),
    surface = Color(0xFFFCFCFB),
    onSurface = Color(0xFF0B0B0B),
    surfaceVariant = Color(0xFFF0EFEC),
    onSurfaceVariant = Color(0xFF52514E),
    surfaceContainer = Color(0xFFF3F2EF),
    outline = Color(0xFF898781),
    outlineVariant = Color(0xFFE1E0D9),
)

private val DarkScheme = darkColorScheme(
    primary = Color(0xFF3987E5),
    onPrimary = Color.White,
    background = Color(0xFF0D0D0D),
    onBackground = Color(0xFFF0EFEC),
    surface = Color(0xFF1A1A19),
    onSurface = Color(0xFFF0EFEC),
    surfaceVariant = Color(0xFF242423),
    onSurfaceVariant = Color(0xFFC3C2B7),
    surfaceContainer = Color(0xFF1F1F1E),
    outline = Color(0xFF898781),
    outlineVariant = Color(0xFF2C2C2A),
)

/** Colours that identify an activity everywhere in the app; [inactive] when there is none. */
data class ActivityColors(val walk: Color, val run: Color, val idle: Color, val inactive: Color) {
    fun of(activity: String): Color = when (activity) {
        "walk" -> walk
        "run" -> run
        "idle" -> idle
        else -> inactive
    }
}

private val LightActivity =
    ActivityColors(Color(0xFF2A78D6), Color(0xFFEB6834), Color(0xFF0E7D58), Color(0xFF6E6D69))
private val DarkActivity =
    ActivityColors(Color(0xFF3987E5), Color(0xFFD95926), Color(0xFF199E70), Color(0xFF4A4A4A))

val LocalActivityColors = staticCompositionLocalOf { LightActivity }

@Composable
fun ActivityTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    MaterialTheme(colorScheme = if (dark) DarkScheme else LightScheme) {
        CompositionLocalProvider(
            LocalActivityColors provides if (dark) DarkActivity else LightActivity,
            content = content,
        )
    }
}
