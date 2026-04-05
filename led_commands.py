"""
led_commands.py -- Hjaelpefunktioner til at sende LED-kommandoer til ESP32.

BLE korer i en separat daemon-traad (se main.py).
_ble_loop saettes af main.py inden AppWindow oprettes.
fire() sender en coroutine til BLE-traaden paa en traad-sikker maade.
"""

import asyncio
import logging
from enum import Enum
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Saettes af main.py naar BLE event loop er klar
_ble_loop: Optional[asyncio.AbstractEventLoop] = None

# BLE tilgaengelig hvis bluetooth_manager kan importeres
BLUETOOTH_ENABLED = False
bluetooth_manager = None

try:
    from bluetooth_manager import bluetooth_manager as _bm  # type: ignore[import]
    bluetooth_manager = _bm
    BLUETOOTH_ENABLED = True
except Exception as exc:
    logger.warning(f"[LED] BLE ikke tilgaengeligt: {exc}")


class Effect(Enum):
    SOLID        = "solid"
    RAINBOW      = "rainbow"
    SINELON      = "sinelon"
    CONFETTI     = "confetti"
    TWINKLE      = "twinkle"
    THEATERCHASE = "theaterchase"
    COLORWIPE    = "colorwipe"
    COMET        = "comet"
    GLITTER      = "glitter"
    PULSE        = "pulse"
    METEOR       = "meteor"
    NOISE        = "noise"
    DUALWIPE     = "dualwipe"
    GRADIENT     = "gradient"
    OFF          = "off"

    def __str__(self) -> str:
        return self.value


def fire(coro) -> None:
    """
    Send en coroutine til BLE daemon-traaden paa en traad-sikker maade.
    Bruges fra Qt main thread (ingen await noedvendig).
    """
    if _ble_loop is None or _ble_loop.is_closed():
        return
    try:
        asyncio.run_coroutine_threadsafe(coro, _ble_loop)
    except Exception as exc:
        logger.debug(f"[LED] fire() fejlede: {exc}")


async def _send(command: str) -> None:
    if not BLUETOOTH_ENABLED or bluetooth_manager is None:
        return
    try:
        await bluetooth_manager.send_command(command)
    except Exception as exc:
        logger.error(f"[LED] Kommando fejlede '{command}': {exc}")


async def send_white_led_command(on: bool, white_bright: int = 255) -> None:
    bright = max(0, min(white_bright, 255))
    if on:
        # Send brightness samen med on-kommandoen
        await _send(f"WHITE=on;WHITE_BRIGHT={bright}")
    else:
        # Send KUN WHITE=off -- ingen WHITE_BRIGHT.
        # ESP32-firmware aktiverer det hvide LED hvis WHITE_BRIGHT=255 er med
        # i samme kommando, selv naar WHITE=off er sat.
        await _send("WHITE=off")


async def send_pixel_effect_command(
    effect: Optional[Effect] = None,
    rgb_bright: int = 255,
    solid_color: Optional[Tuple[int, int, int]] = None,
) -> None:
    parts: list[str] = []
    if effect is not None:
        parts.append(f"EFFECT={effect.value}")
    parts.append(f"RGB_BRIGHT={max(0, min(rgb_bright, 255))}")
    if solid_color is not None:
        r, g, b = (max(0, min(c, 255)) for c in solid_color)
        parts.append(f"COLOR={r},{g},{b}")
    if parts:
        await _send(";".join(parts))


async def send_rgb_solid_color_command(r: int, g: int, b: int) -> None:
    await send_pixel_effect_command(effect=Effect.SOLID, solid_color=(r, g, b))
