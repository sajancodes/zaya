package com.zaya.companion.runtime

import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Environment
import com.zaya.companion.audio.MicCapture
import com.zaya.companion.audio.CallAudioRoute
import com.zaya.companion.audio.PhoneCamera
import android.view.Surface
import android.util.Base64
import com.zaya.companion.audio.SpeakerOutput
import com.zaya.companion.core.Backoff
import com.zaya.companion.core.ZayaBuild
import com.zaya.companion.data.PairingStore
import com.zaya.companion.net.AuthResult
import com.zaya.companion.net.ContentUriBody
import com.zaya.companion.net.SocketEvents
import com.zaya.companion.net.ZayaApi
import com.zaya.companion.net.ZayaSocket
import com.zaya.companion.protocol.CallUiState
import com.zaya.companion.protocol.ConnectionPhase
import com.zaya.companion.protocol.ConnectionStatus
import com.zaya.companion.protocol.Envelope
import com.zaya.companion.protocol.Pairing
import com.zaya.companion.protocol.Protocol
import com.zaya.companion.protocol.RemoteFile
import com.zaya.companion.protocol.TaskItem
import com.zaya.companion.protocol.WhatsappFeed
import com.zaya.companion.protocol.WhatsappRow
import com.zaya.companion.protocol.array
import com.zaya.companion.protocol.child
import com.zaya.companion.protocol.flag
import com.zaya.companion.protocol.num
import com.zaya.companion.protocol.str
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.onStart
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * The live link between this phone and the Zaya runtime on the laptop.
 *
 * It owns four things and nothing else: how we sign in, the control socket, the
 * voice socket, and the microphone/speaker pair. Everything the owner sees is
 * produced by [ZayaModel] out of laptop events; this class only decides *when*
 * to connect, and it is built so that one failing stream can never take the
 * others down with it.
 */
class ZayaRuntime(
    private val context: Context,
    private val scope: CoroutineScope,
    val model: ZayaModel = ZayaModel(),
    private val store: PairingStore = PairingStore(context),
) {
    private val _connection = MutableStateFlow(ConnectionStatus())
    val connection: StateFlow<ConnectionStatus> = _connection.asStateFlow()

    private val _pairing = MutableStateFlow<Pairing?>(null)
    val pairing: StateFlow<Pairing?> = _pairing.asStateFlow()

    private val effectChannel = Channel<RuntimeEffect>(Channel.BUFFERED)
    val effects: Flow<RuntimeEffect> = effectChannel.receiveAsFlow()

    private val reconnectSignal = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    private val outbox = ArrayDeque<Pair<String, String>>()

    private val restClient = okhttp3.OkHttpClient.Builder()
        .connectTimeout(CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .readTimeout(READ_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .writeTimeout(READ_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    private val socketClient = okhttp3.OkHttpClient.Builder()
        .connectTimeout(CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        // A WebSocket is idle between events; liveness is checked by the
        // application-level ping below, not by a read timeout.
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .pingInterval(SOCKET_PING_SECONDS, TimeUnit.SECONDS)
        .retryOnConnectionFailure(false)
        .build()

    @Volatile
    private var control: ZayaSocket? = null

    @Volatile
    private var voice: ZayaSocket? = null

    @Volatile
    private var lastMessageAt: Long = 0L

    @Volatile
    private var speaker: SpeakerOutput? = null

    @Volatile
    private var micCapture: MicCapture? = null

    /** HTTP client bound to the signed-in session; null while signed out. */
    @Volatile
    private var api: ZayaApi? = null

    /** Set while the owner holds their own microphone open in a call. */
    @Volatile
    private var muted: Boolean = false

    /** Real uplink/downlink rates the laptop reported; defaults match the protocol. */
    @Volatile
    private var uplinkRate: Int = Protocol.UPLINK_RATE

    @Volatile
    private var downlinkRate: Int = Protocol.DOWNLINK_RATE

    private var supervisor: Job? = null
    val updates = com.zaya.companion.updates.AppUpdates(context)
    private var updateChecks: Job? = null
    private val callAudio = CallAudioRoute(context)
    val hardwareController by lazy { com.zaya.companion.service.HardwareController(context) }
    val cellularCallManager by lazy { com.zaya.companion.service.CellularCallManager(context) }
    val mediaPlaybackController by lazy { com.zaya.companion.service.MediaPlaybackController(context) }
    val appLauncher by lazy { com.zaya.companion.service.AppLauncher(context) }
    val screenCaptureManager by lazy { com.zaya.companion.service.ScreenCaptureManager(context) }
    val actionExecutor by lazy {
        com.zaya.companion.action.ActionExecutor(
            context = context,
            hardwareController = hardwareController,
            mediaController = mediaPlaybackController,
            appLauncher = appLauncher,
            callManager = cellularCallManager,
            screenCaptureManager = screenCaptureManager,
        )
    }
    val actionRegistry by lazy { actionExecutor.registry }
    private val _speakerphone = MutableStateFlow(false)
    val speakerphone: StateFlow<Boolean> = _speakerphone.asStateFlow()
    private val _videoEnabled = MutableStateFlow(false)
    val videoEnabled: StateFlow<Boolean> = _videoEnabled.asStateFlow()
    private val _videoSharing = MutableStateFlow(false)
    val videoSharing: StateFlow<Boolean> = _videoSharing.asStateFlow()
    private val _videoGeometry = MutableStateFlow<PhoneCamera.Geometry?>(null)
    val videoGeometry: StateFlow<PhoneCamera.Geometry?> = _videoGeometry.asStateFlow()
    private var phoneCamera: PhoneCamera? = null
    private var previewSurface: Surface? = null
    private var videoCallId = ""
    private var videoGeneration = 0L

    /** UI and camera callbacks share this lock; stale callbacks cannot affect a new call. */
    @Synchronized
    fun setVideoEnabled(enabled: Boolean) {
        if (!enabled) {
            videoGeneration++
            _videoEnabled.value = false
            phoneCamera?.stop()
            phoneCamera = null
            previewSurface = null
            _videoSharing.value = false
            _videoGeometry.value = null
            if (videoCallId.isNotEmpty()) control?.send(JSONObject()
                .put("type", "call.video.toggle").put("call_id", videoCallId).put("enabled", false).toString())
            videoCallId = ""
            return
        }
        val call = (model.call.value as? CallUiState.Active)?.call ?: return
        if (_videoEnabled.value) return
        if (context.checkSelfPermission(android.Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            model.setVoice(note = "Allow the camera to turn video on")
            return
        }
        val sent = control?.send(JSONObject().put("type", "call.video.toggle")
            .put("call_id", call.callId).put("enabled", true).toString()) == true
        if (!sent) { model.setVoice(note = "No link to Zaya for video"); return }
        val generation = ++videoGeneration
        videoCallId = call.callId
        model.setVoice(note = "")
        phoneCamera = PhoneCamera(context,
            onFrame = { jpeg -> synchronized(this) {
                val activeId = (model.call.value as? CallUiState.Active)?.call?.callId
                if (_videoEnabled.value && videoGeneration == generation && activeId == call.callId && videoCallId == call.callId) {
                    val delivered = control?.send(JSONObject().put("type", "call.video.frame").put("call_id", call.callId)
                        .put("jpeg", Base64.encodeToString(jpeg, Base64.NO_WRAP)).toString()) == true
                    _videoSharing.value = delivered
                    if (!delivered) {
                        setVideoEnabled(false)
                        model.setVoice(note = "Video link unavailable")
                    }
                }
            } },
            onGeometry = { geometry -> synchronized(this) {
                if (videoGeneration == generation && videoCallId == call.callId) _videoGeometry.value = geometry
            } },
            onError = { message -> synchronized(this) {
                if (videoGeneration == generation) {
                    setVideoEnabled(false)
                    model.setVoice(note = message)
                }
            } },
        )
        // Camera capture starts only once the visible preview Surface is ready.
        _videoEnabled.value = true
    }

    @Synchronized
    fun attachVideoPreview(surface: Surface, configureBuffer: (Int, Int) -> Unit) {
        val activeId = (model.call.value as? CallUiState.Active)?.call?.callId
        if (!_videoEnabled.value || activeId != videoCallId || !surface.isValid) return
        if (previewSurface === surface) return
        if (previewSurface != null) { setVideoEnabled(false); return }
        previewSurface = surface
        phoneCamera?.start(surface, configureBuffer)
    }

    @Synchronized
    fun detachVideoPreview(surface: Surface) {
        if (previewSurface === surface) setVideoEnabled(false)
    }

    fun setSpeakerphone(enabled: Boolean) {
        if (model.call.value !is CallUiState.Active) return
        runCatching { callAudio.setSpeaker(enabled) }
            .onSuccess { _speakerphone.value = it }
            .onFailure { model.setVoice(note = "Could not change the phone speaker") }
    }

    // ── lifecycle ────────────────────────────────────────────────────────────

    fun start() {
        if (supervisor != null) return
        supervisor = scope.launch {
            combine(store.pairing, reconnectSignal.onStart { emit(Unit) }) { pair, _ -> pair }
                .collectLatest { pair -> runConnection(pair) }
        }
        updateChecks = scope.launch {
            while (isActive) {
                updates.check()
                delay(6 * 60 * 60 * 1000L)
            }
        }
    }

    fun stop() {
        supervisor?.cancel()
        supervisor = null
        updateChecks?.cancel()
        updateChecks = null
        teardownSession()
        model.connectionLost("Disconnected")
        _connection.value = ConnectionStatus(ConnectionPhase.UNPAIRED, "Disconnected")
    }

    /** The owner asked for an immediate retry (from the notification or the UI). */
    fun reconnectNow() {
        reconnectSignal.tryEmit(Unit)
    }

    // ── pairing ──────────────────────────────────────────────────────────────

    /** First-time pairing with a key from the laptop's Remote Control panel. */
    suspend fun pair(address: String, key: String, deviceName: String): AuthResult {
        val base = Pairing.normalizeAddress(address)
        if (base.isEmpty()) {
            return AuthResult.Denied("Enter the laptop address first")
        }
        val api = ZayaApi(base, restClient)
        val result = api.pair(base, key, deviceName, ZayaBuild.VERSION)
        if (result is AuthResult.Ok) {
            store.save(
                Pairing(
                    address = base,
                    deviceId = result.deviceId,
                    secret = result.deviceSecret,
                    serverName = result.serverName,
                    deviceName = deviceName,
                ),
            )
            adoptAudio(result.uplinkRate, result.downlinkRate)
        }
        return result
    }

    /** Forget this laptop: tell it to revoke us, then drop the credential. */
    suspend fun forgetDevice(): Boolean {
        val current = _pairing.value
        var revoked = false
        if (current != null) {
            revoked = runCatching { ZayaApi(current.baseUrl, restClient).also {
                it.token = api?.token
            }.revokeSelf(current.deviceId) }.getOrDefault(false)
        }
        store.clear()
        teardownSession()
        model.connectionLost("Device unpaired")
        return revoked
    }

    fun addressOf(): String = _pairing.value?.address.orEmpty()

    // ── connection loop ──────────────────────────────────────────────────────

    private suspend fun runConnection(pair: Pairing?) {
        _pairing.value = pair
        if (pair == null) {
            // A revoked device lands here after its credential is dropped; keep
            // the explanation instead of flattening it into "not paired".
            if (_connection.value.phase != ConnectionPhase.REVOKED) {
                _connection.value =
                    ConnectionStatus(ConnectionPhase.UNPAIRED, "Not paired with a laptop")
            }
            return
        }
        val backoff = Backoff()
        var unauthorizedStreak = 0
        while (scope.isActive) {
            val base = pair.baseUrl
            status(ConnectionPhase.CONNECTING, "Signing in…", attempts = backoff.attempts)
            val api = ZayaApi(base, restClient)
            when (val auth = api.login(pair, ZayaBuild.VERSION)) {
                is AuthResult.Ok -> {
                    if (auth.protocolVersion != Protocol.VERSION) {
                        _connection.value = ConnectionStatus(
                            ConnectionPhase.INCOMPATIBLE,
                            "That laptop speaks protocol ${auth.protocolVersion}; this app speaks ${Protocol.VERSION}",
                        )
                        delay(INCOMPATIBLE_RETRY_MILLIS)
                        continue
                    }
                    api.token = auth.token
                    this.api = api
                    adoptAudio(auth.uplinkRate, auth.downlinkRate)
                    val outcome = session(base, api, auth.token, backoff)
                    if (backoff.attempts == 0) unauthorizedStreak = 0
                    when (outcome) {
                        SessionOutcome.Unauthorized -> {
                            // The socket refused the token even though the sign-in
                            // worked. Retry a couple of times, then treat the
                            // credential as dead instead of looping forever.
                            unauthorizedStreak += 1
                            if (unauthorizedStreak >= MAX_UNAUTHORIZED_STREAK) {
                                store.clear()
                                _connection.value = ConnectionStatus(
                                    ConnectionPhase.REVOKED,
                                    "The laptop no longer accepts this phone. Pair it again.",
                                )
                                teardownSession()
                                return
                            }
                            status(ConnectionPhase.CONNECTING, "Signing in again…")
                            delay(RETRY_AFTER_UNAUTHORIZED_MILLIS)
                            continue
                        }

                        is SessionOutcome.Failed -> {
                            status(
                                ConnectionPhase.OFFLINE,
                                outcome.message,
                                attempts = backoff.attempts,
                            )
                        }

                        SessionOutcome.Closed -> {
                            status(
                                ConnectionPhase.OFFLINE,
                                "The laptop closed the link",
                                attempts = backoff.attempts,
                            )
                        }
                    }
                }

                is AuthResult.Denied -> {
                    if (auth.retryAfterSeconds > 0) {
                        status(
                            ConnectionPhase.OFFLINE,
                            auth.message,
                            attempts = backoff.attempts,
                        )
                        countdown(auth.retryAfterSeconds)
                        continue
                    }
                    // A revoked or unknown device: keeping the credential would
                    // only produce a refusal loop, so hand it back to the owner.
                    store.clear()
                    _connection.value = ConnectionStatus(
                        ConnectionPhase.REVOKED,
                        auth.message.ifBlank { "This phone is no longer paired" },
                    )
                    teardownSession()
                    return
                }

                is AuthResult.Unavailable -> {
                    status(ConnectionPhase.OFFLINE, auth.message, attempts = backoff.attempts)
                }
            }
            val wait = backoff.nextDelayMillis()
            _connection.value = _connection.value.copy(
                phase = ConnectionPhase.OFFLINE,
                retryInSeconds = (wait / 1000).toInt(),
            )
            delay(wait)
        }
    }

    /**
     * One control-socket generation: open, greet, pump until it dies.
     *
     * The voice socket is a separate connection with its own failure mode: if it
     * breaks, this one keeps carrying chat, tasks and microphone frames.
     */
    private suspend fun session(
        base: String,
        api: ZayaApi,
        token: String,
        backoff: Backoff,
    ): SessionOutcome {
        val finished = kotlinx.coroutines.CompletableDeferred<SessionOutcome>()
        var openedAt = 0L
        lastMessageAt = System.currentTimeMillis()
        val socket = ZayaSocket(
            socketClient,
            "${Pairing.wsBase(base)}/ws/mobile?token=$token",
            object : SocketEvents {
                override fun onOpen(socket: ZayaSocket) {
                    openedAt = System.currentTimeMillis()
                    lastMessageAt = openedAt
                    _connection.value = ConnectionStatus(ConnectionPhase.ONLINE, "Connected")
                    sendHello(socket)
                    sendCapabilitiesReport(socket)
                    openVoiceSocket(base, token)
                    scope.launch { updates.check() }
                    flushOutbox(socket)
                }

                override fun onText(socket: ZayaSocket, text: String) {
                    lastMessageAt = System.currentTimeMillis()
                    val envelope = Envelope.parse(text) ?: return
                    if (envelope.type == Protocol.Type.PONG) return
                    val effects = model.apply(envelope)
                    if (envelope.type in setOf(Protocol.Type.HELLO, Protocol.Type.CALL_ANSWERED, Protocol.Type.CALL_MUTE)) {
                        muted = model.voice.value.muted
                        if (envelope.type == Protocol.Type.CALL_MUTE) applyMicState()
                    }
                    if (envelope.type == Protocol.Type.CALL_VIDEO && !envelope.payload.flag("video_enabled") &&
                        envelope.payload.str("call_id", 64) == videoCallId && _videoEnabled.value) setVideoEnabled(false)

                    when (envelope.type) {
                        Protocol.Type.HARDWARE_ACTION -> handleHardwareAction(envelope.payload)
                        Protocol.Type.CALL_CONTROL -> handleCallControl(envelope.payload)
                        Protocol.Type.CALL_ANNOUNCE -> {
                            val caller = envelope.payload.str("caller", 100)
                            cellularCallManager.announceCaller(caller)
                        }
                        Protocol.Type.AUTO_REPLY -> {
                            val key = envelope.payload.str("key", 200)
                            val text = envelope.payload.str("text", 1000)
                            com.zaya.companion.service.ZayaNotificationListener.sendAutoReply(key, text)
                        }
                        Protocol.Type.DOUBLE_CLAP_CONFIG -> {
                            val enabled = envelope.payload.flag("enabled", true)
                            micCapture?.clapDetector?.enabled = enabled
                        }
                        Protocol.Type.MEDIA_CONTROL -> handleMediaControl(envelope.payload)
                        Protocol.Type.OPEN_DEEP_LINK -> handleDeepLink(envelope.payload)
                        Protocol.Type.LAUNCH_APP -> handleLaunchApp(envelope.payload)
                        Protocol.Type.ACTION_INVOKE -> handleActionInvoke(envelope.payload)
                    }

                    dispatch(effects)
                }

                override fun onClosed(socket: ZayaSocket, code: Int, reason: String) {
                    finished.complete(
                        if (code == SocketEvents.CLOSE_UNAUTHORIZED) SessionOutcome.Unauthorized
                        else SessionOutcome.Closed,
                    )
                }

                override fun onFailure(socket: ZayaSocket, error: Throwable) {
                    finished.complete(SessionOutcome.Failed(ZayaApi.friendlyNetworkMessage(error)))
                }
            },
        )
        control = socket
        socket.open()

        val watchdog = scope.launch {
            while (isActive) {
                delay(HEARTBEAT_SECONDS * 1000)
                val current = control ?: return@launch
                if (!current.isOpen) continue
                val silent = System.currentTimeMillis() - lastMessageAt
                if (silent > STALE_AFTER_MILLIS) {
                    // The laptop is not answering. Reconnect from scratch rather
                    // than sitting on a socket that looks open and is not.
                    current.close(1001, "heartbeat timeout")
                    finished.complete(SessionOutcome.Failed("Zaya stopped answering"))
                    return@launch
                }
                current.send(JSONObject().put("type", Protocol.Control.PING).toString())
            }
        }

        val outcome = try {
            finished.await()
        } finally {
            watchdog.cancel()
        }
        val lived = System.currentTimeMillis() - openedAt
        if (lived >= HEALTHY_SESSION_MILLIS && outcome !is SessionOutcome.Unauthorized) {
            backoff.reset()
        }
        teardownSession()
        model.connectionLost(outcome.reasonForOwner())
        return outcome
    }

    private fun sendHello(socket: ZayaSocket) {
        val hello = JSONObject()
            .put("type", Protocol.Control.HELLO)
            .put("app_version", ZayaBuild.VERSION)
            .put("audio_output", true)
        socket.send(hello.toString())
    }

    private fun openVoiceSocket(base: String, token: String) {
        voice?.close(1000, "replaced")
        val socket = ZayaSocket(
            socketClient,
            "${Pairing.wsBase(base)}/ws/phone-output?token=$token",
            object : SocketEvents {
                override fun onBytes(socket: ZayaSocket, data: ByteArray) {
                    if (data.isEmpty()) return
                    if (data.size > Protocol.MAX_FRAME_BYTES) return
                    if (model.call.value is CallUiState.Dialing || model.call.value is CallUiState.Ringing) return
                    speakerFor().enqueue(data)
                }

                override fun onText(socket: ZayaSocket, text: String) {
                    // audio.start / audio.ping: liveness only, nothing to show.
                }

                override fun onFailure(socket: ZayaSocket, error: Throwable) {
                    // Voice is best-effort: the control socket stays up and the
                    // owner sees a mic/speaker note instead of a dead screen.
                    model.setVoice(speakerActive = false, note = "Voice link is down")
                }

                override fun onClosed(socket: ZayaSocket, code: Int, reason: String) {
                    model.setVoice(speakerActive = false)
                }
            },
        )
        voice = socket
        socket.open()
    }

    val taskCoordinator: com.zaya.companion.action.TaskCoordinator get() = actionExecutor.taskCoordinator
    val memoryStore: com.zaya.companion.memory.PersonalMemoryStore get() = actionExecutor.memoryStore

    // ── commands ─────────────────────────────────────────────────────────────

    /** True when the command reached the laptop (or was parked for the reconnect). */
    suspend fun send(text: String): Boolean {
        val clean = text.trim()
        val lower = clean.lowercase()

        // 1. Task Cancellation Gate
        if (taskCoordinator.activeTask.value?.isRunning == true) {
            if (lower in setOf("cancel", "stop", "abort", "cancel task", "stop task", "never mind")) {
                val active = taskCoordinator.activeTask.value
                if (active != null) {
                    taskCoordinator.cancelTask(active.taskId, "Cancelled by user request")
                    model.notice("Task stopped by user.")
                    return true
                }
            }
        }

        // 2. Direct Local Personal Memory Commands
        if (lower.startsWith("remember ") || lower.startsWith("forget ") || lower.contains("what do you remember")) {
            val memoryNotice = handleLocalMemoryCommand(clean)
            if (memoryNotice != null) {
                model.beginCommand(clean)
                model.notice(memoryNotice)
                return true
            }
        }

        val started = model.beginCommand(clean)
        if (started == null) return false
        val (requestId, _) = started
        val socket = control
        if (socket == null || !socket.isOpen) {
            park(requestId, clean)
            return false
        }
        val message = JSONObject()
            .put("type", Protocol.Control.COMMAND)
            .put("text", clean)
            .put("request_id", requestId)
        val sent = socket.send(message.toString())
        if (!sent) park(requestId, clean)
        return sent
    }

    private fun handleLocalMemoryCommand(text: String): String? {
        val lower = text.lowercase().trim()
        if (lower.startsWith("remember ")) {
            val raw = text.substring(9).trim()
            val parts = when {
                raw.contains(" is ") -> raw.split(" is ", limit = 2)
                raw.contains(" = ") -> raw.split(" = ", limit = 2)
                raw.contains(":") -> raw.split(":", limit = 2)
                else -> listOf(raw, "true")
            }
            val key = parts[0].removePrefix("that ").trim()
            val value = if (parts.size > 1) parts[1].trim() else "true"
            return when (val res = memoryStore.saveMemory(key, value, confirmed = true)) {
                is com.zaya.companion.memory.MemorySaveResult.Saved -> res.message
                is com.zaya.companion.memory.MemorySaveResult.SensitiveDataBlocked -> "For your privacy, I cannot store sensitive information such as passwords or payment details."
                is com.zaya.companion.memory.MemorySaveResult.RequiresConfirmation -> res.prompt
                is com.zaya.companion.memory.MemorySaveResult.Invalid -> res.reason
            }
        } else if (lower.startsWith("forget ")) {
            val key = text.substring(7).trim()
            val removed = memoryStore.forgetMemory(key)
            return if (removed) "I have forgotten '$key' and removed it from your saved preferences."
            else "I couldn't find any saved preference matching '$key'."
        } else if (lower.contains("what do you remember")) {
            val query = lower.substringAfter("about", "").trim()
            val list = if (query.isNotBlank()) memoryStore.getRelevantMemories(query) else memoryStore.memories.value
            return if (list.isEmpty()) {
                if (query.isNotBlank()) "I don't have anything remembered about '$query'."
                else "You have no saved personal preferences yet."
            } else {
                val lines = list.take(5).map { "• ${it.key}: ${it.value} (${it.category.displayName})" }
                "Saved preferences:\n" + lines.joinToString("\n")
            }
        }
        return null
    }

    private fun park(requestId: String, text: String) {
        model.markCommandQueued(requestId)
        synchronized(outbox) {
            if (outbox.none { it.first == requestId }) {
                if (outbox.size >= MAX_OUTBOX) outbox.removeFirst()
                outbox.addLast(requestId to text)
            }
        }
    }

    private fun flushOutbox(socket: ZayaSocket) {
        val pending = synchronized(outbox) {
            val copy = outbox.toList()
            outbox.clear()
            copy
        }
        val retries = model.tracker.inFlight().filter { entry ->
            pending.none { it.first == entry.first }
        }
        for ((requestId, text) in pending + retries.take(MAX_RESEND)) {
            val message = JSONObject()
                .put("type", Protocol.Control.COMMAND)
                .put("text", text)
                .put("request_id", requestId)
            if (!socket.send(message.toString())) {
                park(requestId, text)
            }
        }
    }

    // ── calls ────────────────────────────────────────────────────────────────

    fun answer(callId: String) = sendCallControl(Protocol.Control.CALL_ANSWER, callId)

    fun decline(callId: String) = sendCallControl(Protocol.Control.CALL_DECLINE, callId)

    fun endCall() {
        val active = model.call.value
        val callId = when (active) {
            is CallUiState.Active -> active.call.callId
            is CallUiState.Ringing -> active.call.callId
            is CallUiState.Dialing -> active.call.callId
            CallUiState.Idle -> ""
        }
        sendCallControl(Protocol.Control.CALL_END, callId)
    }

    /** The owner pressed call: ask Zaya to talk now. */
    fun startCall() {
        val message = JSONObject().put("type", Protocol.Control.CALL_START)
        if (control?.send(message.toString()) != true) {
            model.notice("No link to Zaya right now")
        }
    }

    fun setMuted(value: Boolean) {
        if (model.call.value !is CallUiState.Active) return
        muted = value
        model.setVoice(muted = value)
        val message = JSONObject()
            .put("type", Protocol.Control.CALL_MUTE)
            .put("muted", value)
        control?.send(message.toString())
        applyMicState()
    }

    /** What the speaker is playing right now, 0f…1f, for the call meter. */
    fun outputLevel(): Float = speaker?.level ?: 0f

    /** Fire-and-forget output switch, for UI callbacks. */
    fun changeOutputInBackground(target: String) {
        scope.launch { setOutputTarget(target) }
    }

    private fun sendCallControl(type: String, callId: String) {
        val message = JSONObject()
            .put("type", type)
            .put("call_id", callId)
        control?.send(message.toString())
    }

    // ── audio ────────────────────────────────────────────────────────────────

    private fun speakerFor(): SpeakerOutput {
        speaker?.let { return it }
        val created = SpeakerOutput(
            communication = model.call.value is CallUiState.Active,
            sampleRate = downlinkRate,
            onError = { message -> model.setVoice(speakerActive = false, note = message) },
        )
        speaker = created
        created.start()
        return created
    }

    /** Rebuilt whenever the laptop reports a different rate after a reconnect. */
    private fun adoptAudio(uplink: Int, downlink: Int) {
        val changed = uplink != uplinkRate || downlink != downlinkRate
        uplinkRate = uplink
        downlinkRate = downlink
        if (changed) {
            stopVoice()
        }
    }

    private fun applyMicState() {
        val wanted = model.call.value is CallUiState.Active && !muted
        if (!wanted) {
            micCapture?.stop()
            micCapture = null
            model.setVoice(micActive = false)
            return
        }
        if (micCapture?.isRunning == true) return
        if (!hasAudioPermission()) {
            model.setVoice(
                micActive = false,
                note = "Microphone permission is off, so Zaya cannot hear you",
            )
            return
        }
        val created = MicCapture(
            sampleRate = uplinkRate,
            onFrame = { frame -> sendMicFrame(frame) },
            onError = { message -> model.setVoice(micActive = false, note = message) },
            onDoubleClap = {
                val msg = JSONObject()
                    .put("type", Protocol.Control.DOUBLE_CLAP_DETECTED)
                    .put("payload", JSONObject())
                    .put("timestamp", System.currentTimeMillis() / 1000.0)
                control?.send(msg.toString())
            },
        )
        micCapture = created
        if (created.start()) {
            model.setVoice(micActive = true, note = "")
        } else {
            micCapture = null
        }
    }

    /**
     * Microphone frames only travel during a call, and only while the owner has
     * not muted. Anything else would push room noise into Zaya's own session.
     */
    private fun sendMicFrame(frame: ByteArray) {
        if (muted) return
        if (model.call.value !is CallUiState.Active) return
        if (frame.size > Protocol.MAX_FRAME_BYTES) return
        control?.send(frame)
    }

    private fun stopVoice() {
        setVideoEnabled(false)
        micCapture?.stop()
        micCapture = null
        speaker?.stop()
        speaker = null
        callAudio.end()
        _speakerphone.value = false
        muted = false
        model.setVoice(micActive = false, speakerActive = false, muted = muted)
    }

    private fun hasAudioPermission(): Boolean =
        context.checkPermission(
            android.Manifest.permission.RECORD_AUDIO,
            android.os.Process.myPid(),
            android.os.Process.myUid(),
        ) == PackageManager.PERMISSION_GRANTED

    private fun dispatch(effects: List<RuntimeEffect>) {
        for (effect in effects) {
            when (effect) {
                is RuntimeEffect.StartVoice -> {
                    speaker?.stop()
                    speaker = null
                    runCatching { callAudio.stopRinging(); callAudio.begin() }
                        .onFailure { model.setVoice(note = "Phone audio route unavailable") }
                    applyMicState()
                }
                is RuntimeEffect.StopVoice -> stopVoice()
                is RuntimeEffect.Ringback -> {
                    stopVoice()
                    runCatching { callAudio.ringback() }
                        .onFailure { model.setVoice(note = "Ringing tone unavailable") }
                }
                is RuntimeEffect.Ring -> {
                    model.setVoice(micActive = false, speakerActive = false)
                    effectChannel.trySend(effect)
                }

                else -> effectChannel.trySend(effect)
            }
        }
    }

    // ── laptop data ──────────────────────────────────────────────────────────

    suspend fun refreshTasks(): List<TaskItem> {
        val client = api ?: return emptyList()
        return runCatching { client.tasks() }.getOrElse { emptyList() }.also { rows ->
            if (rows.isNotEmpty()) model.mergeTasks(rows)
        }
    }

    suspend fun syncNow() {
        val client = api ?: return
        runCatching { client.snapshot() }.getOrNull()?.let { model.applySnapshot(it) }
        refreshTasks()
    }

    suspend fun setOutputTarget(target: String): String? {
        if (target !in Protocol.Output.TARGETS) return null
        val client = api ?: return null
        val applied = runCatching { client.setOutput(target) }.getOrNull() ?: return null
        model.setOutputTarget(applied)
        val message = JSONObject()
            .put("type", Protocol.Control.OUTPUT)
            .put("target", applied)
        control?.send(message.toString())
        return applied
    }

    suspend fun whatsapp(
        action: String,
        chat: String = "",
        query: String = "",
        limit: Int = 15,
    ): WhatsappFeed {
        val client = api
            ?: return model.whatsapp.value.copy(error = "Not connected to the laptop")
        return try {
            val json = client.whatsapp(action, chat, query, limit)
                ?: return model.whatsapp.value.copy(error = "No answer from the laptop")
            val result = json.child("result")
            val rows = ArrayList<WhatsappRow>()
            result?.child("data")?.let { data ->
                for (key in data.keys()) {
                    val entry = data.optJSONObject(key)
                    val row = if (entry != null) {
                        WhatsappRow(
                            chatId = key,
                            title = entry.str("title", Protocol.MAX_TITLE).ifBlank { entry.str("name", Protocol.MAX_TITLE) },
                            summary = entry.str("summary", Protocol.MAX_DETAIL)
                                .ifBlank { entry.str("text", Protocol.MAX_DETAIL) },
                            score = entry.optInt("score", 0),
                            category = entry.str("category", 40),
                        )
                    } else {
                        WhatsappRow(
                            chatId = key,
                            title = key,
                            summary = data.optString(key, "").take(Protocol.MAX_DETAIL),
                        )
                    }
                    rows += row
                }
            }
            val evidence = ArrayList<String>()
            result?.array("evidence")?.let { array ->
                for (index in 0 until array.length()) {
                    val text = array.optString(index, "")
                    if (text.isNotBlank()) evidence += text.take(Protocol.MAX_DETAIL)
                }
            }
            val feed = model.whatsapp.value.copy(
                action = action,
                status = result?.str("status", 40).orEmpty(),
                summary = result?.str("summary", Protocol.MAX_DETAIL).orEmpty(),
                rows = rows.ifEmpty { model.whatsapp.value.rows },
                evidence = evidence,
                error = if (json.flag("ok")) "" else json.str("error", Protocol.MAX_DETAIL),
            )
            model.setWhatsapp(feed)
            feed
        } catch (error: Exception) {
            model.setWhatsapp(model.whatsapp.value.copy(error = ZayaApi.friendlyNetworkMessage(error)))
            model.whatsapp.value
        }
    }

    suspend fun setWhatsappMode(chatId: String, mode: String): Boolean {
        val client = api ?: return false
        return try {
            client.setWhatsappMode(chatId, mode)?.let { result ->
                val scope = result.str("scope", 40)
                val applied = result.str("mode", 40)
                val current = model.whatsapp.value
                model.setWhatsapp(
                    current.copy(
                        globalMode = if (scope == "chat") current.globalMode else applied,
                        chatId = result.str("chat_id", Protocol.MAX_REFERENCE),
                        chatMode = if (scope == "chat") applied else current.chatMode,
                        error = "",
                    ),
                )
                if (scope != "chat") {
                    val message = JSONObject()
                        .put("type", Protocol.Control.WHATSAPP_MODE)
                        .put("chat_id", "")
                        .put("mode", applied)
                    control?.send(message.toString())
                }
                true
            } ?: false
        } catch (error: Exception) {
            model.setWhatsapp(
                model.whatsapp.value.copy(error = ZayaApi.friendlyNetworkMessage(error)),
            )
            false
        }
    }

    suspend fun listFiles(): List<RemoteFile> {
        val client = api ?: return emptyList()
        return runCatching { client.files() }.getOrElse { emptyList() }
    }

    /** Files land in a folder this app owns; the owner can hand them to other apps. */
    fun downloadsFolder(): File {
        val root = context.getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS) ?: context.filesDir
        return File(root, "Zaya").apply { mkdirs() }
    }

    suspend fun download(name: String): File {
        val client = api ?: throw IllegalStateException("Not connected to the laptop")
        val safe = File(name).name
        if (safe.isBlank()) throw IllegalArgumentException("Bad file name")
        val destination = File(downloadsFolder(), safe)
        client.download(safe, destination)
        return destination
    }

    suspend fun upload(uri: Uri, displayName: String): Boolean {
        val client = api ?: return false
        val resolver = context.contentResolver
        val name = File(displayName).name.ifBlank { "upload" }
        val body = ContentUriBody(resolver, uri, name)
        val json = client.upload(name, body)
        return json?.optBoolean("ok") == true
    }

    // ── helpers ──────────────────────────────────────────────────────────────

    private fun teardownSession() {
        control?.close(1000, "closed")
        control = null
        voice?.close(1000, "closed")
        voice = null
        stopVoice()
        effectChannel.trySend(RuntimeEffect.StopRinging)
    }

    private fun status(phase: ConnectionPhase, detail: String, attempts: Int = 0) {
        _connection.value = ConnectionStatus(phase, detail, 0, attempts)
    }

    private suspend fun countdown(seconds: Int) {
        var left = seconds.coerceAtLeast(0)
        while (left > 0 && scope.isActive) {
            _connection.value = _connection.value.copy(retryInSeconds = left)
            delay(1000)
            left -= 1
        }
    }

    private sealed interface SessionOutcome {
        data object Closed : SessionOutcome
        data object Unauthorized : SessionOutcome
        data class Failed(val message: String) : SessionOutcome

        fun reasonForOwner(): String = when (this) {
            Closed -> "The link to the laptop closed"
            Unauthorized -> "The laptop asked the phone to sign in again"
            is Failed -> message
        }
    }

    fun sendNotificationEvent(payload: JSONObject) {
        val msg = JSONObject()
            .put("type", Protocol.Control.NOTIFICATION_EVENT)
            .put("payload", payload)
            .put("timestamp", System.currentTimeMillis() / 1000.0)
        control?.send(msg.toString())
    }

    private fun handleHardwareAction(payload: JSONObject) {
        val action = payload.str("action", 40)
        when (action) {
            "torch_on" -> hardwareController.setFlashlight(true)
            "torch_off" -> hardwareController.setFlashlight(false)
            "wifi" -> hardwareController.openWifiSettings()
            "bluetooth" -> hardwareController.openBluetoothSettings()
            "hotspot" -> hardwareController.openHotspotSettings()
            "location" -> hardwareController.openLocationSettings()
            "battery", "status" -> {
                val status = hardwareController.getBatteryStatus()
                val report = JSONObject()
                    .put("type", Protocol.Control.HARDWARE_STATUS)
                    .put("payload", JSONObject(status))
                    .put("timestamp", System.currentTimeMillis() / 1000.0)
                control?.send(report.toString())
            }
            "volume" -> {
                val vol = payload.num("percent", 50)
                hardwareController.setMediaVolume(vol)
            }
        }
    }

    private fun handleCallControl(payload: JSONObject) {
        val action = payload.str("action", 40)
        when (action) {
            "answer" -> cellularCallManager.answerCall()
            "reject" -> cellularCallManager.rejectCall()
            "announce" -> {
                val caller = payload.str("caller", 100)
                cellularCallManager.announceCaller(caller)
            }
        }
    }

    private fun handleMediaControl(payload: JSONObject) {
        val action = payload.str("action", 40)
        val success = mediaPlaybackController.executeAction(action)
        val report = JSONObject()
            .put("type", Protocol.Control.ACTION_RESULT)
            .put("payload", JSONObject().put("action", action).put("success", success).put("module", "media"))
            .put("timestamp", System.currentTimeMillis() / 1000.0)
        control?.send(report.toString())
    }

    private fun handleDeepLink(payload: JSONObject) {
        val app = payload.str("target_app", 60)
        val query = payload.str("query", 200)
        val success = appLauncher.openDeepLink(app, query)
        val report = JSONObject()
            .put("type", Protocol.Control.ACTION_RESULT)
            .put("payload", JSONObject().put("target_app", app).put("success", success).put("module", "deep_link"))
            .put("timestamp", System.currentTimeMillis() / 1000.0)
        control?.send(report.toString())
    }

    private fun handleLaunchApp(payload: JSONObject) {
        val name = payload.str("name", 80)
        val success = appLauncher.launchAppByName(name)
        val report = JSONObject()
            .put("type", Protocol.Control.ACTION_RESULT)
            .put("payload", JSONObject().put("name", name).put("success", success).put("module", "app_launcher"))
            .put("timestamp", System.currentTimeMillis() / 1000.0)
        control?.send(report.toString())
    }

    fun sendCapabilitiesReport(socket: ZayaSocket? = control) {
        val caps = actionRegistry.discoverCapabilities()
        val arr = org.json.JSONArray()
        caps.forEach { arr.put(it.toJsonObject()) }
        val msg = JSONObject()
            .put("type", Protocol.Control.CAPABILITIES_REPORT)
            .put("payload", JSONObject().put("capabilities", arr))
            .put("timestamp", System.currentTimeMillis() / 1000.0)
        socket?.send(msg.toString())
    }

    private fun handleActionInvoke(payload: JSONObject) {
        val actionId = payload.str("action_id", 60)
        val args = payload.optJSONObject("arguments") ?: JSONObject()
        val action: com.zaya.companion.action.AndroidAction = when (actionId) {
            "set_flashlight" -> com.zaya.companion.action.AndroidAction.SetFlashlight(args.optBoolean("enabled", true))
            "get_flashlight_state" -> com.zaya.companion.action.AndroidAction.GetFlashlightState
            "open_settings" -> com.zaya.companion.action.AndroidAction.OpenSystemSettings(
                setting = args.optString("setting", "settings"),
                packageName = args.optString("package_name", "").ifBlank { null }
            )
            "control_media" -> com.zaya.companion.action.AndroidAction.ControlMedia(args.optString("action", "toggle"))
            "get_media_status" -> com.zaya.companion.action.AndroidAction.GetMediaStatus
            "launch_app" -> com.zaya.companion.action.AndroidAction.LaunchApp(args.optString("name", ""))
            "lookup_contact" -> com.zaya.companion.action.AndroidAction.LookUpContact(args.optString("query", ""))
            "initiate_call" -> com.zaya.companion.action.AndroidAction.InitiateCall(
                queryOrNumber = args.optString("query", args.optString("phone_number", "")),
                directCall = args.optBoolean("direct_call", false),
                confirmed = args.optBoolean("confirmed", false)
            )
            "get_incoming_call_state" -> com.zaya.companion.action.AndroidAction.GetIncomingCallState
            "set_caller_announcement" -> com.zaya.companion.action.AndroidAction.SetCallerAnnouncement(
                enabled = args.optBoolean("enabled", true)
            )
            "compose_sms" -> com.zaya.companion.action.AndroidAction.ComposeSms(
                recipient = args.optString("recipient", ""),
                message = args.optString("message", ""),
                confirmed = args.optBoolean("confirmed", false),
                directSend = args.optBoolean("direct_send", false)
            )
            "answer_call" -> com.zaya.companion.action.AndroidAction.AnswerCall
            "reject_call" -> com.zaya.companion.action.AndroidAction.RejectCall
            "read_notifications" -> com.zaya.companion.action.AndroidAction.ReadNotifications(
                packageFilter = args.optString("package_filter", "").ifBlank { null },
                limit = args.optInt("limit", 5)
            )
            "read_latest_notification" -> com.zaya.companion.action.AndroidAction.ReadLatestNotification(
                packageFilter = args.optString("package_filter", "").ifBlank { null }
            )
            "summarize_notifications" -> com.zaya.companion.action.AndroidAction.SummarizeNotifications(
                packageFilter = args.optString("package_filter", "").ifBlank { null }
            )
            "draft_notification_reply" -> com.zaya.companion.action.AndroidAction.DraftNotificationReply(
                targetKey = args.optString("notification_key", "").ifBlank { null },
                targetSender = args.optString("sender", "").ifBlank { null },
                targetPackage = args.optString("package", "").ifBlank { null },
                contextInstruction = args.optString("instruction", "").ifBlank { null }
            )
            "reply_notification" -> com.zaya.companion.action.AndroidAction.ReplyToNotification(
                notificationKey = args.optString("notification_key", "").ifBlank { null },
                targetSender = args.optString("sender", "").ifBlank { null },
                targetPackage = args.optString("package", "").ifBlank { null },
                text = args.optString("text", ""),
                confirmed = args.optBoolean("confirmed", false)
            )
            "capture_screen" -> com.zaya.companion.action.AndroidAction.CaptureScreen
            "describe_screen" -> com.zaya.companion.action.AndroidAction.DescribeScreen(
                prompt = args.optString("prompt", "").ifBlank { null }
            )
            "extract_visible_text" -> com.zaya.companion.action.AndroidAction.ExtractVisibleText(
                filter = args.optString("filter", "").ifBlank { null }
            )
            "summarize_screen" -> com.zaya.companion.action.AndroidAction.SummarizeScreen(
                focus = args.optString("focus", "").ifBlank { null }
            )
            "scroll_screen" -> com.zaya.companion.action.AndroidAction.ScrollScreen(args.optString("direction", "down"))
            "tap_screen" -> com.zaya.companion.action.AndroidAction.TapScreen(
                x = args.optDouble("x", 0.0).toFloat(),
                y = args.optDouble("y", 0.0).toFloat()
            )
            "run_task" -> com.zaya.companion.action.AndroidAction.RunTask(args.optString("task_id", ""))
            "cancel_task" -> com.zaya.companion.action.AndroidAction.CancelTask(args.optString("task_id", ""))
            "plan_and_execute_task" -> com.zaya.companion.action.AndroidAction.PlanAndExecuteTask(
                prompt = args.optString("prompt", ""),
                taskId = args.optString("task_id", "")
            )
            "remember_memory" -> com.zaya.companion.action.AndroidAction.RememberMemory(
                key = args.optString("key", ""),
                value = args.optString("value", ""),
                category = args.optString("category", "PREFERENCE"),
                confirmed = args.optBoolean("confirmed", false)
            )
            "forget_memory" -> com.zaya.companion.action.AndroidAction.ForgetMemory(
                key = args.optString("key", ""),
                category = args.optString("category", "").ifBlank { null }
            )
            "query_memory" -> com.zaya.companion.action.AndroidAction.QueryMemory(
                query = args.optString("query", "")
            )
            else -> {
                val errResult = com.zaya.companion.action.ActionResult.unsupported("Action '$actionId' is not supported.")
                val report = JSONObject()
                    .put("type", Protocol.Control.ACTION_RESULT)
                    .put("payload", errResult.toJsonObject())
                    .put("timestamp", System.currentTimeMillis() / 1000.0)
                control?.send(report.toString())
                return
            }
        }

        scope.launch {
            val result = actionExecutor.execute(action)
            val report = JSONObject()
                .put("type", Protocol.Control.ACTION_RESULT)
                .put("payload", result.toJsonObject())
                .put("timestamp", System.currentTimeMillis() / 1000.0)
            control?.send(report.toString())
        }
    }

    private companion object {
        const val CONNECT_TIMEOUT_SECONDS = 10L
        const val READ_TIMEOUT_SECONDS = 20L
        const val SOCKET_PING_SECONDS = 20L
        const val HEARTBEAT_SECONDS = 15L
        const val STALE_AFTER_MILLIS = 45_000L
        const val HEALTHY_SESSION_MILLIS = 20_000L
        const val RETRY_AFTER_UNAUTHORIZED_MILLIS = 2_000L
        const val INCOMPATIBLE_RETRY_MILLIS = 30_000L
        const val MAX_UNAUTHORIZED_STREAK = 3
        const val MAX_OUTBOX = 20
        const val MAX_RESEND = 10
    }
}
