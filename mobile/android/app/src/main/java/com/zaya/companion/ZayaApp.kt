package com.zaya.companion

import android.app.Application
import com.zaya.companion.runtime.ZayaRuntime
import com.zaya.companion.service.Notifications
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * The app object, and the one place the UI finds the live runtime.
 *
 * The runtime belongs to [com.zaya.companion.service.ZayaService], not to an
 * Activity: rotating the phone, leaving the app or losing the screen must never
 * drop the link to the laptop. Activities only look it up here.
 */
class ZayaApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Notifications.ensureChannels(this)
    }

    companion object {
        private val _runtime = MutableStateFlow<ZayaRuntime?>(null)

        /** Null until the service has built it, and again after it is destroyed. */
        val runtime: StateFlow<ZayaRuntime?> = _runtime.asStateFlow()

        internal fun attach(runtime: ZayaRuntime) {
            _runtime.value = runtime
        }

        internal fun detach(runtime: ZayaRuntime?) {
            if (_runtime.value === runtime) _runtime.value = null
        }
    }
}
