package com.halfwake.pocket

import android.content.Context
import android.graphics.*
import android.util.AttributeSet
import android.view.MotionEvent
import android.view.View
import java.util.Calendar
import kotlin.math.*

/**
 * Draws the circle: the logo-mark fill (mood-tinted, half solid/half
 * faded), the face (brows/eyes/mouth/decor per mood), and the clock
 * (analog hands or digital readout, real device time only).
 *
 * This view can run two ways:
 *  - Live, inside the app: continuous invalidate() loop, touch-reactive
 *    pupils, blinking. Only possible here — never in a widget.
 *  - Once, for the widget: a single draw() call captured to a Bitmap by
 *    the widget provider at tick time. No animation, just a snapshot.
 */
class FaceClockView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null
) : View(context, attrs) {

    var moodKey: String = "content"
    var reasonText: String = ""
    var live: Boolean = true // false when used purely for widget bitmap capture

    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private var pointerX = -1f
    private var pointerY = -1f
    private var lastBlinkAt = 0L
    private var blinkUntil = 0L

    override fun onTouchEvent(event: MotionEvent): Boolean {
        pointerX = event.x; pointerY = event.y
        if (live) invalidate()
        return true
    }

    fun tick() {
        if (!live) return
        val now = System.currentTimeMillis()
        if (now > blinkUntil + 2400 + (Math.random() * 3200).toLong() && now > lastBlinkAt + 500) {
            blinkUntil = now + 140
            lastBlinkAt = now
        }
        invalidate()
        postDelayed({ tick() }, 50)
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val w = width.toFloat(); val h = height.toFloat()
        val cx = w / 2f; val cy = h / 2f
        val r = min(w, h) / 2f - 4f

        val theme = Themes.of(AppState.widgetTheme)
        val moodColor = Moods.colorOf(moodKey)
        val ink = theme.fg

        // paper backing
        paint.style = Paint.Style.FILL; paint.color = theme.bg
        canvas.drawCircle(cx, cy, r, paint)

        // logo-mark fill: right half solid, left half faded
        canvas.save()
        val clipPath = Path().apply { addCircle(cx, cy, r, Path.Direction.CW) }
        canvas.clipPath(clipPath)
        paint.color = moodColor
        canvas.drawArc(cx - r, cy - r, cx + r, cy + r, -90f, 180f, true, paint)
        paint.color = withAlpha(moodColor, 0.3f)
        canvas.drawArc(cx - r, cy - r, cx + r, cy + r, 90f, 180f, true, paint)
        canvas.restore()

        // outer ring
        paint.style = Paint.Style.STROKE; paint.strokeWidth = 3f; paint.color = moodColor
        canvas.drawCircle(cx, cy, r, paint)

        val face = Faces.of(moodKey)
        val blinking = live && System.currentTimeMillis() < blinkUntil
        drawFace(canvas, cx, cy, r, ink, theme.bg, face, blinking)
        drawClockOrCountdown(canvas, cx, cy, r, ink, theme.bg)
    }

    private fun drawFace(canvas: Canvas, cx: Float, cy: Float, r: Float, ink: Int, bg: Int, face: FaceParams, blinking: Boolean) {
        val eyeY = cy - r * 0.08f
        val eyeDX = r * 0.25f
        val eyeR = r * 0.09f
        val openness = if (blinking) 0.06f else face.eyeOpen

        for (side in intArrayOf(-1, 1)) {
            val ex = cx + side * eyeDX

            // eyebrow
            canvas.save()
            canvas.translate(ex, eyeY - r * 0.16f)
            canvas.rotate(side * -face.brow * 34f)
            paint.style = Paint.Style.STROKE; paint.strokeWidth = 3f; paint.color = ink; paint.strokeCap = Paint.Cap.ROUND
            canvas.drawLine(-r * 0.09f, 0f, r * 0.09f, 0f, paint)
            canvas.restore()

            if (face.xEyes) {
                paint.color = ink; paint.strokeWidth = 3f
                canvas.drawLine(ex - eyeR, eyeY - eyeR, ex + eyeR, eyeY + eyeR, paint)
                canvas.drawLine(ex + eyeR, eyeY - eyeR, ex - eyeR, eyeY + eyeR, paint)
                continue
            }

            canvas.save()
            canvas.translate(ex, eyeY)
            canvas.scale(1f, max(0.06f, openness))
            paint.style = Paint.Style.FILL; paint.color = bg
            canvas.drawCircle(0f, 0f, eyeR, paint)
            paint.style = Paint.Style.STROKE; paint.strokeWidth = 1.5f; paint.color = ink
            canvas.drawCircle(0f, 0f, eyeR, paint)
            canvas.restore()

            if (openness > 0.15f) {
                val px = if (pointerX >= 0) pointerX else cx
                val py = if (pointerY >= 0) pointerY else cy - r * 0.2f
                val dx = px - ex; val dy = py - eyeY
                val dist = min(eyeR * 0.35f, hypot(dx, dy) / 16f)
                val ang = atan2(dy, dx)
                paint.style = Paint.Style.FILL; paint.color = ink
                canvas.drawCircle(ex + cos(ang) * dist, eyeY + sin(ang) * dist * openness, eyeR * 0.35f, paint)
            }
        }

        // mouth
        val mx = cx; val my = cy + r * 0.26f
        paint.style = Paint.Style.STROKE; paint.strokeWidth = r * 0.03f; paint.color = ink; paint.strokeCap = Paint.Cap.ROUND
        val path = Path()
        val mw = r * 0.18f
        when (face.mouth) {
            "bigsmile" -> {
                paint.style = Paint.Style.FILL
                path.moveTo(mx - mw, my - r*0.02f)
                path.quadTo(mx, my + r*0.16f, mx + mw, my - r*0.02f)
                path.quadTo(mx, my + r*0.07f, mx - mw, my - r*0.02f)
                canvas.drawPath(path, paint)
            }
            "smile" -> { path.moveTo(mx-mw, my); path.quadTo(mx, my+r*0.11f, mx+mw, my); canvas.drawPath(path, paint) }
            "gentlesmile" -> { path.moveTo(mx-mw, my); path.quadTo(mx, my+r*0.08f, mx+mw, my); canvas.drawPath(path, paint) }
            "frown" -> { path.moveTo(mx-mw, my+r*0.07f); path.quadTo(mx, my-r*0.07f, mx+mw, my+r*0.07f); canvas.drawPath(path, paint) }
            "flatfrown" -> { path.moveTo(mx-mw*0.9f, my+r*0.01f); path.quadTo(mx, my-r*0.02f, mx+mw*0.9f, my+r*0.01f); canvas.drawPath(path, paint) }
            "o" -> { paint.style = Paint.Style.STROKE; canvas.drawOval(mx-r*0.06f, my-r*0.09f, mx+r*0.06f, my+r*0.09f, paint) }
            "wavy" -> {
                path.moveTo(mx-mw, my); path.quadTo(mx-mw*0.5f, my-r*0.07f, mx, my)
                path.quadTo(mx+mw*0.5f, my+r*0.07f, mx+mw, my); canvas.drawPath(path, paint)
            }
            "flatsmall" -> canvas.drawLine(mx-mw*0.6f, my, mx+mw*0.6f, my, paint)
            "smirk" -> { path.moveTo(mx-mw, my+r*0.015f); path.quadTo(mx+r*0.02f, my+r*0.06f, mx+mw*1.1f, my-r*0.03f); canvas.drawPath(path, paint) }
            "sour" -> {
                path.moveTo(mx-mw, my+r*0.03f)
                path.lineTo(mx-mw*0.5f, my-r*0.03f)
                path.lineTo(mx, my+r*0.02f)
                path.lineTo(mx+mw*0.5f, my-r*0.03f)
                path.lineTo(mx+mw, my+r*0.03f)
                canvas.drawPath(path, paint)
            }
            else -> canvas.drawLine(mx-mw*0.8f, my, mx+mw*0.8f, my, paint)
        }
    }

    private fun drawClockOrCountdown(canvas: Canvas, cx: Float, cy: Float, r: Float, ink: Int, bg: Int) {
        val now = Calendar.getInstance()

        // numerals
        paint.textAlign = Paint.Align.CENTER
        paint.textSize = r * 0.11f
        val numRadius = r * 0.85f
        for (i in 1..12) {
            val a = (i / 12.0 * 2 * PI).toFloat()
            val nx = cx + sin(a) * numRadius
            val ny = cy - cos(a) * numRadius + r * 0.04f
            haloText(canvas, i.toString(), nx, ny, ink, bg)
        }

        if (AppState.widgetClockStyle == "analog") {
            val hrs = now.get(Calendar.HOUR) ; val mins = now.get(Calendar.MINUTE); val secs = now.get(Calendar.SECOND)
            val hourAngle = ((hrs + mins / 60.0) / 12.0 * 2 * PI).toFloat()
            val minAngle = ((mins + secs / 60.0) / 60.0 * 2 * PI).toFloat()
            drawHand(canvas, cx, cy, hourAngle, r * 0.95f, r * 0.045f, ink, bg)
            drawHand(canvas, cx, cy, minAngle, r * 0.75f, r * 0.028f, ink, bg)
        } else {
            val h = now.get(Calendar.HOUR); val displayH = if (h == 0) 12 else h
            val m = now.get(Calendar.MINUTE)
            val ampm = if (now.get(Calendar.AM_PM) == Calendar.AM) "AM" else "PM"
            val timeStr = String.format("%d:%02d %s", displayH, m, ampm)
            paint.textSize = r * 0.16f
            haloText(canvas, timeStr, cx, cy - r * 0.55f, ink, bg)
        }
    }

    private fun drawHand(canvas: Canvas, cx: Float, cy: Float, angle: Float, length: Float, width: Float, color: Int, halo: Int) {
        val x2 = cx + sin(angle) * length; val y2 = cy - cos(angle) * length
        paint.style = Paint.Style.STROKE; paint.strokeCap = Paint.Cap.ROUND
        paint.strokeWidth = width + 4f; paint.color = withAlpha(halo, 0.85f)
        canvas.drawLine(cx, cy, x2, y2, paint)
        paint.strokeWidth = width; paint.color = color
        canvas.drawLine(cx, cy, x2, y2, paint)
    }

    private fun haloText(canvas: Canvas, text: String, x: Float, y: Float, color: Int, halo: Int) {
        paint.style = Paint.Style.STROKE; paint.strokeWidth = 3f; paint.color = withAlpha(halo, 0.85f)
        canvas.drawText(text, x, y, paint)
        paint.style = Paint.Style.FILL; paint.color = color
        canvas.drawText(text, x, y, paint)
    }

    private fun withAlpha(color: Int, alpha: Float): Int =
        Color.argb((alpha * 255).toInt(), Color.red(color), Color.green(color), Color.blue(color))
}
