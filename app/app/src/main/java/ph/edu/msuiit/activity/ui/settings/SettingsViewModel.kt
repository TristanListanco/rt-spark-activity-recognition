package ph.edu.msuiit.activity.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import ph.edu.msuiit.activity.data.ActivitySource
import ph.edu.msuiit.activity.data.ApiException
import ph.edu.msuiit.activity.data.AppSettings
import ph.edu.msuiit.activity.data.SettingsStore
import ph.edu.msuiit.activity.data.normalizeBaseUrl

data class SettingsUiState(
    val baseUrl: String = "",
    val deviceId: String = "",
    val loaded: Boolean = false,
    val urlError: String? = null,
    val deviceError: String? = null,
    val testing: Boolean = false,
    val message: String? = null,
    val messageIsError: Boolean = false,
)

class SettingsViewModel(
    private val repository: ActivitySource,
    private val store: SettingsStore,
) : ViewModel() {

    private val _state = MutableStateFlow(SettingsUiState())
    val state: StateFlow<SettingsUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            val saved = store.settings.first()
            _state.update { it.copy(baseUrl = saved.baseUrl, deviceId = saved.deviceId, loaded = true) }
        }
    }

    fun onBaseUrlChange(value: String) =
        _state.update { it.copy(baseUrl = value, urlError = null, message = null) }

    fun onDeviceIdChange(value: String) =
        _state.update { it.copy(deviceId = value, deviceError = null, message = null) }

    fun useDefaultAddress() = onBaseUrlChange(SettingsStore.defaultBaseUrl())

    fun save() {
        val url = validUrl() ?: return
        val deviceId = _state.value.deviceId.trim()
        if (deviceId.isEmpty()) {
            _state.update { it.copy(deviceError = "Enter the board's device ID, e.g. rtspark-01") }
            return
        }
        viewModelScope.launch {
            store.save(AppSettings(url, deviceId))
            _state.update {
                it.copy(baseUrl = url, deviceId = deviceId, message = "Saved", messageIsError = false)
            }
        }
    }

    /** Calls `/api/health` at the typed address (saved or not). */
    fun testConnection() {
        val url = validUrl() ?: return
        viewModelScope.launch {
            _state.update { it.copy(testing = true, message = null) }
            val (message, isError) = try {
                repository.health(url)
                "Connected: the API and its database are up" to false
            } catch (e: ApiException) {
                "Couldn't connect: ${e.message}" to true
            }
            _state.update { it.copy(testing = false, message = message, messageIsError = isError) }
        }
    }

    private fun validUrl(): String? {
        val url = normalizeBaseUrl(_state.value.baseUrl)
        if (url == null) {
            _state.update { it.copy(urlError = "Enter an address like http://192.168.1.44:8000") }
        }
        return url
    }
}
