"""
WavePoint - System Tray Icon

Windows system tray application for quick access to WavePoint controls.
"""

from PyQt6.QtWidgets import (
    QSystemTrayIcon, QMenu, QApplication
)
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QBrush
from PyQt6.QtCore import pyqtSignal, QObject
import logging

logger = logging.getLogger(__name__)


class TrayIcon(QObject):
    """
    System tray icon with context menu.
    
    Provides quick access to:
    - Enable/Disable toggle
    - Test Mode
    - Settings
    - Exit
    """
    
    # Signals
    toggle_requested = pyqtSignal(bool)  # True = enable, False = disable
    test_mode_requested = pyqtSignal()
    calibration_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    show_window_requested = pyqtSignal()
    exit_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._enabled = False
        self._tracking = False
        
        # Create tray icon
        self._tray = QSystemTrayIcon(parent)
        self._tray.setToolTip("WavePoint - Disabled")
        
        # Create icons
        self._icon_disabled = self._create_icon(QColor(128, 128, 128))
        self._icon_enabled = self._create_icon(QColor(0, 200, 0))
        self._icon_tracking = self._create_icon(QColor(0, 150, 255))
        self._icon_error = self._create_icon(QColor(255, 0, 0))
        
        self._tray.setIcon(self._icon_disabled)
        
        # Create context menu
        self._menu = QMenu()
        self._create_menu()
        self._tray.setContextMenu(self._menu)
        
        # Connect signals
        self._tray.activated.connect(self._on_activated)
    
    def _create_icon(self, color: QColor) -> QIcon:
        """Create a simple colored icon."""
        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))  # Transparent background
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw hand shape (simplified)
        painter.setBrush(QBrush(color))
        painter.setPen(color.darker(120))
        
        # Draw palm circle
        painter.drawEllipse(12, 20, 40, 40)
        
        # Draw fingers (simplified rectangles)
        finger_width = 8
        painter.drawRoundedRect(8, 5, finger_width, 25, 3, 3)   # Index
        painter.drawRoundedRect(20, 2, finger_width, 28, 3, 3)  # Middle
        painter.drawRoundedRect(32, 5, finger_width, 25, 3, 3)  # Ring
        painter.drawRoundedRect(44, 12, finger_width, 20, 3, 3) # Pinky
        
        # Draw thumb
        painter.drawRoundedRect(2, 30, 18, finger_width, 3, 3)
        
        painter.end()
        
        return QIcon(pixmap)
    
    def _create_menu(self):
        """Create the context menu."""
        # Status display (non-clickable)
        self._status_action = QAction("Status: Disabled", self._menu)
        self._status_action.setEnabled(False)
        self._menu.addAction(self._status_action)
        
        self._menu.addSeparator()
        
        # Enable/Disable toggle
        self._toggle_action = QAction("Enable Control", self._menu)
        self._toggle_action.setCheckable(True)
        self._toggle_action.triggered.connect(self._on_toggle)
        self._menu.addAction(self._toggle_action)
        
        self._menu.addSeparator()
        
        # Test Mode
        self._test_action = QAction("Test Mode...", self._menu)
        self._test_action.triggered.connect(lambda: self.test_mode_requested.emit())
        self._menu.addAction(self._test_action)
        
        # Calibration
        self._calibrate_action = QAction("Calibrate...", self._menu)
        self._calibrate_action.triggered.connect(lambda: self.calibration_requested.emit())
        self._menu.addAction(self._calibrate_action)
        
        # Settings
        self._settings_action = QAction("Settings...", self._menu)
        self._settings_action.triggered.connect(lambda: self.settings_requested.emit())
        self._menu.addAction(self._settings_action)
        
        self._menu.addSeparator()
        
        # Show main window
        self._show_action = QAction("Show Window", self._menu)
        self._show_action.triggered.connect(lambda: self.show_window_requested.emit())
        self._menu.addAction(self._show_action)
        
        self._menu.addSeparator()
        
        # Exit
        self._exit_action = QAction("Exit", self._menu)
        self._exit_action.triggered.connect(lambda: self.exit_requested.emit())
        self._menu.addAction(self._exit_action)
    
    def _on_activated(self, reason):
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window_requested.emit()
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Single click - toggle on some systems
            pass
    
    def _on_toggle(self, checked: bool):
        """Handle enable/disable toggle."""
        self.toggle_requested.emit(checked)
    
    def show(self):
        """Show the tray icon."""
        self._tray.show()
    
    def hide(self):
        """Hide the tray icon."""
        self._tray.hide()
    
    def set_enabled(self, enabled: bool):
        """Update enabled state."""
        self._enabled = enabled
        self._toggle_action.setChecked(enabled)
        self._update_status()
    
    def set_tracking(self, tracking: bool):
        """Update tracking state."""
        self._tracking = tracking
        self._update_status()
    
    def set_error(self, has_error: bool):
        """Update error state."""
        if has_error:
            self._tray.setIcon(self._icon_error)
            self._status_action.setText("Status: Error")
            self._tray.setToolTip("WavePoint - Error")
        else:
            self._update_status()
    
    def _update_status(self):
        """Update icon and status text based on current state."""
        if self._enabled:
            if self._tracking:
                self._tray.setIcon(self._icon_tracking)
                self._status_action.setText("Status: Tracking")
                self._tray.setToolTip("WavePoint - Tracking")
            else:
                self._tray.setIcon(self._icon_enabled)
                self._status_action.setText("Status: Enabled (No Hand)")
                self._tray.setToolTip("WavePoint - Enabled")
            self._toggle_action.setText("Disable Control")
        else:
            self._tray.setIcon(self._icon_disabled)
            self._status_action.setText("Status: Disabled")
            self._tray.setToolTip("WavePoint - Disabled")
            self._toggle_action.setText("Enable Control")
    
    def show_message(self, title: str, message: str, icon=QSystemTrayIcon.MessageIcon.Information):
        """Show a balloon notification."""
        self._tray.showMessage(title, message, icon, 3000)
    
    def show_notification(self, message: str):
        """Show a simple notification."""
        self.show_message("WavePoint", message)
