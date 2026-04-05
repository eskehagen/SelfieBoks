"""
ui/capture_screen.py -- Capture-siden (Side 1).

Bruger resizeEvent til at placere alle child-widgets dynamisk,
saa skarmstorrelsen ikke behoever at vaere kendt ved opstart.

Layout (z-raekkefolge nedefra og op):
  1. camera_label       -- fuldskarm kamera-preview (baggrund)
  2. capture_overlay    -- centreret animeret capture-knap + tekst
  3. countdown_overlay  -- fuldskarm semi-transparent nedtaellings-overlay (skjult)
  4. flash_overlay      -- fuldskarm hvid "kamera-blink" (skjult)
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QImage, QPixmap
from PyQt6.QtWidgets import QLabel, QWidget

from config import (
    ANIMATION_FPS,
    CAPTURE_BUTTON_FRAMES,
    CAPTURE_BUTTON_SIZE,
    COUNTDOWN_ANIM_FRAMES,
    COUNTDOWN_FRAMES,
)
from ui.widgets.animated_widget import AnimatedWidget

_COUNTDOWN_SIZE = 480


class CaptureScreen(QWidget):
    """
    Viser live kamera-preview med en animeret capture-knap i centrum.
    Emitter `capture_requested` naar brugeren trykker paa knappen.
    """

    capture_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # -- 1. Kamera-preview (fuldskarm baggrund) ------------------------
        self._camera_label = QLabel(self)
        self._camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._camera_label.setStyleSheet("background: black;")

        # -- 2. Capture-knap overlay (centreret) --------------------------
        self._capture_overlay = QWidget(self)
        self._capture_overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._capture_overlay.setFixedSize(CAPTURE_BUTTON_SIZE, CAPTURE_BUTTON_SIZE)

        self._capture_anim = AnimatedWidget(
            CAPTURE_BUTTON_FRAMES,
            size=CAPTURE_BUTTON_SIZE,
            fps=ANIMATION_FPS,
            parent=self._capture_overlay,
        )
        self._capture_anim.setGeometry(0, 0, CAPTURE_BUTTON_SIZE, CAPTURE_BUTTON_SIZE)
        self._capture_anim.clicked.connect(self._on_capture_clicked)

        self._capture_label = QLabel("TAG BILLEDE", self._capture_overlay)
        self._capture_label.setGeometry(0, 0, CAPTURE_BUTTON_SIZE, CAPTURE_BUTTON_SIZE)
        self._capture_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(22)
        font.setBold(True)
        self._capture_label.setFont(font)
        self._capture_label.setStyleSheet("color: white; background: transparent;")
        self._capture_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # -- 3. Nedtaellings-overlay (fuldskarm, skjult normalt) ----------
        self._countdown_overlay = QWidget(self)
        self._countdown_overlay.setStyleSheet("background: rgba(0, 0, 0, 140);")
        self._countdown_overlay.hide()

        self._countdown_numbers = AnimatedWidget(
            COUNTDOWN_FRAMES,
            size=_COUNTDOWN_SIZE,
            fps=ANIMATION_FPS,
            parent=self._countdown_overlay,
        )
        self._countdown_anim = AnimatedWidget(
            COUNTDOWN_ANIM_FRAMES,
            size=_COUNTDOWN_SIZE,
            fps=ANIMATION_FPS,
            parent=self._countdown_overlay,
        )
        self._countdown_numbers.raise_()

        # -- 4. Flash-overlay ----------------------------------------------
        self._flash_overlay = QWidget(self)
        self._flash_overlay.setStyleSheet("background: white;")
        self._flash_overlay.hide()

    # -- Dynamisk layout ved resize --------------------------------------------

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        w, h = self.width(), self.height()

        self._camera_label.setGeometry(0, 0, w, h)

        cx = (w - CAPTURE_BUTTON_SIZE) // 2
        cy = (h - CAPTURE_BUTTON_SIZE) // 2
        self._capture_overlay.move(cx, cy)

        self._countdown_overlay.setGeometry(0, 0, w, h)
        cdx = (w - _COUNTDOWN_SIZE) // 2
        cdy = (h - _COUNTDOWN_SIZE) // 2
        self._countdown_numbers.move(cdx, cdy)
        self._countdown_anim.move(cdx, cdy)

        self._flash_overlay.setGeometry(0, 0, w, h)

        self._capture_overlay.raise_()
        self._countdown_overlay.raise_()
        self._flash_overlay.raise_()

    # -- Kamera-preview opdatering ---------------------------------------------

    def update_frame(self, image: QImage) -> None:
        pix = QPixmap.fromImage(image).scaled(
            self.width(),
            self.height(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.FastTransformation,
        )
        self._camera_label.setPixmap(pix)

    # -- Capture-knap interaktion ----------------------------------------------

    def _on_capture_clicked(self) -> None:
        self.capture_requested.emit()

    # -- Tilstandsstyring ------------------------------------------------------

    def start_countdown(self) -> None:
        self._capture_overlay.hide()
        self._countdown_numbers.reset()
        self._countdown_anim.reset()
        self._countdown_overlay.show()
        self._countdown_overlay.raise_()

    def show_flash(self) -> None:
        self._flash_overlay.show()
        self._flash_overlay.raise_()

    def end_countdown(self) -> None:
        self._countdown_overlay.hide()
        self._flash_overlay.hide()
        self._capture_overlay.show()
        self._capture_anim.reset()
