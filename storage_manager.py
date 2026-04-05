"""
storage_manager.py — Håndterer fil-lagring til disk og Dropbox.

Dropbox-upload køres i en thread-pool executor for ikke at blokere Qt event loop.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DROPBOX_AVAILABLE = False
try:
    import dropbox          # type: ignore[import]
    import dropbox.files    # type: ignore[import]
    _DROPBOX_AVAILABLE = True
except ImportError:
    logger.warning("[Storage] dropbox SDK ikke installeret — Dropbox-upload deaktiveret.")


class StorageManager:
    """
    Håndterer gemning og sletning af selfie-billeder samt asynkron upload til Dropbox.

    Args:
        photos_dir: Lokal mappe til billeder (oprettes automatisk).
        dropbox_token: Dropbox API-token, eller None for at deaktivere upload.
    """

    def __init__(self, photos_dir: Path, dropbox_token: Optional[str] = None) -> None:
        self.photos_dir = photos_dir
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self._token = dropbox_token

        if dropbox_token and not _DROPBOX_AVAILABLE:
            logger.warning("[Storage] Dropbox token angivet men SDK mangler. Kør: pip install dropbox")

    # ── Disk-operationer ───────────────────────────────────────────────────

    def delete(self, filepath: str) -> None:
        """Slet en fil fra disk. Fejl logges men kastes ikke videre."""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"[Storage] Slettet: {filepath}")
        except OSError as exc:
            logger.error(f"[Storage] Kunne ikke slette '{filepath}': {exc}")

    # ── Dropbox-upload (asynkron) ──────────────────────────────────────────

    async def upload_to_dropbox(self, filepath: str) -> bool:
        """
        Upload en fil til Dropbox asynkront (blokerer ikke Qt event loop).

        Returns True ved succes, False ved fejl eller manglende konfiguration.
        """
        if not self._token:
            logger.info(f"[Dropbox] Ingen token — fil beholdes kun lokalt: {filepath}")
            return False

        if not _DROPBOX_AVAILABLE:
            logger.warning("[Dropbox] SDK ikke tilgængeligt.")
            return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._blocking_upload, filepath)

    def _blocking_upload(self, filepath: str) -> bool:
        """Synkron Dropbox-upload — køres i thread-pool via run_in_executor."""
        try:
            dbx = dropbox.Dropbox(self._token)
            dest_path = "/" + Path(filepath).name
            with open(filepath, "rb") as f:
                dbx.files_upload(
                    f.read(),
                    dest_path,
                    mode=dropbox.files.WriteMode.overwrite,
                )
            logger.info(f"[Dropbox] Uploadet til: {dest_path}")
            return True
        except Exception as exc:
            logger.error(f"[Dropbox] Upload fejlede for '{filepath}': {exc}")
            return False
