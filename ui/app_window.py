"""
ui/app_window.py -- Hovedvindue og applikationscontroller.

Tilstande: PREVIEW -> COUNTDOWN -> REVIEW -> PREVIEW

BLE-kommandoer sendes via led_commands.fire() som er traad-sikker --
ingen asyncio i Qt main thread.
"""

import logging
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from camera_manager import CameraManager
from config import COUNTDOWN_DURATION_MS, DROPBOX_ACCESS_TOKEN, PHOTOS_DIR
from storage_manager import StorageManager
from ui.capture_screen import CaptureScreen
from ui.review_screen import ReviewScreen

logger = logging.getLogger(__name__)

# BLE import med graceful fallback
try:
    from led_commands import (  # type: ignore[import]
        BLUETOOTH_ENABLED,
        Effect,
        fire,
        send_pixel_effect_command,
        send_white_led_command,
    )
except Exception:
    BLUETOOTH_ENABLED = False
    Effect = None  # type: ignore[assignment]

    def fire(coro) -> None:  # type: ignore[misc]
        pass


class AppWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SelfieBoks")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._capture_in_progress = False
        self._current_photo_path: str | None = None

        self._camera  = CameraManager(self)
        self._storage = StorageManager(PHOTOS_DIR, DROPBOX_ACCESS_TOKEN)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._capture_screen = CaptureScreen()
        self._review_screen  = ReviewScreen()
        self._stack.addWidget(self._capture_screen)
        self._stack.addWidget(self._review_screen)

        self._camera.frame_ready.connect(self._capture_screen.update_frame)
        self._capture_screen.capture_requested.connect(self._on_capture_requested)
        self._review_screen.save_requested.connect(self._on_save)
        self._review_screen.delete_requested.connect(self._on_delete)

        QTimer.singleShot(150, self._camera.start)
        self._show_capture_screen()

        if BLUETOOTH_ENABLED and Effect:
            fire(send_pixel_effect_command(Effect.RAINBOW))

    def _show_capture_screen(self) -> None:
        self._stack.setCurrentWidget(self._capture_screen)

    def _show_review_screen(self) -> None:
        self._stack.setCurrentWidget(self._review_screen)

    def _on_capture_requested(self) -> None:
        if self._capture_in_progress:
            return
        self._capture_in_progress = True
        self._capture_screen.start_countdown()

        if BLUETOOTH_ENABLED and Effect:
            fire(send_white_led_command(on=True))
            fire(send_pixel_effect_command(Effect.OFF))

        QTimer.singleShot(COUNTDOWN_DURATION_MS, self._take_photo)

    def _take_photo(self) -> None:
        self._capture_screen.show_flash()
        QApplication.processEvents()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._current_photo_path = str(PHOTOS_DIR / f"SELFIE_{timestamp}.jpg")
        self._camera.capture_still(self._current_photo_path)

        self._capture_screen.end_countdown()

        if BLUETOOTH_ENABLED and Effect:
            # Kun WHITE=off -- ingen RAINBOW her.
            # LED'erne er moerklagte mens brugeren ser sit billede.
            # RAINBOW sendes i _go_back_to_camera() naar de vender tilbage.
            fire(send_white_led_command(on=False))

        self._review_screen.show_photo(self._current_photo_path)
        self._show_review_screen()

    def _on_save(self) -> None:
        self._review_screen.stop_timer()
        if self._current_photo_path:
            # Upload korer i ThreadPoolExecutor -- blokerer ikke Qt
            import threading
            threading.Thread(
                target=self._storage._blocking_upload,
                args=(self._current_photo_path,),
                daemon=True,
            ).start()
        self._go_back_to_camera()

    def _on_delete(self) -> None:
        self._review_screen.stop_timer()
        if self._current_photo_path:
            self._storage.delete(self._current_photo_path)
        self._go_back_to_camera()

    def _go_back_to_camera(self) -> None:
        self._current_photo_path  = None
        self._capture_in_progress = False
        if BLUETOOTH_ENABLED and Effect:
            # Kun RAINBOW-effekt -- WHITE er allerede slukket i _take_photo().
            # send_white_led_command(on=False) sendes IKKE her fordi ESP32-firmwaren
            # tolker WHITE_BRIGHT=255 i samme kommando som en aktivering af det hvide LED.
            fire(send_pixel_effect_command(Effect.RAINBOW))
        self._show_capture_screen()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        """Esc lukker appen -- nyttigt under test naar appen koerer fullscreen."""
        if event.key() == Qt.Key.Key_Escape:
            QApplication.quit()
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        logger.info("[App] Lukker -- frigiver kamera.")
        self._review_screen.stop_timer()
        self._camera.stop()
        super().closeEvent(event)
