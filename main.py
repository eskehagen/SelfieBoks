"""
main.py -- Entry point for SelfieBoks.

INGEN qasync. Arkitektur:
  - Qt korer i main-traaden med app.exec()
  - BLE korer i en separat daemon-traad med sit eget asyncio event loop
  - LED-kommandoer sendes via ble_loop.run_coroutine_threadsafe()
  - Dropbox-upload korer i en ThreadPoolExecutor
"""

import asyncio
import logging
import sys
import threading

from PyQt6.QtWidgets import QApplication

from ui.app_window import AppWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Globalt BLE event loop -- saettes af _ble_thread_main, bruges af led_commands
ble_loop: asyncio.AbstractEventLoop | None = None
ble_loop_ready = threading.Event()


def _ble_thread_main() -> None:
    """Koerer i en daemon-traad. Starter BLE event loop og bluetooth_manager."""
    global ble_loop

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ble_loop = loop
    ble_loop_ready.set()   # Signaliser til main at loop er klar

    try:
        from bluetooth_manager import bluetooth_manager  # type: ignore[import]
        from led_commands import BLUETOOTH_ENABLED       # type: ignore[import]

        if BLUETOOTH_ENABLED:
            logger.info("[BLE] Bluetooth manager startet i daemon-traad.")
            loop.run_until_complete(bluetooth_manager.run())
        else:
            logger.info("[BLE] BLE deaktiveret -- traad slutter.")
    except Exception as exc:
        logger.warning(f"[BLE] Traad fejlede: {exc}")
    finally:
        loop.close()


def main() -> None:
    # -- Start BLE daemon-thread -----------------------------------------------
    ble_thread = threading.Thread(target=_ble_thread_main, name="ble-loop", daemon=True)
    ble_thread.start()

    # Vent maks 3 sek paa at BLE-loop er klar (saa led_commands kan bruge det)
    ble_loop_ready.wait(timeout=3.0)

    # Eksporter ble_loop til led_commands saa den kan sende kommandoer
    try:
        import led_commands  # type: ignore[import]
        led_commands._ble_loop = ble_loop
    except Exception:
        pass

    # -- Qt main thread --------------------------------------------------------
    logger.info("[Main] Starter QApplication...")
    app = QApplication(sys.argv)
    app.setApplicationName("SelfieBoks")

    # Detekter faktisk skaermstorrelse og skriv til config inden AppWindow oprettes
    import config as _cfg
    screen_geo = app.primaryScreen().geometry()
    _cfg.SCREEN_WIDTH  = screen_geo.width()
    _cfg.SCREEN_HEIGHT = screen_geo.height()
    logger.info(f"[Main] Skaerm: {_cfg.SCREEN_WIDTH}x{_cfg.SCREEN_HEIGHT}")

    logger.info("[Main] Opretter AppWindow...")
    window = AppWindow()
    window.showFullScreen()
    logger.info("[Main] Korer Qt event loop...")

    exit_code = app.exec()
    logger.info(f"[Main] App afsluttet (exit code {exit_code}).")
    sys.exit(exit_code)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("[Main] Afbrudt af bruger.")
    except Exception as exc:
        logger.exception(f"[Main] Uventet fejl: {exc}")
        sys.exit(1)
