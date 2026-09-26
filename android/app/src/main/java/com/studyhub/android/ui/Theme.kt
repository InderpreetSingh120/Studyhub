package com.studyhub.android.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Color(0xFF2F5FE0),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDEE7FF),
    onPrimaryContainer = Color(0xFF00174B),
    secondary = Color(0xFF565E71),
    background = Color(0xFFF7F8FC),
    onBackground = Color(0xFF191C21),
    surface = Color(0xFFFCFCFF),
    onSurface = Color(0xFF191C21),
    surfaceVariant = Color(0xFFE2E2EC),
    onSurfaceVariant = Color(0xFF45464F),
    error = Color(0xFFB3261E),
    outline = Color(0xFF757680),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF9FB6FF),
    onPrimary = Color(0xFF002A79),
    primaryContainer = Color(0xFF11409A),
    onPrimaryContainer = Color(0xFFDEE7FF),
    secondary = Color(0xFFBEC6DC),
    background = Color(0xFF111318),
    onBackground = Color(0xFFE2E1E9),
    surface = Color(0xFF111318),
    onSurface = Color(0xFFE2E1E9),
    surfaceVariant = Color(0xFF45464F),
    onSurfaceVariant = Color(0xFFC5C6D0),
    error = Color(0xFFFFB4AB),
    outline = Color(0xFF8F909A),
)

@Composable
fun StudyHubTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        content = content,
    )
}
