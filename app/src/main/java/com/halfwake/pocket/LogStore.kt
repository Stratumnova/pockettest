package com.halfwake.pocket

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** layer: "log" (core truth, core-engine-only), "personality" (NPC flair,
 * addon-only), or "tech" (under-the-hood, addon-only). Only LogStore's own
 * append functions may write "log" — no addon is ever given that path. */
data class LogEntry(val atMillis: Long, val category: String, val layer: String, val text: String)

object LogFilters {
    // 2/3 default, Tech off — per spec.
    var log: Boolean = true
    var personality: Boolean = true
    var tech: Boolean = false
}

object LogStore {
    private const val FILE_NAME = "log.json"
    private const val MAX_ENTRIES = 2000

    private fun file(context: Context): File = File(context.filesDir, FILE_NAME)

    fun load(context: Context): List<LogEntry> {
        val f = file(context)
        if (!f.exists()) return emptyList()
        return try {
            val arr = JSONArray(f.readText())
            (0 until arr.length()).map { i ->
                val o = arr.getJSONObject(i)
                LogEntry(o.getLong("at"), o.getString("category"), o.getString("layer"), o.getString("text"))
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    private fun save(context: Context, entries: List<LogEntry>) {
        val arr = JSONArray()
        entries.takeLast(MAX_ENTRIES).forEach { e ->
            arr.put(JSONObject().apply {
                put("at", e.atMillis); put("category", e.category); put("layer", e.layer); put("text", e.text)
            })
        }
        file(context).writeText(arr.toString())
    }

    /** Only path for writing a "log" (truth) entry — nothing addon-facing
     * calls this. Automatically appends log-flair for readability. */
    fun appendTruth(context: Context, category: String, text: String, flairType: String? = null) {
        val flair = flairType?.let { " ${LogDialogue.flair(it)}" } ?: ""
        append(context, LogEntry(System.currentTimeMillis(), category, "log", text + flair))
    }

    /** Addon-facing write path — layer must be "personality" or "tech",
     * enforced here so an addon can never smuggle a "log" entry through. */
    fun appendAddon(context: Context, category: String, layer: String, text: String) {
        if (layer != "personality" && layer != "tech") return
        append(context, LogEntry(System.currentTimeMillis(), category, layer, text))
    }

    private fun append(context: Context, entry: LogEntry) {
        val entries = load(context) + entry
        save(context, entries)
    }

    fun filtered(context: Context): List<LogEntry> {
        return load(context).filter { e ->
            when (e.layer) {
                "log" -> LogFilters.log
                "personality" -> LogFilters.personality
                "tech" -> LogFilters.tech
                else -> false
            }
        }
    }

    fun formatForCopy(context: Context, layer: String?): String {
        val fmt = SimpleDateFormat("MMM d, h:mm a", Locale.getDefault())
        val entries = load(context).filter { layer == null || it.layer == layer }
        return entries.joinToString("\n") { e ->
            "[${fmt.format(Date(e.atMillis))}] ${e.category}-${e.layer}: ${e.text}"
        }
    }
}
