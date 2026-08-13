package com.halfwake.pocket

import android.content.Context

object EffectiveState {

    fun activeCountdownTimer(): TimerSlot? =
        AppState.timers.firstOrNull { it.running && it.remainingMs in 1..10000 }

    fun moodKey(context: Context): String {
        val now = System.currentTimeMillis()
        if (AppState.ringingSource != null) return "alarm"
        if (activeCountdownTimer() != null) return "alarm"
        if (AppState.gameOverrideType != null && now < AppState.gameOverrideExpiresAt) return AppState.gameOverrideType!!
        val gs = AppState.gameSession
        if (gs != null && gs.started && !gs.finished) return "restless"
        val metrics = UsageRepository.currentMetrics(context)
        return computeMood(metrics).mood.id
    }

    fun reasonText(context: Context): String {
        val key = moodKey(context)
        val cd = activeCountdownTimer()
        if (key == "alarm" && AppState.ringingSource != null) {
            return if (AppState.ringingSource == "timer") "Timer's up — ${AppState.ringingLabel}."
            else "Alarm going off — ${AppState.ringingLabel}."
        }
        if (key == "alarm" && cd != null) return "${(cd.remainingMs / 1000) + 1}s left on ${cd.name}."
        if (key == "restless") {
            val gs = AppState.gameSession
            if (gs != null) {
                val used = 6 - gs.guessesLeft
                return "Left a code half-cracked. $used guess${if (used == 1) "" else "es"} in, none of it finished."
            }
        }
        val metrics = UsageRepository.currentMetrics(context)
        return computeMood(metrics).reason
    }

    /** The line actually shown on the face — NPC flair if an addon
     * provides one for this mood, otherwise the honest diary line.
     * Always writes the honest -log entry regardless of what's displayed. */
    fun displayLine(context: Context, moodKey: String, lastLine: String?, writeTruthLog: Boolean = false): String {
        val moodEnum = Mood.entries.find { it.id == moodKey }
        val honestLine = if (moodEnum != null) DiaryLines.pick(moodEnum, lastLine) else reasonText(context)

        if (writeTruthLog) {
            LogStore.appendTruth(context, moodKey, honestLine)
        }

        val flair = NpcBridge.flairFor(context, moodKey)
        return flair ?: honestLine
    }
}
