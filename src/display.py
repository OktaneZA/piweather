"""ST7789 display rendering for PiWeather.

Drives a Waveshare 1.54" 240×240 ST7789 SPI LCD directly via spidev + RPi.GPIO.
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
    """Raw SPI driver for the Waveshare 1.54" 240×240 ST7789 LCD.

    Drives the display directly via spidev + RPi.GPIO — no Pimoroni library required.
    Uses the full Waveshare init sequence (PORCTRL, GCTRL, VCOMS, gamma, etc.) which
    is required to configure the LCD voltage / gamma circuits correctly.

    GPIO pin mapping (BCM numbering):
      DC  = GPIO 25  (physical pin 22)
      RST = GPIO 27  (physical pin 13)
      BL  = GPIO 18  (physical pin 12) — PWM backlight
      CS  = GPIO 8   (physical pin 24, CE0)  — managed by spidev CE0
      MOSI= GPIO 10  (physical pin 19)
      SCLK= GPIO 11  (physical pin 23)
    """

    DC_PIN    = 25
    RST_PIN   = 27
    BL_PIN    = 18   # GPIO 18, physical pin 12 (Waveshare standard wiring)
    SPI_PORT  = 0
    SPI_CS    = 0    # spidev chip-select index: 0 = CE0 → /dev/spidev0.0
    SPI_SPEED = 16_000_000

    # Maximum bytes per spi.writebytes2() call (kernel spidev default buffer = 4096)
    _CHUNK = 4096

    def __init__(self, brightness: int = 100) -> None:
        """Initialise display via direct spidev + RPi.GPIO."""
        import spidev
        import RPi.GPIO as GPIO

        self._GPIO = GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.DC_PIN, GPIO.OUT)
        GPIO.setup(self.RST_PIN, GPIO.OUT)
        GPIO.setup(self.BL_PIN, GPIO.OUT)

        self._spi = spidev.SpiDev()
        self._spi.open(self.SPI_PORT, self.SPI_CS)
        self._spi.max_speed_hz = self.SPI_SPEED
        self._spi.mode = 0

        # Backlight PWM
        self._pwm = GPIO.PWM(self.BL_PIN, 1000)
        self._pwm.start(max(0, min(255, brightness)) / 255 * 100)

        self._reset()
        self._init_display()
        logger.info("ST7789 display initialised (brightness=%d)", brightness)

    # ------------------------------------------------------------------ #
    # Low-level helpers                                                    #
    # ------------------------------------------------------------------ #

    def _cmd(self, cmd: int) -> None:
        """Send a command byte (DC=LOW)."""
        self._GPIO.output(self.DC_PIN, self._GPIO.LOW)
        self._spi.xfer2([cmd])

    def _data(self, data: bytes) -> None:
        """Send data bytes (DC=HIGH), chunked to stay within spidev buffer."""
        self._GPIO.output(self.DC_PIN, self._GPIO.HIGH)
        mv = memoryview(data)
        for offset in range(0, len(mv), self._CHUNK):
            self._spi.writebytes2(mv[offset: offset + self._CHUNK])

    def _reset(self) -> None:
        """Hardware reset pulse."""
        import time
        self._GPIO.output(self.RST_PIN, self._GPIO.HIGH)
        time.sleep(0.05)
        self._GPIO.output(self.RST_PIN, self._GPIO.LOW)
        time.sleep(0.05)
        self._GPIO.output(self.RST_PIN, self._GPIO.HIGH)
        time.sleep(0.15)

    def _init_display(self) -> None:
        """Full Waveshare ST7789 1.54" init sequence."""
        import time

        self._cmd(0x01)   # SW reset
        time.sleep(0.15)
        self._cmd(0x11)   # Sleep out
        time.sleep(0.12)

        self._cmd(0xB2)   # Porch control
        self._data(bytes([0x0C, 0x0C, 0x00, 0x33, 0x33]))

        self._cmd(0xB7)   # Gate control
        self._data(bytes([0x35]))

        self._cmd(0xBB)   # VCOMS setting
        self._data(bytes([0x19]))

        self._cmd(0xC0)   # LCM control
        self._data(bytes([0x2C]))

        self._cmd(0xC2)   # VDV and VRH command enable
        self._data(bytes([0x01]))

        self._cmd(0xC3)   # VRH set
        self._data(bytes([0x12]))

        self._cmd(0xC4)   # VDV set
        self._data(bytes([0x20]))

        self._cmd(0xC6)   # Frame rate control (60 Hz)
        self._data(bytes([0x0F]))

        self._cmd(0xD0)   # Power control 1
        self._data(bytes([0xA4, 0xA1]))

        self._cmd(0xE0)   # Positive voltage gamma
        self._data(bytes([0xD0, 0x04, 0x0D, 0x11, 0x13, 0x2B, 0x3F, 0x54,
                          0x4C, 0x18, 0x0D, 0x0B, 0x1F, 0x23]))

        self._cmd(0xE1)   # Negative voltage gamma
        self._data(bytes([0xD0, 0x04, 0x0C, 0x11, 0x13, 0x2C, 0x3F, 0x44,
                          0x51, 0x2F, 0x1F, 0x1F, 0x20, 0x23]))

        self._cmd(0x21)   # Inversion on (required for correct colours on this module)
        self._cmd(0x3A)   # Colour mode: 16-bit RGB565
        self._data(bytes([0x05]))
        self._cmd(0x36)   # MADCTL: normal orientation
        self._data(bytes([0x00]))

        self._cmd(0x2A)   # Column address (0–239)
        self._data(bytes([0x00, 0x00, 0x00, 0xEF]))
        self._cmd(0x2B)   # Row address (0–239)
        self._data(bytes([0x00, 0x00, 0x00, 0xEF]))

        self._cmd(0x29)   # Display on
        time.sleep(0.05)

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def show(self, image: Image.Image) -> None:
        """Push a 240×240 RGB PIL Image to the display."""
        # Reset the write window for every frame
        self._cmd(0x2A)
        self._data(bytes([0x00, 0x00, 0x00, 0xEF]))
        self._cmd(0x2B)
        self._data(bytes([0x00, 0x00, 0x00, 0xEF]))
        self._cmd(0x2C)   # Memory write

        # Convert RGB888 → RGB565 big-endian using numpy (~1 ms vs ~100 ms pure-Python)
        import numpy as np
        arr = np.frombuffer(image.tobytes(), dtype=np.uint8).reshape(HEIGHT, WIDTH, 3)
        r = arr[:, :, 0].astype(np.uint16)
        g = arr[:, :, 1].astype(np.uint16)
        b = arr[:, :, 2].astype(np.uint16)
        px565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        self._data(px565.astype(np.dtype(">u2")).tobytes())

    def set_brightness(self, brightness: int) -> None:
        """Set backlight brightness 0–255."""
        self._pwm.ChangeDutyCycle(max(0, min(255, brightness)) / 255 * 100)

    def close(self) -> None:
        """Release SPI and GPIO resources."""
        try:
            self._pwm.stop()
            self._spi.close()
            self._GPIO.cleanup()
        except Exception:  # noqa: BLE001
            pass
        logger.info("ST7789 display closed")
