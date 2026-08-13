package com.halfwake.pocket.addons

import android.content.Context
import org.json.JSONObject
import java.io.File

/**
 * Addon folders live at Android/data/com.halfwake.pocket/files/addons/<addon-id>/
 * — the app's own external files directory. No storage permission is
 * needed to read or write here; any file manager can browse to it, which
 * is exactly the "drop a folder in" workflow this is built for.
 *
 * Each addon folder must contain an addon.json manifest:
 * {
 *   "id": "sample-addon",
 *   "name": "Sample Addon",
 *   "version": "0.1",
 *   "provides": ["log_dialogue"]
 * }
 *
 * The base app never assumes an addon is present. Every hook that reads
 * from AddonManager must have a safe, honest-only fallback if the list
 * comes back empty — removing every addon folder must never change core
 * behavior, only remove what that addon added.
 */
data class AddonManifest(
    val id: String,
    val name: String,
    val version: String,
    val provides: List<String>,
    val folder: File,
)

object AddonManager {

    fun addonsDir(context: Context): File {
        val dir = File(context.getExternalFilesDir(null), "addons")
        if (!dir.exists()) dir.mkdirs()
        return dir
    }

    /** Scans the addons folder fresh each call — cheap, and addons only
     * change when the app isn't running (someone editing files), so no
     * caching is needed. */
    fun scan(context: Context): List<AddonManifest> {
        val dir = addonsDir(context)
        val found = mutableListOf<AddonManifest>()

        val subfolders = dir.listFiles { f -> f.isDirectory } ?: return emptyList()
        for (folder in subfolders) {
            val manifestFile = File(folder, "addon.json")
            if (!manifestFile.exists()) continue
            try {
                val json = JSONObject(manifestFile.readText())
                val providesArray = json.optJSONArray("provides")
                val provides = mutableListOf<String>()
                if (providesArray != null) {
                    for (i in 0 until providesArray.length()) provides.add(providesArray.getString(i))
                }
                found.add(
                    AddonManifest(
                        id = json.optString("id", folder.name),
                        name = json.optString("name", folder.name),
                        version = json.optString("version", "0.0"),
                        provides = provides,
                        folder = folder,
                    )
                )
            } catch (e: Exception) {
                // A malformed addon.json is skipped, not fatal — one bad
                // addon folder must never break the base app or any other
                // addon sitting next to it.
                continue
            }
        }
        return found
    }

    /** Reads a specific data file out of a specific addon's folder, or
     * null if the addon or file isn't present. Every call site using this
     * must have a real fallback — this is the actual enforcement point
     * for "removing an addon never breaks the app." */
    fun readAddonFile(addon: AddonManifest, filename: String): String? {
        val f = File(addon.folder, filename)
        return if (f.exists()) f.readText() else null
    }
}
