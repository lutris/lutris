"""Let QML look up strings in the application's existing gettext catalogs."""

from gettext import gettext as _

from PySide6.QtCore import QTranslator


class QmlTranslator(QTranslator):
    def isEmpty(self) -> bool:  # noqa: N802
        return False

    def translate(self, context: str, sourceText: str, disambiguation: str | None = None, n: int = -1) -> str:
        return _(sourceText)
