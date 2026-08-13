package com.halfwake.pocket

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

data class DiaryEntry(val atMillis: Long, val mood: String, val reason: String, val line: String)

object DiaryStore {
    private const val FILE_NAME = "state.json"
    private const val MAX_HISTORY = 500

    private fun file(context: Context): File = File(context.filesDir, FILE_NAME)

    fun load(context: Context): List<DiaryEntry> {
        val f = file(context)
        if (!f.exists()) return emptyList()
        return try {
            val arr = JSONArray(f.readText())
            (0 until arr.length()).map { i ->
                val o = arr.getJSONObject(i)
                DiaryEntry(
                    atMillis = o.getLong("at"),
                    mood = o.getString("mood"),
                    reason = o.getString("reason"),
                    line = o.getString("line"),
                )
            }
        } catch (e: Exception) {
            emptyList()
        }
    }

    private fun save(context: Context, entries: List<DiaryEntry>) {
        val arr = JSONArray()
        entries.takeLast(MAX_HISTORY).forEach { e ->
            arr.put(JSONObject().apply {
                put("at", e.atMillis)
                put("mood", e.mood)
                put("reason", e.reason)
                put("line", e.line)
            })
        }
        file(context).writeText(arr.toString())
    }

    fun append(context: Context, entry: DiaryEntry) {
        val entries = load(context) + entry
        save(context, entries)
    }

    fun latest(context: Context): DiaryEntry? = load(context).lastOrNull()
}
