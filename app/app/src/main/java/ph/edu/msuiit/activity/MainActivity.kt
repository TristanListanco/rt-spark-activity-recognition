package ph.edu.msuiit.activity

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.annotation.DrawableRes
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.lifecycle.ViewModelProvider.AndroidViewModelFactory.Companion.APPLICATION_KEY
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import ph.edu.msuiit.activity.ui.history.HistoryScreen
import ph.edu.msuiit.activity.ui.history.HistoryViewModel
import ph.edu.msuiit.activity.ui.live.LiveScreen
import ph.edu.msuiit.activity.ui.live.LiveViewModel
import ph.edu.msuiit.activity.ui.settings.SettingsScreen
import ph.edu.msuiit.activity.ui.settings.SettingsViewModel
import ph.edu.msuiit.activity.ui.theme.ActivityTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { ActivityTheme { AppScaffold() } }
    }
}

private enum class Tab(val label: String, @param:DrawableRes val icon: Int) {
    Live("Live", R.drawable.ic_tab_live),
    History("History", R.drawable.ic_tab_history),
    Settings("Settings", R.drawable.ic_tab_settings),
}

/** Creates the ViewModels from the app-wide repository and settings (no DI framework needed). */
private val factory = viewModelFactory {
    initializer {
        val app = this[APPLICATION_KEY] as ActivityApp
        LiveViewModel(app.repository, app.settings.settings)
    }
    initializer {
        val app = this[APPLICATION_KEY] as ActivityApp
        HistoryViewModel(app.repository, app.settings.settings)
    }
    initializer {
        val app = this[APPLICATION_KEY] as ActivityApp
        SettingsViewModel(app.repository, app.settings)
    }
}

@Composable
private fun AppScaffold() {
    var tab by rememberSaveable { mutableStateOf(Tab.Live) }
    Scaffold(
        bottomBar = {
            NavigationBar {
                Tab.entries.forEach {
                    NavigationBarItem(
                        selected = tab == it,
                        onClick = { tab = it },
                        icon = { Icon(painterResource(it.icon), contentDescription = null) },
                        label = { Text(it.label) },
                    )
                }
            }
        },
    ) { padding ->
        val modifier = Modifier.padding(padding)
        when (tab) {
            Tab.Live -> LiveScreen(viewModel(factory = factory), modifier)
            Tab.History -> HistoryScreen(viewModel(factory = factory), modifier)
            Tab.Settings -> SettingsScreen(viewModel(factory = factory), modifier)
        }
    }
}
