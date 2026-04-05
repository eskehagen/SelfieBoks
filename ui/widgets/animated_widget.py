"""
ui/widgets/animated_widget.py — Genanvendelig animeret QLabel.

Indlæser PNG-frames progressivt (ét frame per event-loop-iteration) via en
QTimer med interval=0, så UI'en forbliver responsiv under indlæsning.

Understøtter:
- Transparent baggrund (selfie-boks overlay-animationer)
- Klik-signal til interaktive knapper
- pause/resume/reset
"""

from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel


class AnimatedWidget(QLabel):
    """
    QLabel der afspiller en sekvens af PNG-filer som en animation.

    Args:
        frames_path: Sti til mappe med frame_XXXX.png filer.
        size:        Kvadratisk størrelse i pixels (frames skaleres til size×size).
        fps:         Afspilningshastighed i frames pr. sekund.
        parent:      Qt-forældrewidget.
    """

    clicked = pyqtSignal()

    def __init__(
        self,
        frames_path: Path,
        size: int = 400,
        fps: int = 30,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self._size = size
        self._fps = fps
        self._pixmaps: list[QPixmap] = []
        self._load_index = 0
        self._current_index = 0

        # Saml og sortér frame-filer
        if frames_path.exists():
            self._frame_files = sorted(frames_path.glob("*.png"))
        else:
            print(f"[AnimatedWidget] Advarsel: sti ikke fundet: {frames_path}")
            self._frame_files = []

        # Widget-egenskaber
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Transparent så baggrundslaget (kamera/foto) skinner igennem
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")

        # ── Afspilningstimer ──────────────────────────────────────────────
        self._play_timer = QTimer(self)
        self._play_timer.timeout.connect(self._next_frame)

        # ── Progressiv indlæsningstimer ───────────────────────────────────
        # interval=0: fyres for hvert ledigt event-loop-slot, blokerer ikke UI
        self._load_timer = QTimer(self)
        self._load_timer.setInterval(0)
        self._load_timer.timeout.connect(self._load_next_frame)

        if self._frame_files:
            self._load_timer.start()
        else:
            print(f"[AnimatedWidget] Ingen PNG-frames i: {frames_path}")

    # ── Indlæsning ──────────────────────────────────────────────────────────

    def _load_next_frame(self) -> None:
        if self._load_index >= len(self._frame_files):
            self._load_timer.stop()
            # Start afspilning når alle frames er klar
            if self._pixmaps:
                self.setPixmap(self._pixmaps[0])
                self._play_timer.start(1000 // self._fps)
            return

        path = self._frame_files[self._load_index]
        pix = QPixmap(str(path))

        if not pix.isNull():
            # Skalér til ønsket størrelse med smooth transformation (antialiasing)
            pix = pix.scaled(
                self._size,
                self._size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._pixmaps.append(pix)

            # Vis første frame med det samme uden at vente på at alt er indlæst
            if self._load_index == 0:
                self.setPixmap(pix)

        self._load_index += 1

    # ── Afspilning ───────────────────────────────────────────────────────────

    def _next_frame(self) -> None:
        if not self._pixmaps:
            return
        self._current_index = (self._current_index + 1) % len(self._pixmaps)
        self.setPixmap(self._pixmaps[self._current_index])

    def pause(self) -> None:
        """Stop animation på nuværende frame."""
        self._play_timer.stop()

    def resume(self) -> None:
        """Genoptag animation fra nuværende frame."""
        if self._pixmaps and not self._play_timer.isActive():
            self._play_timer.start(1000 // self._fps)

    def reset(self) -> None:
        """Nulstil til første frame."""
        self._current_index = 0
        if self._pixmaps:
            self.setPixmap(self._pixmaps[0])

    # ── Interaktion ──────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
