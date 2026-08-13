# Halfwake — Pocket (Android)

The base app, plus the addon-loader mechanism and a proof-of-concept NPC
flair addon. Widget shows a real snapshot of the clock/face; opening the
app gives you the full live version — tabs, tools, game, settings, log.

## Important: this has not been compiled

Built without an Android SDK or network access in this environment, so
it's syntax-reviewed by hand (brace/paren balance checked, every R.id
reference cross-checked against its XML declaration) but never actually
run through Gradle. Treat it as a strong, structurally-verified draft —
first real build will likely surface a handful of small fixes, which is
normal, not a sign the design is wrong.

## What's real in this build

- **Widget**: renders a genuine static bitmap snapshot of the face/clock
  each tick (RemoteViews can't host a live animated view — this is a real
  platform limit, not a shortcut). Tapping it opens the app.
- **App**: live, touch-reactive face (blinking, pupils tracking touch),
  real analog/digital clock, five tabs — Home, Play (Code Breaker +
  Calculator), Tools (stopwatch, up to 5 named timers with +/-/reset,
  5 named alarms), Settings (App Tracker, both themes, clock style,
  update interval, alarm sound picker, per-app tracking), Log (three
  filterable layers — Core/Flair/Tech, default 2/3 with Tech off — plus
  copy-to-clipboard for bug reports, fully optional, nothing sent
  automatically).
- **Addon loader**: scans `Android/data/com.halfwake.pocket/files/addons/`
  — no permission needed, any file manager can browse there. Each addon
  is a folder with an `addon.json` manifest. Removing a folder makes the
  app fall back to honest-only behavior automatically.
- **NPC bridge**: the base app always has this hook. If an addon declares
  `"provides": ["personality_dialogue"]` and supplies
  `personality-lines.json`, its lines override the display — the honest
  diary line still gets written to the Log regardless, tagged `-log`.
  No addon installed = pure honest behavior, no code changes needed.
- **Sample NPC addon**: `mods/npc-flair-sample/` at repo root (not part
  of the Gradle project — this is what gets manually copied to the
  device's addons folder for testing). Proof-of-concept only — simple
  mood-keyed line pools, not the full memory-tier/token system from the
  addon spec. That's its own dedicated build, later.

## Known gap — flagged honestly, not glossed over

Timers and alarms only actually count down / check their fire time while
the app is open in the foreground (a `Handler` loop drives this). Real
background firing — alarm goes off even with the app fully closed —
needs `AlarmManager`-scheduled exact wakeups per timer/alarm, which is
real, separate work not included in this pass.

## How to test the addon mechanism

1. Build and install the app normally first, confirm it works with zero
   addons present.
2. Connect the phone to a computer (or use a file manager app on-device),
   navigate to `Android/data/com.halfwake.pocket/files/addons/`.
3. Copy the `npc-flair-sample` folder from this repo's `mods/` directory
   into that addons folder.
4. Relaunch the app — the Home tab's line should now come from the addon
   instead of the core diary pool. Check the Log tab with Flair enabled —
   you'll see `-personality` entries alongside the `-log` ones.
5. Delete the addon folder from the device, relaunch — should fall back
   to pure honest lines with zero errors. That fallback working cleanly
   *is* the actual test.

## How to run it

1. Open in Android Studio, let Gradle sync.
2. Run on a device/emulator, Android 10 (API 29) or later.
3. Grant Usage Access when prompted (Settings → Apps → Special access →
   Usage access — manual grant required, no runtime dialog for this one).
4. Grant notification permission if asked (Android 13+).

## Privacy, unchanged

No `INTERNET` permission anywhere in the manifest. Everything — diary,
log, addon content — stays on-device. Copying log text for a bug report
is the one explicitly manual, optional exception, and it never leaves
the device until you personally paste it somewhere.
