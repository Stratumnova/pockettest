package com.halfwake.pocket

/**
 * Kept deliberately independent from DiaryLines (the clock's honest voice)
 * and GameDialogue (Code Breaker's voice). A future addon should be able
 * to extend or replace this pool alone without touching either other
 * system. Starter set only, per the spec — expand once this is live.
 */
object LogDialogue {
    private val pools: Map<String, List<String>> = mapOf(
        "setting_on" to listOf("Noted.", "Written down.", "On the record now.", "Logged."),
        "setting_off" to listOf("Noted.", "Also written down.", "That's on the record too.", "Logged, same as always."),
        "timer_fired" to listOf("Right on time.", "There it goes.", "That's the timer, done.", "Time's up, exactly as set."),
        "alarm_fired" to listOf("Alarm's up.", "That's the one you set.", "Right on schedule.", "There's the wake-up."),
    )

    fun flair(type: String): String {
        val pool = pools[type] ?: return ""
        return pool.random()
    }
}
