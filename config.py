"""
config.py — Centralt konfigurationsmodul for SelfieBoks.
Alle konstanter og tunable parametre samles her, så de er nemme at finde og justere.
"""

from pathlib import Path

# ─── Skærm ───────────────────────────────────────────────────────────────────
# Defaults — overskrives dynamisk i main.py baseret på faktisk skærmstørrelse
SCREEN_WIDTH  = 1920
SCREEN_HEIGHT = 1080

# ─── Kamera (picamera2 / Arducam IMX519) ─────────────────────────────────────
PREVIEW_WIDTH  = 1920
PREVIEW_HEIGHT = 1080  # 1920x1080 @ 60fps bruger 3840x2160 sensor-crop (bred FOV)
PREVIEW_FPS    = 60

# Stillbilledopløsning — 16:9 matcher preview stream (ingen zoom-forskel)
# IMX519 understøtter 4K 16:9 native binning
STILL_WIDTH  = 3840
STILL_HEIGHT = 2160

# ─── Timing (millisekunder) ───────────────────────────────────────────────────
# Nedtælling fra knap-tryk til klik
COUNTDOWN_DURATION_MS = 3000

# Auto-retur fra review-side hvis bruger ikke vælger gem/slet
AUTO_RETURN_MS       = 15_000
# Opdateringsinterval for progress-bar (finere interval = glattere animation)
AUTO_RETURN_TICK_MS  = 50

# ─── Animationer ──────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"

ANIMATION_FPS = 30

CAPTURE_BUTTON_FRAMES  = ASSETS_DIR / "capture_button_frames"
COUNTDOWN_FRAMES       = ASSETS_DIR / "countdown_numbers_frames"
COUNTDOWN_ANIM_FRAMES  = ASSETS_DIR / "countdown_anim_frames"
DELETE_BUTTON_FRAMES   = ASSETS_DIR / "delete_button_frames"
SAVE_BUTTON_FRAMES     = ASSETS_DIR / "save_button_frames"
HEART_FRAMES           = ASSETS_DIR / "heart_frames"

CAPTURE_BUTTON_SIZE = 400   # px (kvadratisk)
REVIEW_BUTTON_SIZE  = 200   # px (kvadratisk, gem/slet knapper)

# ─── Fil-lagring ──────────────────────────────────────────────────────────────
PHOTOS_DIR = Path.home() / "Pictures" / "SelfieBoks"

# ─── Dropbox ─────────────────────────────────────────────────────────────────
# Sæt til dit Dropbox-apptoken for at aktivere upload, eller behold None.
DROPBOX_ACCESS_TOKEN: str | None = None

# ─── Bluetooth (ESP32) ───────────────────────────────────────────────────────
BLE_DEVICE_NAME             = "ESP32"
BLE_SERVICE_UUID            = "19b10000-e8f2-537e-4f6c-d104768a1214"
BLE_LED_CHARACTERISTIC_UUID = "19b10002-e8f2-537e-4f6c-d104768a1214"
BLE_RECONNECT_BACKOFF_MIN   = 5    # sekunder
BLE_RECONNECT_BACKOFF_MAX   = 60   # sekunder
