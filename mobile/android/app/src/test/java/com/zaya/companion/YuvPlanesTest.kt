package com.zaya.companion

import com.zaya.companion.audio.YuvPlanes
import java.nio.ByteBuffer
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Test

class YuvPlanesTest {
    @Test fun `padded interleaved planes preserve VU order and buffer positions`() {
        val y = ByteBuffer.wrap(byteArrayOf(99, 1, 2, 3, 4, 88, 88, 5, 6, 7, 8, 88, 88)).apply { position(1) }
        val u = ByteBuffer.wrap(byteArrayOf(99, 10, 88, 11)).apply { position(1) }
        val v = ByteBuffer.wrap(byteArrayOf(99, 20, 88, 21)).apply { position(1) }
        assertArrayEquals(byteArrayOf(1,2,3,4,5,6,7,8,20,10,21,11),
            YuvPlanes.nv21(4, 2, y, 6, 1, u, 4, 2, v, 4, 2))
        assertEquals(1, y.position()); assertEquals(1, u.position()); assertEquals(1, v.position())
    }

    @Test fun `independent chroma row strides work across rows`() {
        val y = ByteBuffer.wrap(ByteArray(16) { it.toByte() })
        val u = ByteBuffer.wrap(byteArrayOf(20,21,99,22,23))
        val v = ByteBuffer.wrap(byteArrayOf(30,31,99,99,32,33))
        assertArrayEquals(ByteArray(16) { it.toByte() } + byteArrayOf(30,20,31,21,32,22,33,23),
            YuvPlanes.nv21(4, 4, y, 4, 1, u, 3, 1, v, 4, 1))
    }

    @Test(expected = IllegalArgumentException::class)
    fun `odd camera dimensions are rejected`() {
        val plane = ByteBuffer.allocate(20)
        YuvPlanes.nv21(3, 2, plane, 3, 1, plane, 2, 1, plane, 2, 1)
    }
}
