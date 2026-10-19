package com.zaya.companion.core

import com.zaya.companion.protocol.Protocol

/** Identity of this build on the wire. Kept tiny so tests and logs agree. */
object ZayaBuild {
    const val VERSION = "0.1.0"
    const val PROTOCOL = Protocol.VERSION
}
