package ph.edu.msuiit.activity.data

import com.android.volley.DefaultRetryPolicy
import com.android.volley.NoConnectionError
import com.android.volley.RequestQueue
import com.android.volley.TimeoutError
import com.android.volley.toolbox.StringRequest
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Volley (as the lab recommends) behind a suspend function. Volley runs the request
 * off the main thread and calls back on it; cancelling the coroutine cancels the request.
 */
class ApiClient(private val queue: RequestQueue) {

    suspend fun get(url: String): String = suspendCancellableCoroutine { continuation ->
        val request = StringRequest(
            url,
            { body -> continuation.resume(body) },
            { error ->
                val status = error.networkResponse?.statusCode
                val message = when {
                    status != null -> Json.errorMessage(error.networkResponse.data?.decodeToString())
                        ?: "Server error (HTTP $status)"
                    error is TimeoutError -> "The server did not answer in time"
                    error is NoConnectionError -> "Can't reach the server"
                    else -> error.message ?: "Network error"
                }
                continuation.resumeWithException(ApiException(message, status))
            },
        ).apply {
            retryPolicy = DefaultRetryPolicy(TIMEOUT_MS, 0, 1f) // the screens poll; no retries
            setShouldCache(false)
        }
        queue.add(request)
        continuation.invokeOnCancellation { request.cancel() }
    }

    private companion object {
        const val TIMEOUT_MS = 4_000
    }
}
