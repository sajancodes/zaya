package com.zaya.companion.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

/**
 * The dashboard's palette, so the phone is recognisably the same Zaya and not a
 * differently-branded remote control.
 */
private val ZayaColors = darkColorScheme(
    primary = Color(0xFF6366F1),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFF232552),
    onPrimaryContainer = Color(0xFFDDE3ED),
    secondary = Color(0xFF8B8FF8),
    onSecondary = Color(0xFF0B0D14),
    background = Color(0xFF07090F),
    onBackground = Color(0xFFDDE3ED),
    surface = Color(0xFF11141C),
    onSurface = Color(0xFFDDE3ED),
    surfaceVariant = Color(0xFF1B1E27),
    onSurfaceVariant = Color(0xFF8A93A6),
    outline = Color(0xFF2A2F3D),
    error = Color(0xFFEF4444),
    onError = Color(0xFF1B0B0B),
    errorContainer = Color(0xFF3B1416),
    onErrorContainer = Color(0xFFFBD5D5),
)

object ZayaAccent {
    val green = Color(0xFF22C55E)
    val amber = Color(0xFFF59E0B)
    val red = Color(0xFFEF4444)
    val blue = Color(0xFF3B82F6)
    val muted = Color(0xFF5E6A7E)
    val quiet = Color(0xFF2A2F3D)
}

@Composable
fun ZayaTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = ZayaColors, content = content)
}
