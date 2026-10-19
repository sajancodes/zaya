package com.zaya.companion.audio

import java.nio.ByteBuffer

/** Copies a YUV_420_888 crop with independent row/pixel strides to NV21. */
object YuvPlanes {
    fun nv21(width: Int, height: Int, y: ByteBuffer, yRow: Int, yPixel: Int,
             u: ByteBuffer, uRow: Int, uPixel: Int,
             v: ByteBuffer, vRow: Int, vPixel: Int): ByteArray {
        require(width > 0 && height > 0 && width % 2 == 0 && height % 2 == 0)
        val result = ByteArray(width * height * 3 / 2)
        var output = 0
        val yStart = y.position(); val uStart = u.position(); val vStart = v.position()
        for (row in 0 until height) for (column in 0 until width) {
            result[output++] = y.get(yStart + row * yRow + column * yPixel)
        }
        for (row in 0 until height / 2) for (column in 0 until width / 2) {
            result[output++] = v.get(vStart + row * vRow + column * vPixel)
            result[output++] = u.get(uStart + row * uRow + column * uPixel)
        }
        return result
    }
}
