"""
ui/review_screen.py -- Review-siden (Side 2).

Bruger resizeEvent til dynamisk layout -- ingen hardkodede skaermdimensioner.
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QProgressBar, QWidget

from config import (
    ANIMATION_FPS,
    AUTO_RETURN_MS,
    AUTO_RETURN_TICK_MS,
    DELETE_BUTTON_FRAMES,
    REVIEW_BUTTON_SIZE,
    SAVE_BUTTON_FRAMES,
)
from ui.widgets.animated_widget import AnimatedWidget

_PROGRESS_HEIGHT = 8
_BTN_MARGIN_X    = 60
_BTN_MARGIN_Y    = 30


class ReviewScreen(QWidget):
    """
    Viser et fanget billede og lader brugeren vaelge at gemme eller slette det.

    Signals:
        save_requested:   Bruger valgte "GEM".
        delete_requested: Bruger valgte "SLET" eller auto-return timer udloeb.
    """

    save_requested   = pyqtSignal()
    delete_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # -- Foto-display (fuldskarm baggrund) ----------------------------
        self._photo_label = QLabel(self)
        self._photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._photo_label.setStyleSheet("background: black;")

        # -- Auto-return progress-bar --------------------------------------
        self._progress = QProgressBar(self)
        self._progress.setRange(0, AUTO_RETURN_MS)
        self._progress.setValue(AUTO_RETURN_MS)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(
            "QProgressBar { background: #333; border: none; }"
            "QProgressBar::chunk { background: #00aaff; }"
        )

        # -- Animeret SLET-knap (venstre) ----------------------------------
        self._delete_btn = AnimatedWidget(
            DELETE_BUTTON_FRAMES, size=REVIEW_BUTTON_SIZE, fps=ANIMATION_FPS, parent=self
        )
        self._delete_btn.clicked.connect(self.delete_requested.emit)

        self._delete_label = QLabel("SLET", self)
        self._delete_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._delete_label.setStyleSheet(
            "color: white; background: transparent; font-weight: bold; font-size: 18pt;"
        )
        self._delete_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # -- Animeret GEM-knap (hoejre) ------------------------------------
        self._save_btn = AnimatedWidget(
            SAVE_BUTTON_FRAMES, size=REVIEW_BUTTON_SIZE, fps=ANIMATION_FPS, parent=self
        )
        self._save_btn.clicked.connect(self.save_requested.emit)

        self._save_label = QLabel("GEM", self)
        self._save_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._save_label.setStyleSheet(
            "color: white; background: transparent; font-weight: bold; font-size: 18pt;"
        )
        self._save_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # -- Auto-return timer ---------------------------------------------
        self._remaining_ms = AUTO_RETURN_MS
        self._auto_timer = QTimer(self)
        self._auto_timer.setInterval(AUTO_RETURN_TICK_MS)
        self._auto_timer.timeout.connect(self._tick)

        self._current_pixmap_path: str | None = None

    # -- Dynamisk layout ved resize --------------------------------------------

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        w, h = self.width(), self.height()

        self._photo_label.setGeometry(0, 0, w, h)
        self._progress.setGeometry(0, h - _PROGRESS_HEIGHT, w, _PROGRESS_HEIGHT)

        btn_y = h - REVIEW_BUTTON_SIZE - _BTN_MARGIN_Y
        del_x = _BTN_MARGIN_X
        save_x = w - REVIEW_BUTTON_SIZE - _BTN_MARGIN_X

        self._delete_btn.move(del_x, btn_y)
        self._delete_label.setGeometry(del_x, btn_y, REVIEW_BUTTON_SIZE, REVIEW_BUTTON_SIZE)
        self._save_btn.move(save_x, btn_y)
        self._save_label.setGeometry(save_x, btn_y, REVIEW_BUTTON_SIZE, REVIEW_BUTTON_SIZE)

        # Geo-opdater foto hvis vi allerede viser et
        if self._current_pixmap_path:
            self._display_photo(self._current_pixmap_path)

    # -- Offentlige metoder -------------------------------------------------

    def show_photo(self, filepath: str) -> None:
        self._current_pixmap_path = filepath
        self._display_photo(filepath)
        self._start_timer()

    def stop_timer(self) -> None:
        self._auto_timer.stop()

    # -- Intern logik ------------------------------------------------------

    def _display_photo(self, filepath: str) -> None:
        pix = QPixmap(filepath)
        if not pix.isNull():
            pix = pix.scaled(
                self.width(),
                self.height(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.FastTransformation,
            )
        else:
            pix = QPixmap(self.width(), self.height())
            pix.fill(Qt.GlobalColor.black)
        self._photo_label.setPixmap(pix)

    def _start_timer(self) -> None:
        self._remaining_ms = AUTO_RETURN_MS
        self._progress.setValue(AUTO_RETURN_MS)
        self._auto_timer.start()

    def _tick(self) -> None:
        self._remaining_ms -= AUTO_RETURN_TICK_MS
        self._progress.setValue(max(0, self._remaining_ms))
        if self._remaining_ms <= 0:
            self._auto_timer.stop()
            self.delete_requested.emit()
