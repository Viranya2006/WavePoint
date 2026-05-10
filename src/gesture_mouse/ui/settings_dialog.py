"""
WavePoint - Settings Dialog

Comprehensive settings panel for configuring all aspects of WavePoint.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QSlider, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox, QPushButton, QGroupBox, QFormLayout, QFrame,
    QMessageBox, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
import logging

from ..config import (
    Config, UserProfile, HandPreference,
    SmoothingSettings, GestureSettings, GestureEnableSettings, CameraSettings
)

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """
    Settings dialog with multiple tabs for different setting categories.
    """
    
    settings_changed = pyqtSignal()
    profile_changed = pyqtSignal(str)
    
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        
        self.config = config
        self._original_profile = config.current_profile.name
        
        self.setWindowTitle("WavePoint Settings")
        self.setMinimumSize(600, 500)
        
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Profile selector
        profile_layout = QHBoxLayout()
        profile_layout.addWidget(QLabel("Profile:"))
        
        self._profile_combo = QComboBox()
        self._profile_combo.currentTextChanged.connect(self._on_profile_changed)
        profile_layout.addWidget(self._profile_combo, stretch=1)
        
        self._new_profile_btn = QPushButton("New")
        self._new_profile_btn.clicked.connect(self._on_new_profile)
        profile_layout.addWidget(self._new_profile_btn)
        
        self._delete_profile_btn = QPushButton("Delete")
        self._delete_profile_btn.clicked.connect(self._on_delete_profile)
        profile_layout.addWidget(self._delete_profile_btn)
        
        layout.addLayout(profile_layout)
        
        # Tab widget
        self._tabs = QTabWidget()
        
        # General tab
        self._tabs.addTab(self._create_general_tab(), "General")
        
        # Cursor tab
        self._tabs.addTab(self._create_cursor_tab(), "Cursor")
        
        # Gestures tab
        self._tabs.addTab(self._create_gestures_tab(), "Gestures")
        
        # Camera tab
        self._tabs.addTab(self._create_camera_tab(), "Camera")
        
        # Advanced tab
        self._tabs.addTab(self._create_advanced_tab(), "Advanced")
        
        layout.addWidget(self._tabs)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self._reset_btn = QPushButton("Reset to Defaults")
        self._reset_btn.clicked.connect(self._on_reset)
        button_layout.addWidget(self._reset_btn)
        
        button_layout.addStretch()
        
        self._apply_btn = QPushButton("Apply")
        self._apply_btn.clicked.connect(self._on_apply)
        button_layout.addWidget(self._apply_btn)
        
        self._ok_btn = QPushButton("OK")
        self._ok_btn.clicked.connect(self._on_ok)
        button_layout.addWidget(self._ok_btn)
        
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_btn)
        
        layout.addLayout(button_layout)
    
    def _create_general_tab(self) -> QWidget:
        """Create the general settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Hand preference
        hand_group = QGroupBox("Hand Preference")
        hand_layout = QVBoxLayout(hand_group)
        
        self._right_hand_radio = QCheckBox("Right Hand")
        self._left_hand_radio = QCheckBox("Left Hand")
        
        self._right_hand_radio.toggled.connect(
            lambda checked: self._left_hand_radio.setChecked(not checked) if checked else None
        )
        self._left_hand_radio.toggled.connect(
            lambda checked: self._right_hand_radio.setChecked(not checked) if checked else None
        )
        
        hand_layout.addWidget(self._right_hand_radio)
        hand_layout.addWidget(self._left_hand_radio)
        
        layout.addWidget(hand_group)
        
        # Startup options
        startup_group = QGroupBox("Startup")
        startup_layout = QVBoxLayout(startup_group)
        
        self._start_minimized_check = QCheckBox("Start minimized to tray")
        self._test_mode_start_check = QCheckBox("Start in Test Mode (recommended)")
        self._show_notifications_check = QCheckBox("Show notifications")
        
        startup_layout.addWidget(self._start_minimized_check)
        startup_layout.addWidget(self._test_mode_start_check)
        startup_layout.addWidget(self._show_notifications_check)
        
        layout.addWidget(startup_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_cursor_tab(self) -> QWidget:
        """Create the cursor settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Smoothing settings
        smooth_group = QGroupBox("Cursor Smoothing")
        smooth_layout = QFormLayout(smooth_group)
        
        # Smoothing factor
        self._smoothing_slider = QSlider(Qt.Orientation.Horizontal)
        self._smoothing_slider.setRange(10, 90)
        self._smoothing_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._smoothing_slider.setTickInterval(10)
        smooth_layout.addRow("Smoothing (lower = smoother):", self._smoothing_slider)
        
        # Speed
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setRange(50, 200)
        self._speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._speed_slider.setTickInterval(25)
        smooth_layout.addRow("Cursor Speed:", self._speed_slider)
        
        # Acceleration
        self._accel_slider = QSlider(Qt.Orientation.Horizontal)
        self._accel_slider.setRange(100, 300)
        self._accel_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._accel_slider.setTickInterval(25)
        smooth_layout.addRow("Acceleration:", self._accel_slider)
        
        # Jitter threshold
        self._jitter_spin = QDoubleSpinBox()
        self._jitter_spin.setRange(0.5, 10.0)
        self._jitter_spin.setSingleStep(0.5)
        self._jitter_spin.setSuffix(" px")
        smooth_layout.addRow("Jitter Threshold:", self._jitter_spin)
        
        layout.addWidget(smooth_group)
        
        # Dead zone
        deadzone_group = QGroupBox("Dead Zone")
        deadzone_layout = QFormLayout(deadzone_group)
        
        self._deadzone_slider = QSlider(Qt.Orientation.Horizontal)
        self._deadzone_slider.setRange(0, 10)
        self._deadzone_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        deadzone_layout.addRow("Dead Zone Size:", self._deadzone_slider)
        
        layout.addWidget(deadzone_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_gestures_tab(self) -> QWidget:
        """Create the gestures settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Enable/disable gestures
        enable_group = QGroupBox("Enabled Gestures")
        enable_layout = QVBoxLayout(enable_group)
        
        self._enable_left_click = QCheckBox("Left Click (thumb + index pinch)")
        self._enable_right_click = QCheckBox("Right Click (thumb + middle pinch)")
        self._enable_scroll = QCheckBox("Scroll (two fingers vertical)")
        self._enable_drag = QCheckBox("Drag (closed fist)")
        
        enable_layout.addWidget(self._enable_left_click)
        enable_layout.addWidget(self._enable_right_click)
        enable_layout.addWidget(self._enable_scroll)
        enable_layout.addWidget(self._enable_drag)
        
        layout.addWidget(enable_group)
        
        # Timing settings
        timing_group = QGroupBox("Timing")
        timing_layout = QFormLayout(timing_group)
        
        self._dwell_click_spin = QSpinBox()
        self._dwell_click_spin.setRange(50, 500)
        self._dwell_click_spin.setSingleStep(25)
        self._dwell_click_spin.setSuffix(" ms")
        timing_layout.addRow("Click Dwell Time:", self._dwell_click_spin)
        
        self._dwell_drag_spin = QSpinBox()
        self._dwell_drag_spin.setRange(100, 1000)
        self._dwell_drag_spin.setSingleStep(50)
        self._dwell_drag_spin.setSuffix(" ms")
        timing_layout.addRow("Drag Dwell Time:", self._dwell_drag_spin)
        
        self._debounce_spin = QSpinBox()
        self._debounce_spin.setRange(100, 500)
        self._debounce_spin.setSingleStep(25)
        self._debounce_spin.setSuffix(" ms")
        timing_layout.addRow("Click Debounce:", self._debounce_spin)
        
        layout.addWidget(timing_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_camera_tab(self) -> QWidget:
        """Create the camera settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Camera selection
        camera_group = QGroupBox("Camera")
        camera_layout = QFormLayout(camera_group)
        
        self._camera_combo = QComboBox()
        self._camera_combo.addItems(["Camera 0", "Camera 1", "Camera 2"])
        camera_layout.addRow("Camera Device:", self._camera_combo)
        
        # Resolution
        self._resolution_combo = QComboBox()
        self._resolution_combo.addItems([
            "640x480 (Recommended)",
            "1280x720",
            "320x240 (Low CPU)"
        ])
        camera_layout.addRow("Resolution:", self._resolution_combo)
        
        # FPS
        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(15, 60)
        self._fps_spin.setSingleStep(5)
        self._fps_spin.setSuffix(" FPS")
        camera_layout.addRow("Target FPS:", self._fps_spin)
        
        layout.addWidget(camera_group)
        
        # Processing
        proc_group = QGroupBox("Processing")
        proc_layout = QVBoxLayout(proc_group)
        
        self._brightness_norm_check = QCheckBox("Brightness Normalization (for low light)")
        proc_layout.addWidget(self._brightness_norm_check)
        
        layout.addWidget(proc_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_advanced_tab(self) -> QWidget:
        """Create the advanced settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Confidence thresholds
        conf_group = QGroupBox("Confidence Thresholds")
        conf_layout = QFormLayout(conf_group)
        
        self._detection_conf_spin = QDoubleSpinBox()
        self._detection_conf_spin.setRange(0.3, 0.95)
        self._detection_conf_spin.setSingleStep(0.05)
        conf_layout.addRow("Detection Confidence:", self._detection_conf_spin)
        
        self._tracking_conf_spin = QDoubleSpinBox()
        self._tracking_conf_spin.setRange(0.3, 0.95)
        self._tracking_conf_spin.setSingleStep(0.05)
        conf_layout.addRow("Tracking Confidence:", self._tracking_conf_spin)
        
        self._gesture_conf_spin = QDoubleSpinBox()
        self._gesture_conf_spin.setRange(0.3, 0.95)
        self._gesture_conf_spin.setSingleStep(0.05)
        conf_layout.addRow("Gesture Confidence:", self._gesture_conf_spin)
        
        layout.addWidget(conf_group)
        
        # Pinch thresholds
        pinch_group = QGroupBox("Pinch Detection")
        pinch_layout = QFormLayout(pinch_group)
        
        self._pinch_thresh_spin = QDoubleSpinBox()
        self._pinch_thresh_spin.setRange(0.02, 0.10)
        self._pinch_thresh_spin.setSingleStep(0.01)
        self._pinch_thresh_spin.setDecimals(3)
        pinch_layout.addRow("Pinch Threshold:", self._pinch_thresh_spin)
        
        self._pinch_release_spin = QDoubleSpinBox()
        self._pinch_release_spin.setRange(0.04, 0.15)
        self._pinch_release_spin.setSingleStep(0.01)
        self._pinch_release_spin.setDecimals(3)
        pinch_layout.addRow("Pinch Release Threshold:", self._pinch_release_spin)
        
        layout.addWidget(pinch_group)
        
        # Safety
        safety_group = QGroupBox("Safety")
        safety_layout = QFormLayout(safety_group)
        
        self._tracking_timeout_spin = QSpinBox()
        self._tracking_timeout_spin.setRange(200, 2000)
        self._tracking_timeout_spin.setSingleStep(100)
        self._tracking_timeout_spin.setSuffix(" ms")
        safety_layout.addRow("Tracking Lost Timeout:", self._tracking_timeout_spin)
        
        layout.addWidget(safety_group)
        
        layout.addStretch()
        
        return widget
    
    def _load_settings(self):
        """Load current settings into UI."""
        # Update profile list
        self._profile_combo.clear()
        self._profile_combo.addItems(self.config.list_profiles())
        self._profile_combo.setCurrentText(self.config.current_profile.name)
        
        profile = self.config.current_profile
        
        # General
        self._right_hand_radio.setChecked(profile.hand_preference == HandPreference.RIGHT)
        self._left_hand_radio.setChecked(profile.hand_preference == HandPreference.LEFT)
        self._start_minimized_check.setChecked(self.config.app_settings.start_minimized)
        self._test_mode_start_check.setChecked(self.config.app_settings.test_mode_on_start)
        self._show_notifications_check.setChecked(self.config.app_settings.show_notifications)
        
        # Cursor
        self._smoothing_slider.setValue(int(profile.smoothing.alpha * 100))
        self._speed_slider.setValue(int(profile.smoothing.velocity_scale * 100))
        self._accel_slider.setValue(int(profile.smoothing.acceleration_factor * 100))
        self._jitter_spin.setValue(profile.smoothing.jitter_threshold)
        self._deadzone_slider.setValue(int(profile.calibration.dead_zone_radius * 100))
        
        # Gestures
        self._enable_left_click.setChecked(profile.gesture_enable.left_click)
        self._enable_right_click.setChecked(profile.gesture_enable.right_click)
        self._enable_scroll.setChecked(profile.gesture_enable.scroll)
        self._enable_drag.setChecked(profile.gesture_enable.drag)
        self._dwell_click_spin.setValue(profile.gestures.dwell_time_click_ms)
        self._dwell_drag_spin.setValue(profile.gestures.dwell_time_drag_ms)
        self._debounce_spin.setValue(profile.gestures.debounce_time_ms)
        
        # Camera
        self._camera_combo.setCurrentIndex(profile.camera.device_index)
        if profile.camera.width == 640:
            self._resolution_combo.setCurrentIndex(0)
        elif profile.camera.width == 1280:
            self._resolution_combo.setCurrentIndex(1)
        else:
            self._resolution_combo.setCurrentIndex(2)
        self._fps_spin.setValue(profile.camera.fps)
        self._brightness_norm_check.setChecked(profile.camera.brightness_normalization)
        
        # Advanced
        self._detection_conf_spin.setValue(profile.gestures.min_detection_confidence)
        self._tracking_conf_spin.setValue(profile.gestures.min_tracking_confidence)
        self._gesture_conf_spin.setValue(profile.gestures.min_gesture_confidence)
        self._pinch_thresh_spin.setValue(profile.gestures.pinch_threshold)
        self._pinch_release_spin.setValue(profile.gestures.pinch_release_threshold)
        self._tracking_timeout_spin.setValue(profile.gestures.tracking_lost_timeout_ms)
        
        # Update delete button state
        self._delete_profile_btn.setEnabled(profile.name != "Default")
    
    def _save_settings(self):
        """Save UI settings to config."""
        profile = self.config.current_profile
        
        # General
        profile.hand_preference = (
            HandPreference.RIGHT if self._right_hand_radio.isChecked() 
            else HandPreference.LEFT
        )
        self.config.app_settings.start_minimized = self._start_minimized_check.isChecked()
        self.config.app_settings.test_mode_on_start = self._test_mode_start_check.isChecked()
        self.config.app_settings.show_notifications = self._show_notifications_check.isChecked()
        
        # Cursor
        profile.smoothing.alpha = self._smoothing_slider.value() / 100.0
        profile.smoothing.velocity_scale = self._speed_slider.value() / 100.0
        profile.smoothing.acceleration_factor = self._accel_slider.value() / 100.0
        profile.smoothing.jitter_threshold = self._jitter_spin.value()
        profile.calibration.dead_zone_radius = self._deadzone_slider.value() / 100.0
        
        # Gestures
        profile.gesture_enable.left_click = self._enable_left_click.isChecked()
        profile.gesture_enable.right_click = self._enable_right_click.isChecked()
        profile.gesture_enable.scroll = self._enable_scroll.isChecked()
        profile.gesture_enable.drag = self._enable_drag.isChecked()
        profile.gestures.dwell_time_click_ms = self._dwell_click_spin.value()
        profile.gestures.dwell_time_drag_ms = self._dwell_drag_spin.value()
        profile.gestures.debounce_time_ms = self._debounce_spin.value()
        
        # Camera
        profile.camera.device_index = self._camera_combo.currentIndex()
        res_index = self._resolution_combo.currentIndex()
        if res_index == 0:
            profile.camera.width, profile.camera.height = 640, 480
        elif res_index == 1:
            profile.camera.width, profile.camera.height = 1280, 720
        else:
            profile.camera.width, profile.camera.height = 320, 240
        profile.camera.fps = self._fps_spin.value()
        profile.camera.brightness_normalization = self._brightness_norm_check.isChecked()
        
        # Advanced
        profile.gestures.min_detection_confidence = self._detection_conf_spin.value()
        profile.gestures.min_tracking_confidence = self._tracking_conf_spin.value()
        profile.gestures.min_gesture_confidence = self._gesture_conf_spin.value()
        profile.gestures.pinch_threshold = self._pinch_thresh_spin.value()
        profile.gestures.pinch_release_threshold = self._pinch_release_spin.value()
        profile.gestures.tracking_lost_timeout_ms = self._tracking_timeout_spin.value()
        
        # Save to disk
        self.config.save()
    
    def _on_profile_changed(self, name: str):
        """Handle profile selection change."""
        if name and name != self.config.current_profile.name:
            self.config.set_current_profile(name)
            self._load_settings()
            self.profile_changed.emit(name)
    
    def _on_new_profile(self):
        """Create a new profile."""
        from PyQt6.QtWidgets import QInputDialog
        
        name, ok = QInputDialog.getText(
            self, "New Profile", "Profile name:"
        )
        
        if ok and name:
            if name in self.config.list_profiles():
                QMessageBox.warning(
                    self, "Error", f"Profile '{name}' already exists."
                )
                return
            
            self.config.create_profile(name, self.config.current_profile.name)
            self.config.set_current_profile(name)
            self._load_settings()
    
    def _on_delete_profile(self):
        """Delete current profile."""
        name = self.config.current_profile.name
        
        if name == "Default":
            QMessageBox.warning(
                self, "Error", "Cannot delete the Default profile."
            )
            return
        
        reply = QMessageBox.question(
            self, "Delete Profile",
            f"Are you sure you want to delete profile '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.config.delete_profile(name)
            self._load_settings()
    
    def _on_reset(self):
        """Reset to default settings."""
        reply = QMessageBox.question(
            self, "Reset Settings",
            "Reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Create fresh profile with same name
            name = self.config.current_profile.name
            self.config.profiles[name] = UserProfile(name=name)
            self.config.current_profile = self.config.profiles[name]
            self._load_settings()
    
    def _on_apply(self):
        """Apply settings without closing."""
        self._save_settings()
        self.settings_changed.emit()
    
    def _on_ok(self):
        """Apply settings and close."""
        self._save_settings()
        self.settings_changed.emit()
        self.accept()
