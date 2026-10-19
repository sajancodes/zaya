package com.zaya.companion.core

import com.zaya.companion.protocol.Protocol

/** Identity of this build on the wire. Kept tiny so tests and logs agree. */
object ZayaBuild {
    val VERSION = com.zaya.companion.BuildConfig.VERSION_NAME
    const val PROTOCOL = Protocol.VERSION
}
