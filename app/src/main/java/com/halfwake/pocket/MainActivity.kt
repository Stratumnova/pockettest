package com.halfwake.pocket

import android.Manifest
import android.app.Activity
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.view.View
import android.widget.*
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.google.android.material.bottomnavigation.BottomNavigationView
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : AppCompatActivity() {

    private lateinit var faceView: FaceClockView
    private lateinit var tabContent: FrameLayout
    private var activeTab = "home"
    private var currentInput = mutableListOf<Int>()
    private var playMode = "game"

    private val notifPermLauncher = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }
    private val soundPickerLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            val uri: Uri? = result.data?.data
            if (uri != null) {
                contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
                AppState.alarmSoundUri = uri.toString()
                LogStore.appendTruth(this, "setting", "Setting changed: Alarm sound turned ON.", "setting_on")
                AppState.save(this)
                renderTab()
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        AppState.load(this)

        faceView = findViewById(R.id.face_clock)
        tabContent = findViewById(R.id.tab_content)

        findViewById<BottomNavigationView>(R.id.tab_bar).setOnItemSelectedListener { item ->
            activeTab = when (item.itemId) {
                R.id.tab_home -> "home"; R.id.tab_play -> "play"; R.id.tab_tools -> "tools"
                R.id.tab_settings -> "settings"; else -> "log"
            }
            renderTab(); true
        }

        requestNotifPermIfNeeded()
        faceView.tick()
        refreshFace()
        renderTab()
        startForegroundTickLoop()
    }

    override fun onResume() {
        super.onResume()
        if (UsageRepository.hasUsageAccess(this)) {
            TickWorker.ensureScheduled(this, AppState.updateIntervalMinutes.toLong())
            if (DiaryStore.load(this).isEmpty()) TickWorker.runOnce(this)
        }
        refreshFace(); renderTab()
    }

    private fun requestNotifPermIfNeeded() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            notifPermLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    private fun refreshFace() {
        val key = EffectiveState.moodKey(this)
        faceView.moodKey = key
        faceView.reasonText = EffectiveState.reasonText(this)
        faceView.invalidate()
    }

    // ---------- tab rendering ----------

    private fun renderTab() {
        tabContent.removeAllViews()
        val view = when (activeTab) {
            "home" -> buildHomeTab()
            "play" -> buildPlayTab()
            "tools" -> buildToolsTab()
            "settings" -> buildSettingsTab()
            else -> buildLogTab()
        }
        tabContent.addView(view)
    }

    private fun sectionTitle(text: String): TextView = TextView(this).apply {
        this.text = text.uppercase(); textSize = 12f; setPadding(0, 24, 0, 12)
    }

    // ---------- Home ----------

    private fun buildHomeTab(): View {
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }

        if (!UsageRepository.hasUsageAccess(this)) {
            col.addView(TextView(this).apply {
                text = "Halfwake needs Usage Access to read screen time and app activity — it never reads what you type, only how long and how often apps are used."
                setPadding(0, 0, 0, 16)
            })
            col.addView(Button(this).apply {
                text = "Grant usage access"
                setOnClickListener { startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)) }
            })
            return col
        }

        val key = EffectiveState.moodKey(this)
        col.addView(TextView(this).apply { text = key.uppercase(); textSize = 14f; gravity = Gravity.CENTER })
        col.addView(TextView(this).apply {
            text = EffectiveState.reasonText(this@MainActivity)
            textSize = 15f; gravity = Gravity.CENTER; setPadding(0, 8, 0, 0)
        })
        return col
    }

    // ---------- Play: Code Breaker + Calculator ----------

    private fun buildPlayTab(): View {
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val modeBar = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER }
        modeBar.addView(Button(this).apply { text = "Code Breaker"; setOnClickListener { playMode = "game"; renderTab() } })
        modeBar.addView(Button(this).apply { text = "Calculator"; setOnClickListener { playMode = "calculator"; renderTab() } })
        col.addView(modeBar)
        col.addView(if (playMode == "game") buildGameArea() else buildCalculatorArea())
        return col
    }

    private fun buildGameArea(): View {
        if (AppState.gameSession == null) startNewGame()
        val gs = AppState.gameSession!!
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(0, 16, 0, 0) }

        col.addView(TextView(this).apply {
            text = "Wins: ${AppState.winCount}  ·  Losses: ${AppState.loseCount}"; gravity = Gravity.CENTER
        })

        val board = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        gs.guesses.forEach { (guess, exact, partial) ->
            board.addView(TextView(this).apply { text = "${guess.joinToString(" ")}   —   $exact exact · $partial close" })
        }
        col.addView(board)

        val inputRow = TextView(this).apply {
            text = if (currentInput.isEmpty()) "____" else currentInput.joinToString(" ")
            gravity = Gravity.CENTER; textSize = 20f; setPadding(0, 16, 0, 16)
        }
        col.addView(inputRow)

        if (!gs.finished) {
            val pad = GridLayout(this).apply { columnCount = 3 }
            for (d in 0..9) {
                pad.addView(Button(this).apply {
                    text = d.toString()
                    setOnClickListener { if (currentInput.size < 4) { currentInput.add(d); renderTab() } }
                })
            }
            col.addView(pad)
            val actions = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER }
            actions.addView(Button(this).apply { text = "Clear"; setOnClickListener { currentInput.clear(); renderTab() } })
            actions.addView(Button(this).apply { text = "Guess"; setOnClickListener { submitGuess() } })
            col.addView(actions)
            col.addView(TextView(this).apply { text = "${gs.guessesLeft} guesses left"; gravity = Gravity.CENTER })
        } else {
            col.addView(TextView(this).apply { text = "Game over"; gravity = Gravity.CENTER })
        }
        col.addView(Button(this).apply { text = "New game"; setOnClickListener { startNewGame(); renderTab() } })
        return col
    }

    private fun startNewGame() {
        AppState.gameSession = GameSession(secret = CodeBreakerLogic.newSecret())
        AppState.gameOverrideType = null
        currentInput.clear()
    }

    private fun submitGuess() {
        val gs = AppState.gameSession ?: return
        if (gs.finished || currentInput.size < 4) return
        gs.started = true
        val result = CodeBreakerLogic.score(currentInput.toList(), gs.secret)
        gs.guesses.add(Triple(currentInput.toList(), result.exact, result.partial))
        gs.guessesLeft--
        currentInput.clear()

        val cb = AppState.watchlist.find { it.name == "Code Breaker" }
        if (cb?.watched == true) cb.minutes += 1

        when {
            result.exact == 4 -> {
                gs.finished = true; AppState.winCount++
                AppState.gameOverrideType = "smug"; AppState.gameOverrideExpiresAt = System.currentTimeMillis() + 20 * 60 * 1000
                LogStore.appendTruth(this, "smug", "Won a round of Code Breaker. Feeling good about it.")
            }
            gs.guessesLeft == 0 -> {
                gs.finished = true; AppState.loseCount++
                AppState.gameOverrideType = "grumpy"; AppState.gameOverrideExpiresAt = System.currentTimeMillis() + 20 * 60 * 1000
                LogStore.appendTruth(this, "grumpy", "Lost a round of Code Breaker. Not thrilled about it.")
            }
        }
        AppState.save(this)
        refreshFace(); renderTab()
    }

    // ---------- Calculator ----------

    private var calcDisplay = "0"; private var calcAcc: Double? = null; private var calcOp: String? = null; private var calcFresh = true

    private fun buildCalculatorArea(): View {
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(0, 16, 0, 0) }
        col.addView(TextView(this).apply { text = calcDisplay; textSize = 24f; gravity = Gravity.END; setPadding(16, 16, 16, 16) })
        val pad = GridLayout(this).apply { columnCount = 4 }
        val keys = listOf("7","8","9","/","4","5","6","*","1","2","3","-","C","0",".","+","=")
        keys.forEach { k ->
            pad.addView(Button(this).apply { text = k; setOnClickListener { calcPress(k); renderTab() } })
        }
        col.addView(pad)
        return col
    }

    private fun calcPress(key: String) {
        when {
            key.toDoubleOrNull() != null || key == "." -> {
                calcDisplay = if (calcFresh) (if (key == ".") "0." else key) else calcDisplay + key
                calcFresh = false
            }
            key == "C" -> { calcDisplay = "0"; calcAcc = null; calcOp = null; calcFresh = true }
            key in listOf("+", "-", "*", "/") -> {
                val cur = calcDisplay.toDoubleOrNull() ?: 0.0
                calcAcc = if (calcOp != null) applyOp(calcAcc ?: 0.0, cur, calcOp!!) else cur
                calcOp = key; calcFresh = true
            }
            key == "=" -> {
                if (calcOp != null) {
                    val cur = calcDisplay.toDoubleOrNull() ?: 0.0
                    val result = applyOp(calcAcc ?: 0.0, cur, calcOp!!)
                    calcDisplay = result.toString()
                    calcAcc = null; calcOp = null; calcFresh = true
                }
            }
        }
    }
    private fun applyOp(a: Double, b: Double, op: String): Double = when (op) {
        "+" -> a + b; "-" -> a - b; "*" -> a * b; "/" -> if (b == 0.0) Double.NaN else a / b; else -> b
    }

    // ---------- Tools: stopwatch, timers, alarms ----------

    private fun buildToolsTab(): View {
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }

        col.addView(sectionTitle("Timers (name them, keep them)"))
        AppState.timers.forEachIndexed { i, tm -> col.addView(buildTimerRow(i, tm)) }
        if (AppState.timers.size < 5) {
            col.addView(Button(this).apply {
                text = "+ Add timer (${AppState.timers.size}/5)"
                setOnClickListener { AppState.timers.add(TimerSlot("Timer ${AppState.timers.size + 1}", 0, 0, false)); AppState.save(this@MainActivity); renderTab() }
            })
        }

        col.addView(sectionTitle("Alarms"))
        AppState.alarms.forEachIndexed { i, al -> col.addView(buildAlarmRow(i, al)) }

        if (AppState.ringingSource != null) {
            col.addView(Button(this).apply {
                text = "Dismiss — ${AppState.ringingSource} ringing"
                setOnClickListener { dismissRinging(); renderTab() }
            })
        }
        return col
    }

    private fun buildTimerRow(i: Int, tm: TimerSlot): View {
        val row = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(0, 12, 0, 12) }
        val nameField = EditText(this).apply {
            setText(tm.name)
            setOnFocusChangeListener { _, hasFocus -> if (!hasFocus) { tm.name = text.toString().ifBlank { "Timer ${i+1}" }; AppState.save(this@MainActivity) } }
        }
        row.addView(nameField)
        row.addView(TextView(this).apply { text = fmtMs(tm.remainingMs); textSize = 18f; gravity = Gravity.CENTER })

        if (!tm.running) {
            val adj = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER }
            listOf(1L to "+1m", 5L to "+5m", 10L to "+10m", 20L to "+20m").forEach { (mins, label) ->
                adj.addView(Button(this).apply { text = label; setOnClickListener {
                    tm.remainingMs = (tm.remainingMs + mins * 60000).coerceAtLeast(0); tm.totalMs = tm.remainingMs; AppState.save(this@MainActivity); renderTab()
                } })
            }
            row.addView(adj)
            val sub = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER }
            listOf(1L to "-1m", 5L to "-5m", 10L to "-10m", 20L to "-20m").forEach { (mins, label) ->
                sub.addView(Button(this).apply { text = label; setOnClickListener {
                    tm.remainingMs = (tm.remainingMs - mins * 60000).coerceAtLeast(0); tm.totalMs = tm.remainingMs; AppState.save(this@MainActivity); renderTab()
                } })
            }
            row.addView(sub)
            val actions = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER }
            actions.addView(Button(this).apply { text = "Start"; isEnabled = tm.remainingMs > 0; setOnClickListener { tm.running = true; AppState.save(this@MainActivity); renderTab() } })
            actions.addView(Button(this).apply { text = "Reset"; setOnClickListener { tm.remainingMs = 0; tm.totalMs = 0; AppState.save(this@MainActivity); renderTab() } })
            row.addView(actions)
        } else {
            row.addView(Button(this).apply { text = "Cancel"; setOnClickListener { tm.running = false; tm.remainingMs = 0; AppState.save(this@MainActivity); renderTab() } })
        }
        return row
    }

    private fun buildAlarmRow(i: Int, al: AlarmSlot): View {
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL; setPadding(0, 8, 0, 8) }
        row.addView(Switch(this).apply {
            isChecked = al.enabled
            setOnCheckedChangeListener { _, checked ->
                al.enabled = checked
                if (AppState.appTracker) LogStore.appendTruth(this@MainActivity, "setting", "Setting changed: ${al.name} (${al.time}) turned ${if (checked) "ON" else "OFF"}.", if (checked) "setting_on" else "setting_off")
                AppState.save(this@MainActivity)
            }
        })
        row.addView(EditText(this).apply {
            setText(al.name)
            setOnFocusChangeListener { _, hasFocus -> if (!hasFocus) { al.name = text.toString().ifBlank { "Alarm ${i+1}" }; AppState.save(this@MainActivity) } }
        })
        row.addView(EditText(this).apply {
            setText(al.time)
            setOnFocusChangeListener { _, hasFocus -> if (!hasFocus) { al.time = text.toString(); al.firedKey = null; AppState.save(this@MainActivity) } }
        })
        return row
    }

    private fun fmtMs(ms: Long): String {
        val total = (ms / 1000).coerceAtLeast(0)
        return String.format("%d:%02d", total / 60, total % 60)
    }

    private fun dismissRinging() {
        AppState.ringingSource = null; AppState.ringingLabel = null
        AppState.save(this)
        refreshFace()
    }

    /** Runs only while the app is in the foreground — real background
     * firing (app closed) needs AlarmManager-scheduled exact wakeups per
     * timer/alarm, which is a genuine follow-up build, not implemented
     * here yet. Flagging honestly rather than pretending this covers it. */
    private val tickHandler = android.os.Handler(android.os.Looper.getMainLooper())
    private fun startForegroundTickLoop() {
        tickHandler.postDelayed({
            var changed = false
            AppState.timers.forEach { tm ->
                if (tm.running) {
                    tm.remainingMs -= 1000
                    changed = true
                    if (tm.remainingMs <= 0) {
                        tm.running = false; tm.remainingMs = 0
                        AppState.ringingSource = "timer"; AppState.ringingLabel = tm.name
                        LogStore.appendTruth(this, "alarm", "Timer went off (${tm.name}).", "timer_fired")
                    }
                }
            }
            val cal = java.util.Calendar.getInstance()
            val hhmm = String.format("%02d:%02d", cal.get(java.util.Calendar.HOUR_OF_DAY), cal.get(java.util.Calendar.MINUTE))
            val dayKey = "${cal.get(java.util.Calendar.DAY_OF_YEAR)}-$hhmm"
            AppState.alarms.forEach { al ->
                if (al.enabled && al.time == hhmm && al.firedKey != dayKey) {
                    al.firedKey = dayKey; changed = true
                    AppState.ringingSource = "alarm"; AppState.ringingLabel = al.name
                    LogStore.appendTruth(this, "alarm", "${al.name} went off (${al.time}).", "alarm_fired")
                }
            }
            if (changed) { AppState.save(this); refreshFace(); if (activeTab == "tools") renderTab() }
            startForegroundTickLoop()
        }, 1000)
    }

    // ---------- Settings ----------

    private fun buildSettingsTab(): View {
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }

        val trackerRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        trackerRow.addView(Switch(this).apply {
            isChecked = AppState.appTracker
            setOnCheckedChangeListener { _, checked ->
                AppState.appTracker = checked
                LogStore.appendTruth(this@MainActivity, "setting", "Setting changed: App Tracker turned ${if (checked) "ON" else "OFF"}.", if (checked) "setting_on" else "setting_off")
                AppState.save(this@MainActivity)
            }
        })
        trackerRow.addView(TextView(this).apply { text = "App Tracker — logs setting changes while on" })
        col.addView(trackerRow)

        col.addView(sectionTitle("Widget clock style"))
        col.addView(choiceRow(listOf("analog", "digital"), AppState.widgetClockStyle) { AppState.widgetClockStyle = it; AppState.save(this); refreshFace(); renderTab() })

        col.addView(sectionTitle("Widget theme"))
        col.addView(choiceRow(listOf("light", "dark", "colorpop"), AppState.widgetTheme) { AppState.widgetTheme = it; AppState.save(this); refreshFace(); renderTab() })

        col.addView(sectionTitle("App theme"))
        col.addView(choiceRow(listOf("light", "dark", "colorpop"), AppState.appTheme) { AppState.appTheme = it; AppState.save(this); renderTab() })

        col.addView(sectionTitle("Diary update frequency"))
        col.addView(choiceRow(listOf("15", "30", "60"), AppState.updateIntervalMinutes.toString()) {
            AppState.updateIntervalMinutes = it.toInt(); AppState.save(this); TickWorker.ensureScheduled(this, AppState.updateIntervalMinutes.toLong()); renderTab()
        })

        col.addView(sectionTitle("Alarm & timer sound"))
        col.addView(TextView(this).apply { text = if (AppState.alarmSoundUri != null) "Custom sound selected" else "Using default (no file chosen)" })
        col.addView(Button(this).apply {
            text = "Choose sound file"
            setOnClickListener {
                val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply { addCategory(Intent.CATEGORY_OPENABLE); type = "audio/*" }
                soundPickerLauncher.launch(intent)
            }
        })

        col.addView(sectionTitle("Tracked apps"))
        AppState.watchlist.forEach { app ->
            val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            row.addView(Switch(this).apply {
                isChecked = app.watched
                setOnCheckedChangeListener { _, checked ->
                    app.watched = checked
                    if (AppState.appTracker) LogStore.appendTruth(this@MainActivity, "setting", "Setting changed: ${app.name} tracking turned ${if (checked) "ON" else "OFF"}.", if (checked) "setting_on" else "setting_off")
                    AppState.save(this@MainActivity)
                }
            })
            row.addView(TextView(this).apply { text = "${app.name} (${app.minutes}m)" })
            col.addView(row)
        }

        return col
    }

    private fun choiceRow(options: List<String>, current: String, onPick: (String) -> Unit): View {
        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        options.forEach { opt ->
            row.addView(Button(this).apply {
                text = opt
                alpha = if (opt == current) 1f else 0.5f
                setOnClickListener { onPick(opt) }
            })
        }
        return row
    }

    // ---------- Log ----------

    private fun buildLogTab(): View {
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }

        val filterRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        filterRow.addView(CheckBox(this).apply { text = "Core"; isChecked = LogFilters.log; setOnCheckedChangeListener { _, c -> LogFilters.log = c; AppState.save(this@MainActivity); renderTab() } })
        filterRow.addView(CheckBox(this).apply { text = "Flair"; isChecked = LogFilters.personality; setOnCheckedChangeListener { _, c -> LogFilters.personality = c; AppState.save(this@MainActivity); renderTab() } })
        filterRow.addView(CheckBox(this).apply { text = "Tech"; isChecked = LogFilters.tech; setOnCheckedChangeListener { _, c -> LogFilters.tech = c; AppState.save(this@MainActivity); renderTab() } })
        col.addView(filterRow)

        val fmt = SimpleDateFormat("MMM d, h:mm a", Locale.getDefault())
        LogStore.filtered(this).reversed().forEach { e ->
            col.addView(TextView(this).apply {
                text = "${fmt.format(Date(e.atMillis))} — ${e.category}-${e.layer}\n${e.text}"
                setPadding(0, 12, 0, 12)
            })
        }

        col.addView(sectionTitle("Copy for a bug report — nothing is sent automatically"))
        val copyRow = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        listOf("All" to null, "Core" to "log", "Flair" to "personality", "Tech" to "tech").forEach { (label, layer) ->
            copyRow.addView(Button(this).apply {
                text = "Copy $label"
                setOnClickListener {
                    val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                    clipboard.setPrimaryClip(ClipData.newPlainText("Halfwake log", LogStore.formatForCopy(this@MainActivity, layer)))
                    Toast.makeText(this@MainActivity, "Copied", Toast.LENGTH_SHORT).show()
                }
            })
        }
        col.addView(copyRow)
        return col
    }
}
