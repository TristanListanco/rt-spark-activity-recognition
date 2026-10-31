package ph.edu.msuiit.activity

import android.app.Application
import com.android.volley.toolbox.Volley
import ph.edu.msuiit.activity.data.ActivityRepository
import ph.edu.msuiit.activity.data.ActivitySource
import ph.edu.msuiit.activity.data.ApiClient
import ph.edu.msuiit.activity.data.SettingsStore

/** Holds the app-wide objects (one Volley queue, the repository and the settings). */
class ActivityApp : Application() {
    lateinit var repository: ActivitySource
        private set
    lateinit var settings: SettingsStore
        private set

    override fun onCreate() {
        super.onCreate()
        repository = ActivityRepository(ApiClient(Volley.newRequestQueue(this)))
        settings = SettingsStore(this)
    }
}
