"""ST7789 display rendering for PiWeather.

Drives a Waveshare 1.54" 240×240 ST7789 SPI LCD via Pimoroni's st7789 library.
All rendering is done into a PIL Image which is then pushed to the display.

Layout (240×240):
  y  0–28   Label row: "TODAY" / "TOMORROW" (left) + time HH:MM (right)
  y 30–130  Weather icon 100×100, centred
  y 135–155 Weather description (centred)
  y 160–190 Hi / Low temperatures (centred)
  y 195–220 Full date: "Monday 16 March 2026" (centred)
  y 225–235 Day indicator: two dots (today = left active, tomorrow = right active)
"""

import logging
import os
from datetime import datetime
from typing import Any, Optional

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Display dimensions                                                   #
# ------------------------------------------------------------------ #

WIDTH = 240
HEIGHT = 240

# ------------------------------------------------------------------ #
# Colours                                                              #
# ------------------------------------------------------------------ #

BG_COLOR     = (8, 12, 24)        # dark navy background
TEXT_COLOR   = (255, 255, 255)    # white
DIM_COLOR    = (100, 110, 130)    # dimmed / inactive
HIGH_COLOR   = (255, 160, 0)      # warm orange — high temperature
LOW_COLOR    = (80, 160, 255)     # cool blue   — low temperature
ACCENT_COLOR = (0, 200, 255)      # cyan accent
DOT_ACTIVE   = (255, 255, 255)    # active day dot
DOT_INACTIVE = (50, 55, 70)       # inactive day dot

# ------------------------------------------------------------------ #
# Font helpers                                                         #
# ------------------------------------------------------------------ #

_FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a TrueType font at *size* px.

    Search order:
    1. Bundled font in src/fonts/ (DejaVuSans / DejaVuSans-Bold)
    2. Common system font locations (DejaVu → Liberation → Arial → FreeSans)
    3. PIL built-in bitmap fallback (no size control)
    """
    candidates = [
        os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
        # Linux / Raspberry Pi OS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # Windows
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        # macOS
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    logger.warning("No TrueType font found (size=%d bold=%s) — using PIL default", size, bold)
    return ImageFont.load_default()


# ------------------------------------------------------------------ #
# Icon helpers                                                         #
# ------------------------------------------------------------------ #

_ICON_DIR = os.path.join(os.path.dirname(__file__), "icons")
_ICON_CACHE: dict[str, Image.Image] = {}


def _load_icon(name: str, size: int = 100) -> Optional[Image.Image]:
    """Load and cache a weather icon PNG, resized to *size*×*size* px.

    Args:
        name: Icon base name without extension, e.g. ``"01d"``.
        size: Target size in pixels (square).

    Returns:
        RGBA PIL Image, or None if the file is not found.
    """
    cache_key = f"{name}@{size}"
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    path = os.path.join(_ICON_DIR, f"{name}.png")
    if not os.path.isfile(path):
        logger.warning("Weather icon not found: %s", path)
        return None

    try:
        img = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        _ICON_CACHE[cache_key] = img
        return img
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load icon %s: %s", path, exc)
        return None


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    """Return pixel width of *text* rendered with *font*."""
    try:
        bb = draw.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0]
    except AttributeError:
        w, _ = draw.textsize(text, font=font)  # type: ignore[attr-defined]
        return w


def _draw_centred(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font: ImageFont.FreeTypeFont,
    color: tuple[int, int, int],
) -> None:
    """Draw *text* horizontally centred on the display at *y*."""
    w = _text_width(draw, text, font)
    draw.text(((WIDTH - w) // 2, y), text, font=font, fill=color)


# ------------------------------------------------------------------ #
# Main rendering functions                                             #
# ------------------------------------------------------------------ #

def draw_weather(
    image: Image.Image,
    day_data: dict[str, Any],
    day: int,
    now: datetime,
) -> None:
    """Render a full weather screen into *image* (must be 240×240 RGB).

    Args:
        image: PIL Image to draw onto (modified in place).
        day_data: Weather dict for the day (``today`` or ``tomorrow`` key).
        day: 0 = today, 1 = tomorrow.
        now: Current local datetime (for time display on today's screen).
    """
    draw = ImageDraw.Draw(image)
    image.paste(BG_COLOR, [0, 0, WIDTH, HEIGHT])

    font_label   = _font(18, bold=True)
    font_time    = _font(18)
    font_desc    = _font(15)
    font_temp    = _font(28, bold=True)
    font_date    = _font(15)

    # ---- Row 1: label + time ----------------------------------------
    label = "TODAY" if day == 0 else "TOMORROW"
    draw.text((8, 6), label, font=font_label, fill=ACCENT_COLOR)

    if day == 0:
        time_str = now.strftime("%H:%M")
        tw = _text_width(draw, time_str, font_time)
        draw.text((WIDTH - tw - 8, 6), time_str, font=font_time, fill=DIM_COLOR)

    # ---- Separator line ---------------------------------------------
    draw.line([(0, 28), (WIDTH, 28)], fill=(30, 35, 55), width=1)

    # ---- Weather icon (100×100, centred) ----------------------------
    icon_name = day_data.get("icon", "01d")
    icon_img = _load_icon(icon_name, size=100)
    icon_y = 32
    if icon_img is not None:
        icon_x = (WIDTH - 100) // 2
        # Composite RGBA icon onto dark background
        bg_patch = Image.new("RGBA", (100, 100), BG_COLOR + (255,))
        combined = Image.alpha_composite(bg_patch, icon_img)
        image.paste(combined.convert("RGB"), (icon_x, icon_y))
    else:
        # Fallback: draw a placeholder circle
        draw.ellipse(
            [(WIDTH // 2 - 45, icon_y + 5), (WIDTH // 2 + 45, icon_y + 95)],
            outline=DIM_COLOR, width=2,
        )

    # ---- Description ------------------------------------------------
    desc = day_data.get("description", "")
    _draw_centred(draw, desc, 138, font_desc, DIM_COLOR)

    # ---- Hi / Low ---------------------------------------------------
    high = day_data.get("high", 0)
    low = day_data.get("low", 0)
    unit_sym = day_data.get("unit_symbol", "°C")
    hi_str = f"▲ {high:.0f}{unit_sym}"
    lo_str = f"▼ {low:.0f}{unit_sym}"
    hi_w = _text_width(draw, hi_str, font_temp)
    lo_w = _text_width(draw, lo_str, font_temp)
    gap = 18
    total_w = hi_w + gap + lo_w
    left_x = (WIDTH - total_w) // 2
    draw.text((left_x, 160), hi_str, font=font_temp, fill=HIGH_COLOR)
    draw.text((left_x + hi_w + gap, 160), lo_str, font=font_temp, fill=LOW_COLOR)

    # ---- Date -------------------------------------------------------
    date_str = day_data.get("date", "")
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            # %-d (Linux) / %#d (Windows) strips leading zero — use manual format instead
            date_label = f"{dt.strftime('%A')} {dt.day} {dt.strftime('%B %Y')}"
        except (ValueError, AttributeError):
            date_label = date_str
    else:
        date_label = now.strftime("%A %-d %B %Y") if day == 0 else ""
    _draw_centred(draw, date_label, 197, font_date, DIM_COLOR)

    # ---- Day indicator dots -----------------------------------------
    dot_r = 5
    dot_y = 230
    spacing = 22
    cx = WIDTH // 2
    # today dot (left)
    d0_color = DOT_ACTIVE if day == 0 else DOT_INACTIVE
    d1_color = DOT_ACTIVE if day == 1 else DOT_INACTIVE
    draw.ellipse(
        [(cx - spacing - dot_r, dot_y - dot_r), (cx - spacing + dot_r, dot_y + dot_r)],
        fill=d0_color,
    )
    draw.ellipse(
        [(cx + spacing - dot_r, dot_y - dot_r), (cx + spacing + dot_r, dot_y + dot_r)],
        fill=d1_color,
    )


def draw_error(image: Image.Image, message: str) -> None:
    """Render an error / loading screen into *image*.

    Shown on boot while waiting for the first weather fetch.
    """
    draw = ImageDraw.Draw(image)
    image.paste(BG_COLOR, [0, 0, WIDTH, HEIGHT])

    font_title = _font(18, bold=True)
    font_msg   = _font(14)

    _draw_centred(draw, "PiWeather", 80, font_title, ACCENT_COLOR)

    # Wrap message into ~22-char lines
    words = message.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 > 22:
            if current:
                lines.append(current)
            current = word
        else:
            current = (current + " " + word).strip()
    if current:
        lines.append(current)

    for i, line in enumerate(lines[:4]):
        _draw_centred(draw, line, 120 + i * 22, font_msg, DIM_COLOR)


# ------------------------------------------------------------------ #
# ST7789 SPI driver                                                    #
# ------------------------------------------------------------------ #

class ST7789:
    """Wrapper around the Pimoroni st7789 library for the Waveshare 1.54" 240×240 LCD.

    GPIO pin mapping (BCM numbering):
      DC  = GPIO 25  (physical pin 22)
      RST = GPIO 27  (physical pin 13)
      BL  = GPIO 24  (physical pin 18) — PWM backlight
      CS  = GPIO 8   (physical pin 24, CE0)
      MOSI= GPIO 10  (physical pin 19)
      SCLK= GPIO 11  (physical pin 23)
    """

    DC_PIN    = 25
    RST_PIN   = 27
    BL_PIN    = 24
    CS_PIN    = 8   # BCM GPIO pin for CE0 (physical pin 24)
    SPI_PORT  = 0
    SPI_CS    = 0   # spidev chip-select index: 0 = CE0 → /dev/spidev0.0
    SPI_SPEED = 16_000_000

    def __init__(self, brightness: int = 100) -> None:
        """Initialise display via the st7789 library."""
        import ST7789 as _ST7789
        import RPi.GPIO as GPIO

        self._disp = _ST7789.ST7789(
            port=self.SPI_PORT,
            cs=self.SPI_CS,
            dc=self.DC_PIN,
            rst=self.RST_PIN,
            backlight=self.BL_PIN,
            rotation=0,
            spi_speed_hz=self.SPI_SPEED,
            width=WIDTH,
            height=HEIGHT,
        )

        self._GPIO = GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.BL_PIN, GPIO.OUT)
        self._pwm = GPIO.PWM(self.BL_PIN, 1000)
        self._pwm.start(brightness / 255 * 100)

        logger.info("ST7789 display initialised (brightness=%d)", brightness)

    def show(self, image: Image.Image) -> None:
        """Push a PIL Image to the display."""
        self._disp.display(image)

    def set_brightness(self, brightness: int) -> None:
        """Set backlight brightness 0–255."""
        self._pwm.ChangeDutyCycle(max(0, min(255, brightness)) / 255 * 100)

    def close(self) -> None:
        """Release GPIO resources."""
        try:
            self._pwm.stop()
            self._GPIO.cleanup()
        except Exception:  # noqa: BLE001
            pass
        logger.info("ST7789 display closed")
