"""
WavePoint - Main Window

Primary application window with status display and quick controls.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGroupBox, QStatusBar, QMenuBar,
    QMenu, QTabWidget
)
from PyQt6.QtGui import QFont, QAction, QCloseEvent
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
import logging

from .test_mode_widget import TestModeWidget
from .settings_dialog import SettingsDialog
from .calibration_dialog import CalibrationDialog

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    Main application window.

    Provides:
    - Status overview
    - Quick enable/disable
    - Access to test mode, calibration, settings
    """

    # Signals
    enable_requested = pyqtSignal(bool)
    close_to_tray = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("WavePoint")
        self.setMinimumSize(900, 700)

        # State
        self._enabled = False
        self._tracking = False
        self._fps = 0.0
        self._gesture = "None"
        self._confidence = 0.0

        # References (set by app)
        self._config = None
        self._tracker = None
        self._test_mode = None

        self._setup_ui()
        self._setup_menu()

        # Update timer for status
        self._status_timer = QTimer()
        self._status_timer.timeout.connect(self._update_status)

        # Frame update timer for test mode
        self._frame_timer = QTimer()
        self._frame_timer.timeout.connect(self._update_test_frame)

    def _setup_ui(self):
        """Setup the user interface."""
        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("WavePoint")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Status indicator
        self._status_indicator = QLabel("● Disabled")
        self._status_indicator.setFont(QFont("Segoe UI", 14))
        self._status_indicator.setStyleSheet("color: #888;")
        header_layout.addWidget(self._status_indicator)

        layout.addLayout(header_layout)

        # Main control area
        control_frame = QFrame()
        control_frame.setFrameStyle(
            QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        control_layout = QHBoxLayout(control_frame)
        control_layout.setSpacing(20)

        # Enable/Disable button
        self._toggle_btn = QPushButton("Enable Mouse Control")
        self._toggle_btn.setMinimumSize(200, 60)
        self._toggle_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self._toggle_btn.clicked.connect(self._on_toggle)
        control_layout.addWidget(self._toggle_btn)

        # Quick stats
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        stats_layout.setSpacing(5)

        self._gesture_label = QLabel("Gesture: None")
        self._gesture_label.setFont(QFont("Segoe UI", 11))
        stats_layout.addWidget(self._gesture_label)

        self._confidence_label = QLabel("Confidence: 0%")
        self._confidence_label.setFont(QFont("Segoe UI", 11))
        stats_layout.addWidget(self._confidence_label)

        self._fps_label = QLabel("FPS: 0")
        self._fps_label.setFont(QFont("Segoe UI", 11))
        stats_layout.addWidget(self._fps_label)

        control_layout.addWidget(stats_widget)
        control_layout.addStretch()

        layout.addWidget(control_frame)

        # Tab widget for different views
        self._tabs = QTabWidget()

        # Test mode tab
        self._test_widget = TestModeWidget()
        self._test_widget.start_requested.connect(self._on_test_start)
        self._test_widget.stop_requested.connect(self._on_test_stop)
        self._test_widget.enable_control_requested.connect(
            self._on_enable_from_test)
        self._tabs.addTab(self._test_widget, "Test Mode")

        # Status tab
        self._tabs.addTab(self._create_status_tab(), "Status")

        # Help tab
        self._tabs.addTab(self._create_help_tab(), "Help")

        layout.addWidget(self._tabs)

        # Quick action buttons
        action_layout = QHBoxLayout()

        self._calibrate_btn = QPushButton("Calibrate")
        self._calibrate_btn.setMinimumHeight(40)
        self._calibrate_btn.clicked.connect(self._on_calibrate)
        action_layout.addWidget(self._calibrate_btn)

        self._settings_btn = QPushButton("Settings")
        self._settings_btn.setMinimumHeight(40)
        self._settings_btn.clicked.connect(self._on_settings)
        action_layout.addWidget(self._settings_btn)

        action_layout.addStretch()

        layout.addLayout(action_layout)

        # Status bar
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage(
            "Ready - Start in Test Mode to verify setup")

    def _setup_menu(self):
        """Setup the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        settings_action = QAction("&Settings...", self)
        settings_action.triggered.connect(self._on_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        minimize_action = QAction("&Minimize to Tray", self)
        minimize_action.triggered.connect(self._minimize_to_tray)
        file_menu.addAction(minimize_action)

        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self._on_exit)
        file_menu.addAction(exit_action)

        # Control menu
        control_menu = menubar.addMenu("&Control")

        self._enable_action = QAction("&Enable Mouse Control", self)
        self._enable_action.setCheckable(True)
        self._enable_action.triggered.connect(self._on_toggle)
        control_menu.addAction(self._enable_action)

        control_menu.addSeparator()

        test_action = QAction("&Test Mode", self)
        test_action.triggered.connect(lambda: self._tabs.setCurrentIndex(0))
        control_menu.addAction(test_action)

        calibrate_action = QAction("&Calibrate...", self)
        calibrate_action.triggered.connect(self._on_calibrate)
        control_menu.addAction(calibrate_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _create_status_tab(self) -> QWidget:
        """Create the status tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Performance group
        perf_group = QGroupBox("Performance")
        perf_layout = QVBoxLayout(perf_group)

        self._perf_fps_label = QLabel("FPS: --")
        self._perf_frame_time_label = QLabel("Frame Time: -- ms")
        self._perf_dropped_label = QLabel("Dropped Frames: 0")
        self._perf_detection_label = QLabel("Detection Rate: --%")

        perf_layout.addWidget(self._perf_fps_label)
        perf_layout.addWidget(self._perf_frame_time_label)
        perf_layout.addWidget(self._perf_dropped_label)
        perf_layout.addWidget(self._perf_detection_label)

        layout.addWidget(perf_group)

        # System group
        sys_group = QGroupBox("System")
        sys_layout = QVBoxLayout(sys_group)

        self._sys_camera_label = QLabel("Camera: Not initialized")
        self._sys_engine_label = QLabel("Engine: Not initialized")
        self._sys_profile_label = QLabel("Profile: Default")

        sys_layout.addWidget(self._sys_camera_label)
        sys_layout.addWidget(self._sys_engine_label)
        sys_layout.addWidget(self._sys_profile_label)

        layout.addWidget(sys_group)

        layout.addStretch()

        return widget

    def _create_help_tab(self) -> QWidget:
        """Create the help tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        help_text = QLabel("""
<h2>Gesture Guide</h2>

<p><b>Pointing (Index Finger)</b><br>
Extend your index finger while curling other fingers.<br>
The cursor will follow your fingertip.</p>

<p><b>Left Click (Pinch)</b><br>
Touch your thumb to your index fingertip.<br>
Hold briefly to confirm the click.</p>

<p><b>Right Click</b><br>
Touch your thumb to your middle fingertip.</p>

<p><b>Scroll</b><br>
Extend index and middle fingers together.<br>
Move up/down to scroll.</p>

<p><b>Drag</b><br>
Make a fist to start dragging.<br>
Open your hand to release.</p>

<p><b>Pause/Neutral</b><br>
Open palm with all fingers extended.<br>
Cursor moves but no actions are triggered.</p>

<h2>Tips</h2>
<ul>
<li>Ensure good, even lighting on your hand</li>
<li>Avoid busy backgrounds</li>
<li>Keep your hand within the camera frame</li>
<li>Move smoothly - avoid jerky movements</li>
<li>Calibrate for best accuracy</li>
</ul>
        """)
        help_text.setWordWrap(True)
        help_text.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(help_text)

        layout.addStretch()

        return widget

    def set_config(self, config):
        """Set configuration reference."""
        self._config = config
        self._sys_profile_label.setText(
            f"Profile: {config.current_profile.name}")

    def set_tracker(self, tracker):
        """Set hand tracker reference."""
        self._tracker = tracker

    def set_test_mode(self, test_mode):
        """Set test mode reference."""
        self._test_mode = test_mode

    def _on_toggle(self):
        """Handle enable/disable toggle."""
        self._enabled = not self._enabled
        self.enable_requested.emit(self._enabled)
        self._update_toggle_button()

    def _update_toggle_button(self):
        """Update toggle button appearance."""
        if self._enabled:
            self._toggle_btn.setText("Disable Mouse Control")
            self._toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
            """)
            self._status_indicator.setText("● Enabled")
            self._status_indicator.setStyleSheet("color: #4CAF50;")
        else:
            self._toggle_btn.setText("Enable Mouse Control")
            self._toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            self._status_indicator.setText("● Disabled")
            self._status_indicator.setStyleSheet("color: #888;")

        self._enable_action.setChecked(self._enabled)

    def set_enabled(self, enabled: bool):
        """Set enabled state from external source."""
        self._enabled = enabled
        self._update_toggle_button()

    def set_tracking(self, tracking: bool):
        """Update tracking state."""
        self._tracking = tracking
        if tracking:
            self._status_indicator.setText("● Tracking")
            self._status_indicator.setStyleSheet("color: #2196F3;")
        elif self._enabled:
            self._status_indicator.setText("● Enabled (No Hand)")
            self._status_indicator.setStyleSheet("color: #4CAF50;")

    def update_stats(self, gesture: str, confidence: float, fps: float):
        """Update displayed statistics."""
        self._gesture = gesture
        self._confidence = confidence
        self._fps = fps

        self._gesture_label.setText(f"Gesture: {gesture}")
        self._confidence_label.setText(f"Confidence: {confidence:.0%}")
        self._fps_label.setText(f"FPS: {fps:.1f}")

        self._perf_fps_label.setText(f"FPS: {fps:.1f}")
        self._perf_frame_time_label.setText(
            f"Frame Time: {1000/fps:.1f} ms" if fps > 0 else "Frame Time: -- ms")

    def _update_status(self):
        """Periodic status update."""
        if self._tracker and self._tracker.is_running:
            self._perf_dropped_label.setText(
                f"Dropped Frames: {self._tracker.dropped_frames}")
            det_rate = 1.0 - self._tracker.drop_rate
            self._perf_detection_label.setText(
                f"Detection Rate: {det_rate:.0%}")

    def _on_test_start(self):
        """Handle test mode start request."""
        if self._test_mode:
            self._test_mode.start()
            self._test_widget.set_running(True)
            self._status_timer.start(100)
            self._frame_timer.start(33)  # ~30 FPS for camera preview
            self._statusbar.showMessage(
                "Test Mode active - verify your gestures")

    def _on_test_stop(self):
        """Handle test mode stop request."""
        if self._test_mode:
            self._test_mode.stop()
            self._test_widget.set_running(False)
            self._status_timer.stop()
            self._frame_timer.stop()

            # Show recommendations
            recommendations = self._test_mode.get_recommendations()
            self._test_widget.update_recommendations(recommendations)
            self._statusbar.showMessage("Test Mode stopped")

    def _on_enable_from_test(self):
        """Handle enable request from test mode."""
        self._on_test_stop()
        self._enabled = True
        self.enable_requested.emit(True)
        self._update_toggle_button()
        self._statusbar.showMessage("Mouse control enabled")

    def _on_calibrate(self):
        """Open calibration dialog."""
        if not self._tracker:
            logger.error("Tracker not set")
            return

        dialog = CalibrationDialog(self._tracker, self)
        dialog.calibration_complete.connect(self._on_calibration_complete)
        dialog.exec()

    def _on_calibration_complete(self, calibration):
        """Handle calibration completion."""
        if self._config:
            self._config.update_calibration(calibration)
            self._statusbar.showMessage("Calibration saved")

    def _on_settings(self):
        """Open settings dialog."""
        if not self._config:
            logger.error("Config not set")
            return

        dialog = SettingsDialog(self._config, self)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec()

    def _on_settings_changed(self):
        """Handle settings change."""
        self._sys_profile_label.setText(
            f"Profile: {self._config.current_profile.name}")
        self._statusbar.showMessage("Settings updated")

    def _minimize_to_tray(self):
        """Minimize to system tray."""
        self.hide()
        self.close_to_tray.emit()

    def _on_exit(self):
        """Exit application."""
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    def _on_about(self):
        """Show about dialog."""
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.about(
            self,
            "About WavePoint",
            "WavePoint v1.0.0\n\n"
            "Control your computer using hand gestures.\n\n"
            "A production-grade accessibility tool for Windows.\n\n"
            "• No cloud connectivity\n"
            "• No data collection\n"
            "• All processing is local"
        )

    def closeEvent(self, event: QCloseEvent):
        """Handle window close - minimize to tray instead."""
        event.ignore()
        self._minimize_to_tray()

    def update_test_frame(self, frame, info):
        """Update test mode display (called externally)."""
        self._test_widget.update_frame(frame)
        self._test_widget.update_info(info)

    def _update_test_frame(self):
        """Timer callback to process and display test mode frames."""
        if not self._test_mode or not self._test_mode._running:
            return

        result = self._test_mode.process_frame()
        if result is not None:
            frame, info = result
            self._test_widget.update_frame(frame)
            self._test_widget.update_info(info)
