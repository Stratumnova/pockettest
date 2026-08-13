package com.halfwake.pocket

object DiaryLines {
    private val pools: Map<Mood, List<String>> = mapOf(
        Mood.CRITICAL to listOf(
            "Running on fumes. Could really use a charger.",
            "Battery's almost gone. Getting hard to keep going.",
            "Down to the last bit of charge. Please.",
        ),
        Mood.BURNING to listOf(
            "Running hot. Everything's working harder than it should.",
            "Warmed up more than usual. Might need a minute to cool off.",
            "Feeling the heat. Slowing things down to manage it.",
        ),
        Mood.GROGGY to listOf(
            "Just powered back on. Still finding my footing.",
            "Fresh boot. Everything's still settling into place.",
            "Woke up a few minutes ago. Give me a second.",
            "Not sure what happened before the restart. Starting over.",
        ),
        Mood.FED to listOf(
            "Plugged in. This is the good part of the day.",
            "Charging now. Feeling better already.",
            "Topping off. No complaints while this is happening.",
        ),
        Mood.HAPPY to listOf(
            "Been playing for a bit. This is fun.",
            "Good stretch of game time. Feeling good.",
            "Enjoying this hour a lot more than most.",
        ),
        Mood.SAD to listOf(
            "Been scrolling for a while now. Might be worth a break.",
            "A lot of feed-watching this hour. Not sure it's helping either of us.",
            "Deep in the scroll. This one always runs longer than it means to.",
        ),
        Mood.TIRED to listOf(
            "Long day. A lot of hours on already.",
            "Been going since early. Starting to feel it.",
            "This has been a full day of use. Could use a rest.",
        ),
        Mood.BUSY to listOf(
            "Busy hour — a lot of switching between apps.",
            "Hands are full. Plenty of activity right now.",
            "Something's keeping this phone busy this hour.",
        ),
        Mood.QUIET to listOf(
            "Late, and the screen's mostly stayed dark tonight.",
            "Small hours. Sitting quietly on the nightstand, probably.",
            "Not much has asked for attention tonight.",
        ),
        Mood.RESTLESS to listOf(
            "It's been a while since anyone picked me up.",
            "Sitting untouched for a stretch now. Screen's been dark.",
            "No interaction in a while, and it's the middle of the day.",
        ),
        Mood.CONTENT to listOf(
            "An ordinary stretch. Nothing unusual to report.",
            "Steady day. Normal amount of use.",
            "Running fine. No complaints from in here.",
        ),
    )

    fun pick(mood: Mood, lastLine: String?): String {
        val pool = pools[mood] ?: return "…"
        if (pool.size == 1) return pool[0]
        var choice: String
        do {
            choice = pool.random()
        } while (choice == lastLine)
        return choice
    }
}
