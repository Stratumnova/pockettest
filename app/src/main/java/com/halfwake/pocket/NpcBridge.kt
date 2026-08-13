package com.halfwake.pocket

import android.content.Context
import com.halfwake.pocket.addons.AddonManager
import org.json.JSONObject

/**
 * This is the actual addon-loader proof point: the base app always has
 * this hook, always checks for a "personality_dialogue" addon, and always
 * has a real fallback if none is found. Removing the addon folder makes
 * this silently return null every time — the caller falls back to the
 * plain honest diary line, nothing else changes.
 *
 * This first NPC addon is intentionally simple — mood-keyed line pools,
 * no memory tiers, no token economy yet. That's the next, separate build.
 * This one exists to prove the mechanism works end to end.
 */
object NpcBridge {

    /** Returns a flair line for the given mood if a personality-dialogue
     * addon is installed and has content for that mood, else null. */
    fun flairFor(context: Context, moodKey: String): String? {
        val addons = AddonManager.scan(context)
        val personalityAddon = addons.firstOrNull { it.provides.contains("personality_dialogue") } ?: return null

        val raw = AddonManager.readAddonFile(personalityAddon, "personality-lines.json") ?: return null
        return try {
            val json = JSONObject(raw)
            val pool = json.optJSONArray(moodKey) ?: return null
            if (pool.length() == 0) return null
            val line = pool.getString((0 until pool.length()).random())

            // Logged as personality, addon-namespaced — never as truth.
            LogStore.appendAddon(context, moodKey, "personality", line)
            line
        } catch (e: Exception) {
            null
        }
    }

    /** True if any installed addon declares itself a personality source —
     * used by the UI to decide whether to even attempt flairFor(). */
    fun hasPersonalityAddon(context: Context): Boolean =
        AddonManager.scan(context).any { it.provides.contains("personality_dialogue") }
}
