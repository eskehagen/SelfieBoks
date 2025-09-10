import asyncio
import sys
import threading
import time
from enum import Enum
from typing import Optional, Tuple

# Vi importerer den delte instans fra vores anden fil
from bluetooth_manager import bluetooth_manager

# På Windows er Bleak ofte mere stabil med WindowsSelectorEventLoopPolicy
if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        # Politik er måske allerede sat eller ikke nødvendig i det aktuelle miljø
        pass


# --- Enum med understøttede Pixel LED Effekt Navne ---
class Effect(Enum):
    SOLID = "solid"
    RAINBOW = "rainbow"
    SINELON = "sinelon"
    CONFETTI = "confetti"
    TWINKLE = "twinkle"        # rettet stavefejl
    THEATERCHASE = "theaterchase"
    COLORWIPE = "colorwipe"
    COMET = "comet"
    GLITTER = "glitter"
    PULSE = "pulse"
    METEOR = "meteor"
    NOISE = "noise"
    DUALWIPE = "dualwipe"
    GRADIENT = "gradient"
    OFF = "off"

    def __str__(self):
        return self.value


# --- Funktioner til at bygge og sende kommandoer ---

async def send_raw_command(command: str):
    """Sender en rå, uformateret kommando-streng."""
    try:
        print(f"[BLE] RAW → {command}")
        await bluetooth_manager.send_command(command)
    except Exception as e:
        print(f"[BLE][ERROR] Kunne ikke sende kommando: {e}")


async def send_white_led_command(on: bool, white_bright: Optional[int] = 255):
    """
    Bygger og sender en kommando til at styre det hvide LED-lys.
    :param on: Tænd eller sluk (True/False).
    :param white_bright: Lysstyrke for hvidt lys (0-255).
    """
    parts = [f"WHITE={'on' if on else 'off'}"]
    if white_bright is not None:
        clamped_bright = max(0, min(white_bright, 255))
        parts.append(f"WHITE_BRIGHT={clamped_bright}")

    command = ";".join(parts)
    await send_raw_command(command)


async def send_pixel_effect_command(
    effect: Optional[Effect] = None,
    rgb_bright: Optional[int] = 255,
    solid_color: Optional[Tuple[int, int, int]] = None
):
    """
    Bygger og sender en kommando til at styre RGB Pixel LED-effekter.
    :param effect: En effekt fra Effect-enum'en.
    :param rgb_bright: Lysstyrke for RGB (0-255).
    :param solid_color: En (R, G, B) tuple for faste farver.
    """
    parts = []
    if effect is not None:
        parts.append(f"EFFECT={effect.value}")

    if rgb_bright is not None:
        clamped_bright = max(0, min(rgb_bright, 255))
        parts.append(f"RGB_BRIGHT={clamped_bright}")

    if solid_color is not None:
        r, g, b = solid_color
        clamped_r = max(0, min(r, 255))
        clamped_g = max(0, min(g, 255))
        clamped_b = max(0, min(b, 255))
        parts.append(f"COLOR={clamped_r},{clamped_g},{clamped_b}")

    if parts:
        command = ";".join(parts)
        await send_raw_command(command)


async def send_rgb_solid_color_command(r: int, g: int, b: int):
    """En hjælpe-funktion til nemt at sætte en fast farve."""
    await send_pixel_effect_command(effect=Effect.SOLID, solid_color=(r, g, b))


# --- Baggrunds event loop-håndtering for robust start uden aktivt loop ---
_bg_loop: Optional[asyncio.AbstractEventLoop] = None
_bg_thread: Optional[threading.Thread] = None
_ble_task_started: bool = False


def _bg_loop_thread():
    """Kører et dedikeret asyncio event loop i en daemon-tråd."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    global _bg_loop
    _bg_loop = loop
    loop.run_forever()


def _ensure_background_loop():
    """Sørger for, at der er et baggrunds event loop kørende."""
    global _bg_thread
    if _bg_thread and _bg_thread.is_alive():
        return
    _bg_thread = threading.Thread(target=_bg_loop_thread, name="ble-bg-loop", daemon=True)
    _bg_thread.start()
    # Vent kort til loop’et er klar
    for _ in range(100):
        if _bg_loop is not None:
            return
        time.sleep(0.01)
    if _bg_loop is None:
        raise RuntimeError("Kunne ikke initialisere baggrunds event loop.")


def _submit_coro_to_bg(coro: asyncio.coroutines):
    """Indsender en coroutine til baggrunds event loop på en trådsikker måde."""
    _ensure_background_loop()
    assert _bg_loop is not None
    return asyncio.run_coroutine_threadsafe(coro, _bg_loop)


# --- Hjælperfunktion til at starte bluetooth_manager ---
def start_bluetooth_manager():
    """Starter den delte bluetooth_manager-instans i baggrunden."""
    global _ble_task_started
    if _ble_task_started:
        return

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(bluetooth_manager.run())
        print("[BLE] Bluetooth manager startet i eksisterende event loop.")
        _ble_task_started = True
    except RuntimeError:
        # Ingen event loop kører (fx hvis kaldt fra synkron kode eller fremmed tråd)
        _submit_coro_to_bg(bluetooth_manager.run())
        print("[BLE] Bluetooth manager startet i baggrunds-event loop.")
        _ble_task_started = True


# --- Eksempel på brug (kører kun hvis filen køres direkte) ---
if __name__ == '__main__':
    async def test_commands():
        print("--- Kører led_commands.py i test-mode ---")
        start_bluetooth_manager()
        await asyncio.sleep(2)

        print("Simulerer afsendelse af kommandoer...")
        await send_white_led_command(on=True, white_bright=128)
        await asyncio.sleep(2)
        await send_pixel_effect_command(effect=Effect.RAINBOW, rgb_bright=200)
        await asyncio.sleep(2)
        await send_rgb_solid_color_command(r=0, g=255, b=0)  # Grøn
        await asyncio.sleep(2)
        await send_pixel_effect_command(effect=Effect.OFF)

    asyncio.run(test_commands())
