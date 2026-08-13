package com.halfwake.pocket

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.halfwake.pocket.widget.HalfwakeWidgetProvider
import java.util.concurrent.TimeUnit

class TickWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        AppState.load(applicationContext)

        val metrics = UsageRepository.currentMetrics(applicationContext)
        val result = computeMood(metrics)
        val last = DiaryStore.latest(applicationContext)
        val line = EffectiveState.displayLine(applicationContext, result.mood.id, last?.line, writeTruthLog = true)

        DiaryStore.append(
            applicationContext,
            DiaryEntry(atMillis = System.currentTimeMillis(), mood = result.mood.id, reason = result.reason, line = line)
        )

        if (result.mood == Mood.CRITICAL) {
            NotificationHelper.notifyCritical(applicationContext, metrics.batteryPercent)
        }

        AppState.save(applicationContext)
        HalfwakeWidgetProvider.updateAll(applicationContext)
        return Result.success()
    }

    companion object {
        private const val WORK_NAME = "halfwake_tick"

        fun ensureScheduled(context: Context, minutes: Long = AppState.updateIntervalMinutes.toLong()) {
            val request = PeriodicWorkRequestBuilder<TickWorker>(minutes, TimeUnit.MINUTES).build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.REPLACE, // REPLACE, not KEEP — lets a changed interval actually take effect
                request
            )
        }

        /** Runs a tick immediately — used on first launch so the diary isn't empty. */
        fun runOnce(context: Context) {
            val request = androidx.work.OneTimeWorkRequestBuilder<TickWorker>().build()
            WorkManager.getInstance(context).enqueue(request)
        }
    }
}
