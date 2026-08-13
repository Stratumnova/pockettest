package com.halfwake.pocket

import android.content.Context
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager

enum class AppCategory { GAME, SOCIAL_OR_VIDEO, OTHER }

/**
 * Classifies an app using Android's own declared category metadata
 * (ApplicationInfo.category) — real system data most apps supply for the
 * Play Store listing, not a manually maintained guess-list. A small
 * override map catches the handful of high-traffic apps that sometimes
 * report CATEGORY_UNDEFINED despite being unambiguous in practice.
 */
object AppCategoryRepository {

    // Fallback only — used when the OS reports no category at all.
    private val overrides: Map<String, AppCategory> = mapOf(
        "com.google.android.youtube" to AppCategory.SOCIAL_OR_VIDEO,
        "com.instagram.android" to AppCategory.SOCIAL_OR_VIDEO,
        "com.zhiliaoapp.musically" to AppCategory.SOCIAL_OR_VIDEO, // TikTok
        "com.twitter.android" to AppCategory.SOCIAL_OR_VIDEO,
        "com.facebook.katana" to AppCategory.SOCIAL_OR_VIDEO,
        "com.snapchat.android" to AppCategory.SOCIAL_OR_VIDEO,
        "com.reddit.frontpage" to AppCategory.SOCIAL_OR_VIDEO,
    )

    private val cache = HashMap<String, AppCategory>()

    fun categoryOf(context: Context, packageName: String): AppCategory {
        cache[packageName]?.let { return it }

        val result = try {
            val pm = context.packageManager
            val info: ApplicationInfo = pm.getApplicationInfo(packageName, 0)
            when (info.category) {
                ApplicationInfo.CATEGORY_GAME -> AppCategory.GAME
                ApplicationInfo.CATEGORY_SOCIAL, ApplicationInfo.CATEGORY_VIDEO -> AppCategory.SOCIAL_OR_VIDEO
                else -> overrides[packageName] ?: AppCategory.OTHER
            }
        } catch (e: PackageManager.NameNotFoundException) {
            overrides[packageName] ?: AppCategory.OTHER
        }

        cache[packageName] = result
        return result
    }
}
