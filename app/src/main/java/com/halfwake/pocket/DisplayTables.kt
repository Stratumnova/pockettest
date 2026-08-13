package com.halfwake.pocket

import android.graphics.Color

data class FaceParams(val brow: Float, val eyeOpen: Float, val mouth: String, val decor: String = "none", val xEyes: Boolean = false)
data class ThemeColors(val bg: Int, val fg: Int, val muted: Int, val accent: Int)

/** MOODS and FACES must always share an identical key set — this was a
 * real crash once (an "alarm" mood existed in one table but not the
 * other) and is now a standing rule, not just a preference. */
object Moods {
    private val colors: Map<String, Int> = mapOf(
        Mood.CRITICAL.id to Color.parseColor("#a34444"),
        Mood.BURNING.id to Color.parseColor("#c2703d"),
        Mood.GROGGY.id to Color.parseColor("#9a9488"),
        Mood.FED.id to Color.parseColor("#4f7a3a"),
        Mood.HAPPY.id to Color.parseColor("#c9a227"),
        Mood.SAD.id to Color.parseColor("#5c6a8f"),
        Mood.TIRED.id to Color.parseColor("#7a7385"),
        Mood.BUSY.id to Color.parseColor("#c2703d"),
        Mood.QUIET.id to Color.parseColor("#3d4a5c"),
        Mood.RESTLESS.id to Color.parseColor("#6f6b8f"),
        Mood.CONTENT.id to Color.parseColor("#6b7a5e"),
        "smug" to Color.parseColor("#c9a227"),
        "grumpy" to Color.parseColor("#a34444"),
        "alarm" to Color.parseColor("#a34444"),
        "startled" to Color.parseColor("#e08a3d"),
    )
    fun colorOf(moodKey: String): Int = colors[moodKey] ?: colors[Mood.CONTENT.id]!!
}

object Faces {
    private val params: Map<String, FaceParams> = mapOf(
        Mood.CRITICAL.id to FaceParams(-0.5f, 1.1f, "o", "sweat"),
        Mood.BURNING.id to FaceParams(-0.7f, 0.6f, "frown", "heat"),
        Mood.GROGGY.id to FaceParams(-0.1f, 0.35f, "flat", "zzz"),
        Mood.FED.id to FaceParams(0.35f, 1.0f, "smile", "spark"),
        Mood.HAPPY.id to FaceParams(0.5f, 1.0f, "bigsmile", "sparkle"),
        Mood.SAD.id to FaceParams(-0.4f, 0.85f, "frown", "tear"),
        Mood.TIRED.id to FaceParams(-0.15f, 0.3f, "flatfrown", "bags"),
        Mood.BUSY.id to FaceParams(0.15f, 1.0f, "neutral", "motion"),
        Mood.QUIET.id to FaceParams(0.05f, 0.05f, "flatsmall", "moon"),
        Mood.RESTLESS.id to FaceParams(-0.25f, 1.05f, "wavy", "squiggle"),
        Mood.CONTENT.id to FaceParams(0.2f, 1.0f, "gentlesmile"),
        "smug" to FaceParams(0.15f, 0.85f, "smirk"),
        "grumpy" to FaceParams(-0.6f, 0.7f, "frown", "cloud"),
        "alarm" to FaceParams(-0.6f, 1.0f, "sour", xEyes = true),
        "startled" to FaceParams(0.4f, 1.5f, "o"),
    )
    fun of(moodKey: String): FaceParams = params[moodKey] ?: params[Mood.CONTENT.id]!!
}

object Themes {
    private val palettes: Map<String, ThemeColors> = mapOf(
        "light" to ThemeColors(Color.parseColor("#f4f1ec"), Color.parseColor("#23211d"), Color.parseColor("#8a8578"), Color.parseColor("#6b7a5e")),
        "dark" to ThemeColors(Color.parseColor("#1e2126"), Color.parseColor("#f4f1ec"), Color.parseColor("#9aa0a8"), Color.parseColor("#7a92a8")),
        "colorpop" to ThemeColors(Color.parseColor("#fff8f0"), Color.parseColor("#1a1a1a"), Color.parseColor("#7a4a9e"), Color.parseColor("#e0457b")),
    )
    fun of(name: String): ThemeColors = palettes[name] ?: palettes["light"]!!
}
