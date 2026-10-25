package com.zaya.companion.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

/**
 * Soft rose accents on warm dark surfaces; status colors retain their meaning.
 */
private val ZayaColors = darkColorScheme(
    primary = Color(0xFFF4A8C5),
    onPrimary = Color(0xFF461B30),
    primaryContainer = Color(0xFF593044),
    onPrimaryContainer = Color(0xFFFFD9E7),
    secondary = Color(0xFFDDB8D3),
    onSecondary = Color(0xFF35202F),
    secondaryContainer = Color(0xFF44303E),
    onSecondaryContainer = Color(0xFFFAD9ED),
    background = Color(0xFF181218),
    onBackground = Color(0xFFF8EAF0),
    surface = Color(0xFF241C24),
    onSurface = Color(0xFFF8EAF0),
    surfaceVariant = Color(0xFF342731),
    onSurfaceVariant = Color(0xFFD2BBC8),
    surfaceContainer = Color(0xFF2B2029),
    outline = Color(0xFF947C8A),
    outlineVariant = Color(0xFF4C3B47),
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
    val muted = Color(0xFFBAA2B1)
    val quiet = Color(0xFF4C3B47)
}

@Composable
fun ZayaTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = ZayaColors, content = content)
}
