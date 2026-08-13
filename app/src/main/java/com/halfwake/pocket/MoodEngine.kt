package com.halfwake.pocket

/**
 * Same rule as always: every mood must be traceable to one real metric
 * crossing one real threshold. THRESHOLDS ARE PLACEHOLDERS — tune them
 * once you've watched a week or two of your own real usage.
 *
 * Order matters: rules are checked top to bottom, first match wins. This
 * ordering is deliberate, not arbitrary — see inline notes on Quiet vs.
 * Restless and Critical vs. everything else.
 */
object Thresholds {
    const val CRITICAL_BATTERY_PERCENT = 10

    // PowerManager thermal status constants: 0 NONE, 1 LIGHT, 2 MODERATE,
    // 3 SEVERE, 4 CRITICAL, 5 EMERGENCY, 6 SHUTDOWN.
    const val BURNING_THERMAL_STATUS_MIN = 3

    const val GROGGY_UPTIME_MS = 60L * 60 * 1000

    const val HAPPY_GAME_MS_LAST_HOUR = 15L * 60 * 1000
    const val SAD_SOCIAL_MS_LAST_HOUR = 30L * 60 * 1000

    const val TIRED_FOREGROUND_MS_TODAY = 6L * 60 * 60 * 1000

    const val BUSY_SWITCHES_PER_HOUR = 15

    const val QUIET_HOUR_START = 0
    const val QUIET_HOUR_END = 5
    const val QUIET_MAX_FOREGROUND_MS_TODAY = 30L * 60 * 1000

    const val RESTLESS_HOURS_SINCE_INTERACTION = 6
}

enum class Mood(val id: String) {
    CRITICAL("critical"),
    BURNING("burning"),
    GROGGY("groggy"),
    FED("fed"),
    HAPPY("happy"),
    SAD("sad"),
    TIRED("tired"),
    BUSY("busy"),
    QUIET("quiet"),
    RESTLESS("restless"),
    CONTENT("content"),
}

data class MoodResult(val mood: Mood, val reason: String)

data class PhoneMetrics(
    val uptimeMs: Long,
    val hourLocal: Int,
    val appSwitchesLastHour: Int,
    val foregroundMsToday: Long,
    val msSinceLastInteraction: Long?,
    val batteryPercent: Int,
    val isCharging: Boolean,
    val thermalStatus: Int,
    val gameMsLastHour: Long,
    val socialVideoMsLastHour: Long,
)

fun computeMood(m: PhoneMetrics): MoodResult {
    // 1. Critical — battery on the floor and not currently being helped.
    //    Overrides everything; a phone about to die doesn't get to be "happy".
    if (m.batteryPercent <= Thresholds.CRITICAL_BATTERY_PERCENT && !m.isCharging) {
        return MoodResult(Mood.CRITICAL, "battery at ${m.batteryPercent}%, not charging")
    }

    // 2. Burning up — thermal throttling underway.
    if (m.thermalStatus >= Thresholds.BURNING_THERMAL_STATUS_MIN) {
        return MoodResult(Mood.BURNING, "thermal status ${m.thermalStatus}, at/above ${Thresholds.BURNING_THERMAL_STATUS_MIN}")
    }

    // 3. Groggy — just rebooted.
    if (m.uptimeMs < Thresholds.GROGGY_UPTIME_MS) {
        val mins = m.uptimeMs / 60000
        return MoodResult(Mood.GROGGY, "uptime is ${mins}m, under the 60m groggy threshold")
    }

    // 4. Fed — plugged in and charging right now.
    if (m.isCharging) {
        return MoodResult(Mood.FED, "currently charging, ${m.batteryPercent}%")
    }

    // 5. Happy — meaningful game time in the last hour.
    if (m.gameMsLastHour >= Thresholds.HAPPY_GAME_MS_LAST_HOUR) {
        val mins = m.gameMsLastHour / 60000
        return MoodResult(Mood.HAPPY, "${mins}min in game apps this hour")
    }

    // 6. Sad — heavy social/video time in the last hour. This is the
    //    doomscroll signal — deliberately gentle wording, not guilt-tripping.
    if (m.socialVideoMsLastHour >= Thresholds.SAD_SOCIAL_MS_LAST_HOUR) {
        val mins = m.socialVideoMsLastHour / 60000
        return MoodResult(Mood.SAD, "${mins}min in social/video apps this hour")
    }

    // 7. Tired — a lot of total screen time today, regardless of app type.
    if (m.foregroundMsToday >= Thresholds.TIRED_FOREGROUND_MS_TODAY) {
        val hours = m.foregroundMsToday / 3600000
        return MoodResult(Mood.TIRED, "${hours}h+ of screen time today")
    }

    // 8. Busy — high app-switching rate, not tied to any one category.
    if (m.appSwitchesLastHour >= Thresholds.BUSY_SWITCHES_PER_HOUR) {
        return MoodResult(Mood.BUSY, "${m.appSwitchesLastHour} app switches this hour")
    }

    // 9. Quiet — checked before Restless so ordinary sleep reads as "quiet"
    //    rather than misreading six untouched hours at 3am as something odd.
    val isLateNight = m.hourLocal in Thresholds.QUIET_HOUR_START..Thresholds.QUIET_HOUR_END
    if (isLateNight && m.foregroundMsToday <= Thresholds.QUIET_MAX_FOREGROUND_MS_TODAY) {
        val mins = m.foregroundMsToday / 60000
        return MoodResult(Mood.QUIET, "${m.hourLocal}:00 local, ${mins}min screen time today")
    }

    // 10. Restless — long daytime stretch with no interaction at all.
    val hoursSinceInteraction = m.msSinceLastInteraction?.let { it / 3600000.0 }
    if (hoursSinceInteraction != null && hoursSinceInteraction >= Thresholds.RESTLESS_HOURS_SINCE_INTERACTION) {
        return MoodResult(
            Mood.RESTLESS,
            "%.1fh since last screen interaction".format(hoursSinceInteraction)
        )
    }

    // 11. Content — default.
    val hours = m.uptimeMs / 3600000
    return MoodResult(Mood.CONTENT, "uptime ${hours}h, no other condition met")
}
