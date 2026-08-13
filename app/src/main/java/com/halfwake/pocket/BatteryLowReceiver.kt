package com.halfwake.pocket

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * ACTION_BATTERY_LOW is one of the system broadcasts still deliverable to a
 * manifest-registered receiver even under Android's post-Oreo background
 * broadcast restrictions — it doesn't need a foreground service or a
 * runtime-registered listener to work. ACTION_BATTERY_OKAY resets the
 * "already notified" flag so the notice can fire again on a future dip.
 */
class BatteryLowReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            Intent.ACTION_BATTERY_LOW -> {
                val prefs = context.getSharedPreferences("halfwake_prefs", Context.MODE_PRIVATE)
                val alreadyNotified = prefs.getBoolean("battery_low_notified", false)
                if (!alreadyNotified) {
                    val percent = UsageRepository.batteryPercent(context)
                    NotificationHelper.notifyCritical(context, percent)
                    prefs.edit().putBoolean("battery_low_notified", true).apply()
                }
            }
            Intent.ACTION_BATTERY_OKAY -> {
                context.getSharedPreferences("halfwake_prefs", Context.MODE_PRIVATE)
                    .edit().putBoolean("battery_low_notified", false).apply()
            }
        }
    }
}
