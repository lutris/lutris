"""Expose a game's own artwork to Qt Quick, preparing chosen images with QImage."""

import asyncio
import os
import tempfile
from collections.abc import Coroutine
from gettext import gettext as _
from typing import Any

from PySide6.QtCore import Property, QObject, QSize, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QImage

from lutris.backend import game_artwork
from lutris.backend.models import ArtworkChoice, GameArtworkImage
from lutris.exceptions import LutrisError
from lutris.qt.delegates import PromptController
from lutris.qt.tasks import start_task

# The largest each kind is stored at; bigger images are scaled down to fit
STORAGE_SIZES = {"cover": QSize(600, 900), "banner": QSize(920, 430), "icon": QSize(256, 256)}
_LABELS = {"cover": _("Cover"), "banner": _("Banner"), "icon": _("Icon")}


def prepare_image(source: str, kind: str) -> str:
    """Scale an image down to its storage size and save it as PNG (icons, or images with
    transparency) or JPEG, in a temporary file the caller removes. QImage, unlike QPixmap,
    works outside the GUI thread."""
    image = QImage(source)
    if image.isNull():
        raise LutrisError(_("This file isn't an image Lutris can read."))
    limit = STORAGE_SIZES[kind]
    if image.width() > limit.width() or image.height() > limit.height():
        image = image.scaled(limit, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    as_png = kind == "icon" or image.hasAlphaChannel()
    handle, path = tempfile.mkstemp(prefix="lutris-artwork-", suffix=".png" if as_png else ".jpg")
    os.close(handle)
    # PySide6's stub types the format as bytes, but the binding only takes a str
    if not image.save(path, "PNG" if as_png else "JPEG", -1 if as_png else 95):  # ty: ignore[no-matching-overload]
        os.remove(path)
        raise LutrisError(_("The image could not be converted."))
    return path


class GameArtworkController(QObject):
    stateChanged = Signal()
    choicesChanged = Signal()

    def __init__(self, prompts: PromptController, parent: QObject) -> None:
        super().__init__(parent)
        self._prompts = prompts
        self._game_id = ""
        self._images: dict[str, GameArtworkImage] = {}
        self._revision = 0
        self._working = ""
        self._choices: tuple[ArtworkChoice, ...] = ()
        self._choices_kind = ""
        self._loading_choices = False

    @Property(list, notify=stateChanged)
    def images(self) -> list[dict[str, Any]]:
        result = []
        for kind in ("cover", "banner", "icon"):
            image = self._images.get(kind)
            url = QUrl()
            if image and image.path:
                url = QUrl.fromLocalFile(image.path)
                # Images are cached by URL, so a replaced file needs a new one
                url.setQuery(f"revision={self._revision}")
            result.append(
                {
                    "kind": kind,
                    "label": _LABELS[kind],
                    "url": url,
                    "custom": bool(image and image.custom),
                    "working": self._working == kind,
                }
            )
        return result

    @Property(bool, notify=stateChanged)
    def working(self) -> bool:
        return bool(self._working)

    @Property(list, notify=choicesChanged)
    def choices(self) -> list[dict[str, Any]]:
        return [
            {"url": choice.url, "thumbnail": choice.thumbnail_url, "width": choice.width, "height": choice.height}
            for choice in self._choices
        ]

    @Property(str, notify=choicesChanged)
    def choicesKind(self) -> str:  # noqa: N802
        return self._choices_kind

    @Property(bool, notify=choicesChanged)
    def loadingChoices(self) -> bool:  # noqa: N802
        return self._loading_choices

    def open_game(self, game_id: str) -> None:
        self._game_id = game_id
        self._images = {}
        self._choices = ()
        self.stateChanged.emit()
        self.choicesChanged.emit()
        if game_id:
            start_task(self._load(game_id), self._prompts.error)

    async def _load(self, game_id: str) -> None:
        images = await game_artwork.get_game_artwork(game_id)
        if game_id == self._game_id:
            self._images = {image.kind: image for image in images}
            self._revision += 1
            self.stateChanged.emit()

    @Slot(str, QUrl)
    def choose_file(self, kind: str, url: QUrl) -> None:
        self._run(kind, self._use_file(kind, url.toLocalFile()))

    async def _use_file(self, kind: str, source: str) -> GameArtworkImage:
        path = await asyncio.to_thread(prepare_image, source, kind)
        try:
            return await game_artwork.set_custom_artwork(self._game_id, kind, path)
        finally:
            os.remove(path)

    @Slot(str)
    def reset(self, kind: str) -> None:
        self._run(kind, game_artwork.reset_artwork(self._game_id, kind))

    @Slot(str)
    def load_choices(self, kind: str) -> None:
        if self._game_id and not self._loading_choices:
            self._choices = ()
            self._choices_kind = kind
            self._loading_choices = True
            self.choicesChanged.emit()
            start_task(self._load_choices(self._game_id, kind), self._prompts.error)

    async def _load_choices(self, game_id: str, kind: str) -> None:
        try:
            choices = await game_artwork.list_steamgriddb_artwork(game_id, kind)
        finally:
            self._loading_choices = False
            self.choicesChanged.emit()
        if game_id == self._game_id and kind == self._choices_kind:
            self._choices = choices
            self.choicesChanged.emit()
            if not choices:
                self._prompts.notice(_("SteamGridDB has no artwork of this kind for this game."), rich=False)

    @Slot(str)
    def choose_url(self, url: str) -> None:
        if self._choices_kind:
            self._run(self._choices_kind, game_artwork.use_artwork_url(self._game_id, self._choices_kind, url))

    def _run(self, kind: str, operation: Coroutine[Any, Any, GameArtworkImage]) -> None:
        if not self._game_id or self._working:
            operation.close()
            return
        self._working = kind
        self.stateChanged.emit()
        start_task(self._apply(self._game_id, operation), self._prompts.error)

    async def _apply(self, game_id: str, operation: Coroutine[Any, Any, GameArtworkImage]) -> None:
        try:
            image = await operation
        finally:
            self._working = ""
            self.stateChanged.emit()
        if game_id == self._game_id:
            self._images[image.kind] = image
            self._revision += 1
            self.stateChanged.emit()
