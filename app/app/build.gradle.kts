plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "ph.edu.msuiit.activity"
    compileSdk = 37

    defaultConfig {
        applicationId = "ph.edu.msuiit.activity"
        minSdk = 26
        // Not 37 yet: targeting Android 17 may opt in to its local-network restrictions, and
        // this app's whole job is talking to an API on the local network. Revisit after testing.
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"

        // The deployed API (cloud/scripts/azure_create_vm.sh), used until the user sets
        // another address in Settings. Override with -Pactivity.apiUrl=http://... .
        val apiUrl = providers.gradleProperty("activity.apiUrl")
            .getOrElse("http://rtspark-activity-b2093c.eastasia.cloudapp.azure.com")
        buildConfigField("String", "DEFAULT_API_URL", "\"$apiUrl\"")
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.datastore.preferences)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.material3)
    implementation(libs.volley)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    // Android's org.json is only a stub in local unit tests; use the real implementation there.
    testImplementation(libs.org.json)
}
