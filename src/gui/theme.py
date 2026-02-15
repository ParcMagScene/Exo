"""theme.py — Palette de couleurs et constantes visuelles EXO.

Thème bleu / violet / azure avec support mode sombre.
"""

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QColor


class ExoTheme(QObject):
    """Expose la palette de couleurs au QML."""

    themeChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dark = True  # Mode sombre par défaut

    # ─── Couleurs principales ─────────────────────────────

    @Property(QColor, notify=themeChanged)
    def background(self):
        return QColor("#0a0e1a") if self._dark else QColor("#f0f4ff")

    @Property(QColor, notify=themeChanged)
    def surface(self):
        return QColor("#111827") if self._dark else QColor("#ffffff")

    @Property(QColor, notify=themeChanged)
    def surfaceVariant(self):
        return QColor("#1a2234") if self._dark else QColor("#e8edf5")

    @Property(QColor, notify=themeChanged)
    def card(self):
        return QColor("#1e293b") if self._dark else QColor("#ffffff")

    @Property(QColor, notify=themeChanged)
    def cardHover(self):
        return QColor("#263148") if self._dark else QColor("#f0f4ff")

    # ─── Accents ──────────────────────────────────────────

    @Property(QColor, notify=themeChanged)
    def primary(self):
        """Bleu principal."""
        return QColor("#3b82f6")

    @Property(QColor, notify=themeChanged)
    def primaryLight(self):
        return QColor("#60a5fa")

    @Property(QColor, notify=themeChanged)
    def secondary(self):
        """Violet accent."""
        return QColor("#8b5cf6")

    @Property(QColor, notify=themeChanged)
    def secondaryLight(self):
        return QColor("#a78bfa")

    @Property(QColor, notify=themeChanged)
    def accent(self):
        """Azure / cyan."""
        return QColor("#06b6d4")

    @Property(QColor, notify=themeChanged)
    def accentLight(self):
        return QColor("#22d3ee")

    # ─── États ────────────────────────────────────────────

    @Property(QColor, notify=themeChanged)
    def success(self):
        return QColor("#22c55e")

    @Property(QColor, notify=themeChanged)
    def warning(self):
        return QColor("#f59e0b")

    @Property(QColor, notify=themeChanged)
    def error(self):
        return QColor("#ef4444")

    # ─── Texte ────────────────────────────────────────────

    @Property(QColor, notify=themeChanged)
    def textPrimary(self):
        return QColor("#f1f5f9") if self._dark else QColor("#0f172a")

    @Property(QColor, notify=themeChanged)
    def textSecondary(self):
        return QColor("#94a3b8") if self._dark else QColor("#64748b")

    @Property(QColor, notify=themeChanged)
    def textMuted(self):
        return QColor("#475569") if self._dark else QColor("#94a3b8")

    # ─── Orbe d'état ──────────────────────────────────────

    @Property(QColor, notify=themeChanged)
    def orbIdle(self):
        return QColor("#1e3a5f")

    @Property(QColor, notify=themeChanged)
    def orbListening(self):
        return QColor("#7c3aed")

    @Property(QColor, notify=themeChanged)
    def orbProcessing(self):
        return QColor("#0ea5e9")

    @Property(QColor, notify=themeChanged)
    def orbResponding(self):
        return QColor("#6366f1")

    # ─── Dimensions ───────────────────────────────────────

    @Property(int, notify=themeChanged)
    def radiusSmall(self):
        return 8

    @Property(int, notify=themeChanged)
    def radiusMedium(self):
        return 12

    @Property(int, notify=themeChanged)
    def radiusLarge(self):
        return 20

    @Property(int, notify=themeChanged)
    def navRailWidth(self):
        return 72

    @Property(int, notify=themeChanged)
    def topBarHeight(self):
        return 56

    # ─── API ──────────────────────────────────────────────

    @Property(bool, notify=themeChanged)
    def isDark(self):
        return self._dark

    @Slot()
    def toggleTheme(self):
        self._dark = not self._dark
        self.themeChanged.emit()
