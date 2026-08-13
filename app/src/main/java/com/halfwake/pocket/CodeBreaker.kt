package com.halfwake.pocket

object GameDialogue {
    private val pools: Map<String, List<String>> = mapOf(
        "intro" to listOf("Pick a 4-digit code and I'll try to guess it. No wait — you guess mine. Go on."),
        "close_guess" to listOf(
            "Careful. You're closer than you think.", "Mm. That one stung a little.",
            "...Getting warm. I said nothing.", "Don't get cocky. You're not there yet.",
            "That one landed closer than I'd like to admit."
        ),
        "ok_guess" to listOf("A start, I suppose.", "Some of that landed.", "Not nothing. Not much, either.", "You're circling it, at least."),
        "bad_guess" to listOf(
            "Not even warm.", "I could've picked that in my sleep. Try again.",
            "Confidently wrong. I respect it.", "That guess owes me an apology.", "Nothing. Absolutely nothing."
        ),
        "near_win" to listOf(
            "Wait — no. Don't.", "...Lucky guess.", "You wouldn't.", "Okay. Okay. Stay calm.",
            "I did NOT see that coming. I mean — obviously I did."
        ),
        "player_won" to listOf(
            "Fine. FINE. You got it.", "Rewind the clock and try again? I want a rematch.",
            "...Well played. I still want a rematch.", "You got lucky. Say it. Say you got lucky."
        ),
        "clock_won" to listOf(
            "Predictable. Better luck against a real opponent.", "Six tries and nothing. The code was safe with me.",
            "And that's how it's done.", "Not bad. Not good. But not bad."
        ),
    )
    fun line(pool: String): String = pools[pool]?.random() ?: ""
}

data class GuessResult(val exact: Int, val partial: Int)

object CodeBreakerLogic {
    fun newSecret(): List<Int> = List(4) { (0..9).random() }

    fun score(guess: List<Int>, secret: List<Int>): GuessResult {
        var exact = 0
        val secretLeft = mutableListOf<Int>()
        val guessLeft = mutableListOf<Int>()
        for (i in 0..3) {
            if (guess[i] == secret[i]) exact++
            else { secretLeft.add(secret[i]); guessLeft.add(guess[i]) }
        }
        var partial = 0
        val pool = secretLeft.toMutableList()
        for (d in guessLeft) {
            val idx = pool.indexOf(d)
            if (idx > -1) { partial++; pool.removeAt(idx) }
        }
        return GuessResult(exact, partial)
    }
}
