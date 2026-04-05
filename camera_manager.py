"""
camera_manager.py — Kamera-abstraktionslag.

Bruger picamera2 til at levere en live preview via Qt-signals og stillbilleder
via switch_mode_and_capture_file (høj opløsning).

På ikke-Pi platforme (Windows / macOS) falder den tilbage til en simpel mock,
så UI'en kan udvikles og testes uden et Pi kamera tilsluttet.
"""

import logging
from typing import Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QImage

from config import (
    PREVIEW_FPS,
    PREVIEW_HEIGHT,
    PREVIEW_WIDTH,
)

logger = logging.getLogger(__name__)

# ─── Forsøg på at importere picamera2 (Pi-only) ──────────────────────────────
_PICAMERA2_AVAILABLE = False
try:
    from libcamera import Transform         # type: ignore[import]
    from picamera2 import Picamera2         # type: ignore[import]
    _PICAMERA2_AVAILABLE = True
    logger.info("[Camera] picamera2 tilgængeligt.")
except Exception:
    logger.warning("[Camera] picamera2 ikke tilgængeligt — kører i mock-tilstand.")


class CameraManager(QObject):
    """
    Kameramanager der emitter `frame_ready(QImage)` for hvert preview-billede.

    Signal emitteres fra kameraets interne tråd (picamera2) eller fra en QTimer
    (mock). PyQt6 kø-er automatisk signalets slot-kald til GUI-tråden via
    Qt.AutoConnection.

    Vigtigt: `QPixmap.fromImage()` MÅ kun kaldes i GUI-tråden.
    Alle forbundne slots skal derfor lave konverteringen der.
    """

    frame_ready = pyqtSignal(QImage)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._camera: Optional["Picamera2"] = None
        self._running = False
        self._mock_timer: Optional[QTimer] = None

    # ── Livscyklus ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start kamera-preview. Kalder enten picamera2 eller mock."""
        if _PICAMERA2_AVAILABLE:
            self._start_picamera2()
        else:
            self._start_mock()

    def stop(self) -> None:
        """Stop kamera og frigiv ressourcer."""
        self._running = False

        if self._mock_timer:
            self._mock_timer.stop()
            self._mock_timer = None

        if self._camera:
            try:
                self._camera.post_callback = None
                self._camera.stop()
                self._camera.close()
            except Exception as exc:
                logger.error(f"[Camera] Fejl under stop: {exc}")
            finally:
                self._camera = None

    # ── picamera2 ───────────────────────────────────────────────────────────

    def _start_picamera2(self) -> None:
        try:
            self._camera = Picamera2()

            # 1920x1080 sensor-mode bruger 3840x2160 crop (bred FOV, ingen zoom).
            # 1280x720 bruger kun 2560x1440 crop -- det er DERFOR preview saa zoomet ud.
            # Transform(hflip=True) laver spejlvending i ISP -- ingen CPU-overhead.
            config = self._camera.create_video_configuration(
                main={"size": (PREVIEW_WIDTH, PREVIEW_HEIGHT), "format": "RGB888"},
                transform=Transform(hflip=True),
                controls={
                    "FrameRate": PREVIEW_FPS,
                    "AfMode":    2,   # Continuous autofocus
                    "AfSpeed":   1,   # Fast
                },
            )
            self._camera.configure(config)
            self._camera.post_callback = self._on_frame
            self._camera.start()
            self._running = True
            logger.info(
                f"[Camera] Preview startet ({PREVIEW_WIDTH}\u00d7{PREVIEW_HEIGHT} "
                f"@ {PREVIEW_FPS} fps, kontinuerlig AF)."
            )
        except Exception as exc:
            logger.error(f"[Camera] Kunne ikke starte picamera2: {exc}. Falder tilbage til mock.")
            self._camera = None
            self._start_mock()

    def _on_frame(self, request) -> None:
        """
        Callback fra picamera2's interne kameratråd — kaldt for hvert frame.

        REGLER:
        - Må ikke blokere (returner hurtigt).
        - Må ikke oprette QPixmap (kun tilladt i GUI-tråd).
        - QImage er tilladt i alle tråde.
        """
        if not self._running:
            return
        try:
            # picamera2 RGB888: bytes gemmes som BGR (V4L2 konvention).
            # [:, :, ::-1] swapper B<->R kanaler. hflip klares af ISP via Transform.
            bgr = request.make_array("main")
            rgb = bgr[:, :, ::-1].copy()

            h, w = rgb.shape[:2]
            img = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
            self.frame_ready.emit(img.copy())
        except Exception as exc:
            logger.debug(f"[Camera] Frame callback fejl: {exc}")

    def capture_still(self, filepath: str) -> str:
        """
        Gem et stillbillede fra den KOERENDE preview-stream.

        Bruger capture_file() direkte -- ingen mode-skift, ingen sensor-crop-aendring.
        Garanterer identisk FOV som det brugeren ser i preview.
        """
        if not _PICAMERA2_AVAILABLE or self._camera is None:
            return self._mock_capture(filepath)

        try:
            # capture_file() tager et billede fra current stream og gemmer det.
            # picamera2 konverterer automatisk RGB888 -> JPEG via Pillow.
            self._camera.capture_file(filepath)
            logger.info(f"[Camera] Billede gemt: {filepath}")
        except Exception as exc:
            logger.error(f"[Camera] Capture fejlede: {exc}")
            self._mock_capture(filepath)

        return filepath

    # ── Mock (Windows / macOS dev) ──────────────────────────────────────────

    def _start_mock(self) -> None:
        """Genererer animerede testframes via QTimer — ingen Pi nødvendig."""
        import time

        import numpy as np

        self._running = True
        self._mock_timer = QTimer(self)

        def _emit() -> None:
            if not self._running:
                return
            # Simpelt animeret mønster (blå→cyan gradient der bevæger sig)
            t = int(time.monotonic() * 30) % 256
            arr = np.zeros((PREVIEW_HEIGHT, PREVIEW_WIDTH, 3), dtype=np.uint8)
            arr[:, :, 0] = t               # R
            arr[:, :, 1] = 80              # G
            arr[:, :, 2] = 255 - t         # B
            img = QImage(arr.data, PREVIEW_WIDTH, PREVIEW_HEIGHT,
                         PREVIEW_WIDTH * 3, QImage.Format.Format_RGB888)
            self.frame_ready.emit(img.copy())

        self._mock_timer.timeout.connect(_emit)
        self._mock_timer.start(1000 // PREVIEW_FPS)
        logger.info("[Camera] Mock-preview startet.")

    def _mock_capture(self, filepath: str) -> str:
        """Gem et simpelt rødligt placeholder-billede."""
        try:
            import numpy as np
            from PIL import Image

            arr = np.full((PREVIEW_HEIGHT, PREVIEW_WIDTH, 3), [180, 60, 60], dtype=np.uint8)
            Image.fromarray(arr).save(filepath)
            logger.info(f"[Camera] Mock-billede gemt: {filepath}")
        except Exception as exc:
            logger.warning(f"[Camera] Mock capture fejlede: {exc}")
        return filepath
