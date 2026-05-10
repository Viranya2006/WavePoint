"""
WavePoint - Test Mode Widget

PyQt6 widget for displaying test mode camera preview and gesture information.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar, QGroupBox, QTextEdit
)
from PyQt6.QtGui import QImage, QPixmap, QFont
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
import numpy as np
import logging

logger = logging.getLogger(__name__)


class TestModeWidget(QWidget):
    """
    Widget for test mode display.
    
    Shows:
    - Camera preview with landmarks
    - Current gesture
    - Confidence score
    - FPS
    - Recommendations
    """
    
    # Signals
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    enable_control_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._is_running = False
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Title
        title = QLabel("Test Mode")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("Verify gesture detection without mouse control")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #666;")
        layout.addWidget(subtitle)
        
        # Main content area
        content_layout = QHBoxLayout()
        
        # Camera preview
        preview_frame = QFrame()
        preview_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        preview_frame.setMinimumSize(640, 480)
        preview_layout = QVBoxLayout(preview_frame)
        
        self._preview_label = QLabel("Camera Preview")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setMinimumSize(640, 480)
        self._preview_label.setStyleSheet("background-color: #1a1a1a; color: #666;")
        preview_layout.addWidget(self._preview_label)
        
        content_layout.addWidget(preview_frame, stretch=2)
        
        # Info panel
        info_panel = QWidget()
        info_layout = QVBoxLayout(info_panel)
        info_layout.setSpacing(15)
        
        # Gesture info group
        gesture_group = QGroupBox("Current Gesture")
        gesture_layout = QVBoxLayout(gesture_group)
        
        self._gesture_label = QLabel("None")
        self._gesture_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._gesture_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gesture_layout.addWidget(self._gesture_label)
        
        # Confidence bar
        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("Confidence:"))
        self._confidence_bar = QProgressBar()
        self._confidence_bar.setRange(0, 100)
        self._confidence_bar.setValue(0)
        self._confidence_bar.setTextVisible(True)
        self._confidence_bar.setFormat("%v%")
        conf_layout.addWidget(self._confidence_bar)
        gesture_layout.addLayout(conf_layout)
        
        info_layout.addWidget(gesture_group)
        
        # Stats group
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self._fps_label = QLabel("FPS: --")
        self._detection_label = QLabel("Detection Rate: --")
        self._hand_label = QLabel("Hand: --")
        
        stats_layout.addWidget(self._fps_label)
        stats_layout.addWidget(self._detection_label)
        stats_layout.addWidget(self._hand_label)
        
        info_layout.addWidget(stats_group)
        
        # Recommendations group
        rec_group = QGroupBox("Recommendations")
        rec_layout = QVBoxLayout(rec_group)
        
        self._recommendations_text = QTextEdit()
        self._recommendations_text.setReadOnly(True)
        self._recommendations_text.setMaximumHeight(120)
        self._recommendations_text.setPlaceholderText("Start test mode to see recommendations...")
        rec_layout.addWidget(self._recommendations_text)
        
        info_layout.addWidget(rec_group)
        
        info_layout.addStretch()
        
        content_layout.addWidget(info_panel, stretch=1)
        layout.addLayout(content_layout)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self._start_button = QPushButton("Start Test")
        self._start_button.setMinimumHeight(40)
        self._start_button.clicked.connect(self._on_start_clicked)
        button_layout.addWidget(self._start_button)
        
        self._stop_button = QPushButton("Stop Test")
        self._stop_button.setMinimumHeight(40)
        self._stop_button.setEnabled(False)
        self._stop_button.clicked.connect(self._on_stop_clicked)
        button_layout.addWidget(self._stop_button)
        
        self._enable_button = QPushButton("Enable Mouse Control")
        self._enable_button.setMinimumHeight(40)
        self._enable_button.setEnabled(False)
        self._enable_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self._enable_button.clicked.connect(self._on_enable_clicked)
        button_layout.addWidget(self._enable_button)
        
        layout.addLayout(button_layout)
        
        # Warning label
        self._warning_label = QLabel(
            "⚠️ Test your gestures thoroughly before enabling mouse control"
        )
        self._warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._warning_label.setStyleSheet("color: #ff9800; font-weight: bold;")
        layout.addWidget(self._warning_label)
    
    def _on_start_clicked(self):
        """Handle start button click."""
        self.start_requested.emit()
    
    def _on_stop_clicked(self):
        """Handle stop button click."""
        self.stop_requested.emit()
    
    def _on_enable_clicked(self):
        """Handle enable control button click."""
        self.enable_control_requested.emit()
    
    def set_running(self, running: bool):
        """Update running state."""
        self._is_running = running
        self._start_button.setEnabled(not running)
        self._stop_button.setEnabled(running)
        
        if not running:
            self._preview_label.setText("Camera Preview")
            self._preview_label.setStyleSheet("background-color: #1a1a1a; color: #666;")
    
    def update_frame(self, frame: np.ndarray):
        """
        Update the camera preview with a new frame.
        
        Args:
            frame: RGB numpy array
        """
        if frame is None:
            return
        
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        
        q_image = QImage(
            frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888
        )
        
        pixmap = QPixmap.fromImage(q_image)
        scaled = pixmap.scaled(
            self._preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        self._preview_label.setPixmap(scaled)
    
    def update_info(self, info: dict):
        """
        Update the info panel.
        
        Args:
            info: Dict with gesture, confidence, fps, etc.
        """
        # Update gesture
        gesture = info.get('gesture', 'None')
        self._gesture_label.setText(gesture)
        
        # Color based on detection
        if info.get('hand_detected', False):
            self._gesture_label.setStyleSheet("color: #4CAF50;")
        else:
            self._gesture_label.setStyleSheet("color: #f44336;")
        
        # Update confidence
        confidence = info.get('confidence', 0.0)
        self._confidence_bar.setValue(int(confidence * 100))
        
        # Color confidence bar
        if confidence >= 0.7:
            self._confidence_bar.setStyleSheet("""
                QProgressBar::chunk { background-color: #4CAF50; }
            """)
        elif confidence >= 0.5:
            self._confidence_bar.setStyleSheet("""
                QProgressBar::chunk { background-color: #ff9800; }
            """)
        else:
            self._confidence_bar.setStyleSheet("""
                QProgressBar::chunk { background-color: #f44336; }
            """)
        
        # Update stats
        fps = info.get('fps', 0.0)
        self._fps_label.setText(f"FPS: {fps:.1f}")
        
        detection_rate = info.get('detection_rate', 0.0)
        self._detection_label.setText(f"Detection Rate: {detection_rate:.1%}")
        
        hand_type = info.get('is_right_hand')
        if hand_type is not None:
            self._hand_label.setText(f"Hand: {'Right' if hand_type else 'Left'}")
        else:
            self._hand_label.setText("Hand: --")
        
        # Enable control button if detection is good
        good_detection = detection_rate > 0.5 and fps > 15
        self._enable_button.setEnabled(self._is_running and good_detection)
    
    def update_recommendations(self, recommendations: list):
        """Update recommendations text."""
        self._recommendations_text.setText("\n".join(recommendations))
