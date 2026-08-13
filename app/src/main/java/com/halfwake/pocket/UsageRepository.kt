package com.halfwake.pocket

import android.app.AppOpsManager
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.PowerManager
import android.os.Process
import android.os.SystemClock
import java.util.Calendar

/**
 * Everything read here comes from UsageStatsManager, Android's own official
 * aggregate usage-tracking API — the same data source Digital Wellbeing
 * itself is built on. No accessibility service, no input capture, no raw
 * keystrokes. If a number can't be traced to one of these calls, it
 * doesn't belong in this file.
 */
object UsageRepository {

    fun hasUsageAccess(context: Context): Boolean {
        val appOps = context.getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
        val mode = appOps.unsafeCheckOpNoThrow(
            AppOpsManager.OPSTR_GET_USAGE_STATS,
            Process.myUid(),
            context.packageName
        )
        return mode == AppOpsManager.MODE_ALLOWED
    }

    /** Milliseconds since the device last booted. Not app-specific. */
    fun uptimeMs(): Long = SystemClock.elapsedRealtime()

    fun hourLocal(): Int = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)

    private fun startOfTodayMs(): Long {
        val cal = Calendar.getInstance()
        cal.set(Calendar.HOUR_OF_DAY, 0)
        cal.set(Calendar.MINUTE, 0)
        cal.set(Calendar.SECOND, 0)
        cal.set(Calendar.MILLISECOND, 0)
        return cal.timeInMillis
    }

    /** Total time any app spent in the foreground today, summed across apps. */
    fun foregroundMsToday(context: Context): Long {
        if (!hasUsageAccess(context)) return 0L
        val usm = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
        val stats = usm.queryUsageStats(
            UsageStatsManager.INTERVAL_DAILY,
            startOfTodayMs(),
            System.currentTimeMillis()
        )
        return stats?.sumOf { it.totalTimeInForeground } ?: 0L
    }

    data class EventScan(
        val appSwitchesLastHour: Int,
        val msSinceLastInteraction: Long?,
    )

    /**
     * Scans today's usage events once and pulls two honest signals from it:
     * how many times an app was brought to the foreground in the last hour
     * (a proxy for "how busy has this phone been"), and how long it's been
     * since the screen was last turned on/unlocked (a proxy for "how long
     * has this phone sat untouched").
     */
    fun scanEvents(context: Context): EventScan {
        if (!hasUsageAccess(context)) return EventScan(0, null)

        val usm = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
        val now = System.currentTimeMillis()
        val hourAgo = now - 3_600_000
        // Look back 48h so "last interaction" survives across a tick boundary.
        val lookback = now - 48L * 3_600_000

        val events = usm.queryEvents(lookback, now)
        val event = UsageEvents.Event()
        var switchesLastHour = 0
        var lastInteractiveAt = 0L

        while (events.hasNextEvent()) {
            events.getNextEvent(event)
            when (event.eventType) {
                UsageEvents.Event.SCREEN_INTERACTIVE -> {
                    if (event.timeStamp > lastInteractiveAt) lastInteractiveAt = event.timeStamp
                }
                UsageEvents.Event.MOVE_TO_FOREGROUND -> {
                    if (event.timeStamp >= hourAgo) switchesLastHour++
                }
            }
        }

        val sinceInteraction = if (lastInteractiveAt > 0) now - lastInteractiveAt else null
        return EventScan(switchesLastHour, sinceInteraction)
    }

    /** Battery percentage, 0-100. No permission required. */
    fun batteryPercent(context: Context): Int {
        val bm = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        return bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
    }

    /** Reads the sticky battery-changed intent for charging state. No permission required. */
    fun isCharging(context: Context): Boolean {
        val intent = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val status = intent?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        return status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL
    }

    /** Android's own thermal status, 0 (none) through 6 (shutdown). API 29+. */
    fun thermalStatus(context: Context): Int {
        val pm = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        return pm.currentThermalStatus
    }

    data class CategoryUsage(val gameMsLastHour: Long, val socialVideoMsLastHour: Long)

    /**
     * Walks today's foreground/background event pairs once, classifies each
     * completed interval by app category, and sums time spent in each
     * category within the last hour. Same UsageEvents source as scanEvents —
     * just read a second way for a different honest question.
     */
    fun categoryUsageLastHour(context: Context): CategoryUsage {
        if (!hasUsageAccess(context)) return CategoryUsage(0, 0)

        val usm = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
        val now = System.currentTimeMillis()
        val hourAgo = now - 3_600_000
        val events = usm.queryEvents(startOfTodayMs(), now)
        val event = UsageEvents.Event()

        var openPackage: String? = null
        var openStart = 0L
        var gameMs = 0L
        var socialMs = 0L

        fun closeInterval(pkg: String, start: Long, end: Long) {
            val overlapStart = maxOf(start, hourAgo)
            val overlapEnd = minOf(end, now)
            if (overlapEnd <= overlapStart) return
            val duration = overlapEnd - overlapStart
            when (AppCategoryRepository.categoryOf(context, pkg)) {
                AppCategory.GAME -> gameMs += duration
                AppCategory.SOCIAL_OR_VIDEO -> socialMs += duration
                AppCategory.OTHER -> {}
            }
        }

        while (events.hasNextEvent()) {
            events.getNextEvent(event)
            when (event.eventType) {
                UsageEvents.Event.MOVE_TO_FOREGROUND -> {
                    openPackage?.let { closeInterval(it, openStart, event.timeStamp) }
                    openPackage = event.packageName
                    openStart = event.timeStamp
                }
                UsageEvents.Event.MOVE_TO_BACKGROUND -> {
                    if (event.packageName == openPackage) {
                        closeInterval(event.packageName, openStart, event.timeStamp)
                        openPackage = null
                    }
                }
            }
        }
        openPackage?.let { closeInterval(it, openStart, now) }

        return CategoryUsage(gameMs, socialMs)
    }

    fun currentMetrics(context: Context): PhoneMetrics {
        val scan = scanEvents(context)
        val category = categoryUsageLastHour(context)
        return PhoneMetrics(
            uptimeMs = uptimeMs(),
            hourLocal = hourLocal(),
            appSwitchesLastHour = scan.appSwitchesLastHour,
            foregroundMsToday = foregroundMsToday(context),
            msSinceLastInteraction = scan.msSinceLastInteraction,
            batteryPercent = batteryPercent(context),
            isCharging = isCharging(context),
            thermalStatus = thermalStatus(context),
            gameMsLastHour = category.gameMsLastHour,
            socialVideoMsLastHour = category.socialVideoMsLastHour,
        )
    }
}
