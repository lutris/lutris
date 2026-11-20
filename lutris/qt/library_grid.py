"""The library's artwork grid, backed by the same model as the table."""

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QRect, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QImageReader, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QListView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionFocusRect,
    QStyleOptionViewItem,
)

from lutris.backend.models import LibraryArtwork
from lutris.qt.library_model import AnyIndex, GameRole
from lutris.util import datapath

COVER_SIZE = QSize(144, 192)
BANNER_SIZE = QSize(208, 96)
CARD_PADDING = 8


@lru_cache(maxsize=256)
def _thumbnail(path: str, width: int, height: int, scale: float) -> QPixmap:
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid():
        reader.setScaledSize(
            size.scaled(QSize(round(width * scale), round(height * scale)), Qt.AspectRatioMode.KeepAspectRatio)
        )
    pixmap = QPixmap.fromImage(reader.read())
    pixmap.setDevicePixelRatio(scale)
    return pixmap


class ArtworkDelegate(QStyledItemDelegate):
    def __init__(self, parent: QListView) -> None:
        super().__init__(parent)
        self.banners = False
        self.placeholder = QIcon(str(Path(datapath.get()) / "media" / "default_icon.png"))

    @property
    def artwork_size(self) -> QSize:
        return BANNER_SIZE if self.banners else COVER_SIZE

    def sizeHint(self, option: QStyleOptionViewItem, index: AnyIndex) -> QSize:  # noqa: N802
        return self.artwork_size + QSize(4 * CARD_PADDING, 3 * CARD_PADDING + 2 * option.fontMetrics.lineSpacing())

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: AnyIndex) -> None:
        game = index.data(GameRole)
        if game is None:
            return

        state = option.state
        selected = bool(state & QStyle.StateFlag.State_Selected)
        palette = option.palette
        group = QPalette.ColorGroup.Active if state & QStyle.StateFlag.State_Active else QPalette.ColorGroup.Inactive
        background = QPalette.ColorRole.Highlight if selected else QPalette.ColorRole.AlternateBase
        foreground = QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
        card = option.rect.adjusted(CARD_PADDING // 2, CARD_PADDING // 2, -CARD_PADDING // 2, -CARD_PADDING // 2)
        art = QRect(card.topLeft(), self.artwork_size)
        art.moveTop(card.top() + CARD_PADDING)
        art.moveLeft(card.center().x() - art.width() // 2)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(palette.brush(group, background))
        painter.drawRoundedRect(QRectF(card), 6, 6)
        self.paint_artwork(painter, art, game.artwork)

        painter.setPen(palette.color(group, foreground))
        font = option.font
        font.setBold(index.data(Qt.ItemDataRole.FontRole) is not None)
        painter.setFont(font)
        lines = painter.fontMetrics()
        text = QRect(art.left(), art.bottom() + 5, art.width(), lines.lineSpacing())
        painter.drawText(
            text, Qt.AlignmentFlag.AlignCenter, lines.elidedText(game.name, Qt.TextElideMode.ElideRight, text.width())
        )
        if status := index.data(Qt.ItemDataRole.AccessibleDescriptionRole):
            painter.setFont(option.font)
            text.translate(0, text.height())
            status = painter.fontMetrics().elidedText(status, Qt.TextElideMode.ElideRight, text.width())
            painter.drawText(text, Qt.AlignmentFlag.AlignCenter, status)

        if state & QStyle.StateFlag.State_HasFocus:
            focus = QStyleOptionFocusRect()
            focus.rect = card.adjusted(1, 1, -1, -1)
            focus.state = state | QStyle.StateFlag.State_KeyboardFocusChange
            focus.palette = palette
            focus.backgroundColor = palette.color(group, background)
            style = option.widget.style() if option.widget else QApplication.style()
            style.drawPrimitive(QStyle.PrimitiveElement.PE_FrameFocusRect, focus, painter, option.widget)
        painter.restore()

    def paint_artwork(self, painter: QPainter, area: QRect, artwork: LibraryArtwork | None) -> None:
        icon_area = QRect(0, 0, 48, 48)
        icon_area.moveCenter(area.center())
        if artwork:
            images = (
                (artwork.banner_path, artwork.cover_path) if self.banners else (artwork.cover_path, artwork.banner_path)
            )
            device = painter.device()
            scale = device.devicePixelRatioF() if device else 1.0
            for path in images:
                if path and self.paint_image(painter, area, path, scale):
                    return

            if artwork.icon_path and self.paint_image(painter, icon_area, artwork.icon_path, scale):
                return

        icon = (
            QIcon.fromTheme(artwork.icon_name, self.placeholder) if artwork and artwork.icon_name else self.placeholder
        )
        icon.paint(painter, icon_area)

    @staticmethod
    def paint_image(painter: QPainter, area: QRect, path: str, scale: float) -> bool:
        pixmap = _thumbnail(path, area.width(), area.height(), scale)
        if pixmap.isNull():
            return False
        target = QRectF(QRect(0, 0, area.width(), area.height()))
        target.setSize(pixmap.deviceIndependentSize().scaled(target.size(), Qt.AspectRatioMode.KeepAspectRatio))
        target.moveCenter(QRectF(area).center())
        painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
        return True


class LibraryGrid(QListView):
    def __init__(self) -> None:
        super().__init__()
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setMovement(QListView.Movement.Static)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setLayoutMode(QListView.LayoutMode.Batched)
        self.setUniformItemSizes(True)
        self.setSelectionBehavior(QListView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self._artwork_delegate = ArtworkDelegate(self)
        self.setItemDelegate(self._artwork_delegate)

    def set_banners(self, banners: bool) -> None:
        self._artwork_delegate.banners = banners
        self.doItemsLayout()
        self.viewport().update()

    def invalidate_artwork(self) -> None:
        _thumbnail.cache_clear()
        self.viewport().update()
