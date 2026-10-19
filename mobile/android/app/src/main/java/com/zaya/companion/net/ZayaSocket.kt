package com.zaya.companion.net

import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import okio.ByteString.Companion.toByteString

/** Everything a socket can tell us. All callbacks arrive on OkHttp's reader thread. */
interface SocketEvents {
    fun onOpen(socket: ZayaSocket) {}
    fun onText(socket: ZayaSocket, text: String) {}
    fun onBytes(socket: ZayaSocket, data: ByteArray) {}
    fun onClosed(socket: ZayaSocket, code: Int, reason: String) {}
    fun onFailure(socket: ZayaSocket, error: Throwable) {}

    /** The laptop's own token check said no: `4001` (see dashboard/server.py). */
    companion object {
        const val CLOSE_UNAUTHORIZED = 4001
    }
}

/**
 * One WebSocket, one job.
 *
 * The control socket carries JSON both ways plus the phone's microphone PCM; the
 * voice socket carries only Zaya's PCM down to this phone's speaker. They are
 * separate on purpose: a stuck audio stream must never take the control channel
 * with it, and either one can be reconnected without disturbing the other.
 */
class ZayaSocket(
    private val client: OkHttpClient,
    private val url: String,
    private val events: SocketEvents,
) {
    private var socket: WebSocket? = null

    @Volatile
    var isOpen: Boolean = false
        private set

    fun open() {
        val request = Request.Builder().url(url).build()
        socket = client.newWebSocket(request, Listener())
    }

    fun send(text: String): Boolean {
        val ws = socket ?: return false
        return ws.send(text)
    }

    fun send(bytes: ByteArray): Boolean {
        val ws = socket ?: return false
        if (bytes.isEmpty() || bytes.size > MAX_FRAME_BYTES) return false
        return ws.send(bytes.toByteString())
    }

    /** Idempotent: used by the runtime from any thread. */
    fun close(code: Int = 1000, reason: String = "closed") {
        val ws = socket
        socket = null
        isOpen = false
        ws?.close(code, reason)
    }

    private inner class Listener : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            isOpen = true
            events.onOpen(this@ZayaSocket)
        }

        override fun onMessage(webSocket: WebSocket, text: String) {
            events.onText(this@ZayaSocket, text)
        }

        override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
            events.onBytes(this@ZayaSocket, bytes.toByteArray())
        }

        override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
            isOpen = false
            webSocket.close(code, null)
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            isOpen = false
            events.onClosed(this@ZayaSocket, code, reason)
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            isOpen = false
            // A close code can also arrive as a failure with a response.
            val code = response?.code ?: 0
            if (code == SocketEvents.CLOSE_UNAUTHORIZED) {
                events.onClosed(this@ZayaSocket, SocketEvents.CLOSE_UNAUTHORIZED, "unauthorized")
            } else {
                events.onFailure(this@ZayaSocket, t)
            }
        }
    }

    private companion object {
        const val MAX_FRAME_BYTES = 32_768
    }
}
