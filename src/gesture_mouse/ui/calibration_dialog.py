"""
WavePoint - Calibration Dialog

PyQt6 dialog for the calibration workflow.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QStackedWidget, QWidget
)
from PyQt6.QtGui import QImage, QPixmap, QFont, QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint
import numpy as np
import logging

from ..calibration import CalibrationManager, CalibrationStep
from ..hand_tracker import HandTracker, draw_landmarks
from ..config import CalibrationSettings

logger = logging.getLogger(__name__)


class CalibrationDialog(QDialog):
    """
    Dialog for guided calibration workflow.
    """
    
    calibration_complete = pyqtSignal(object)  # CalibrationSettings
    
    def __init__(
        self, 
        hand_tracker: HandTracker,
        parent=None
    ):
        super().__init__(parent)
        
        self.tracker = hand_tracker
        self.calibration_manager = CalibrationManager(
            hand_tracker,
            screen_width=self.screen().size().width(),
            screen_height=self.screen().size().height()
        )
        
        self.setWindowTitle("WavePoint Calibration")
        self.setMinimumSize(800, 600)
        
        self._setup_ui()
        self._setup_callbacks()
        
        # Update timer
        self._timer = QTimer()
        self._timer.timeout.connect(self._update)
        
    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Calibration")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Stacked widget for different screens
        self._stack = QStackedWidget()
        
        # Intro screen
        self._stack.addWidget(self._create_intro_screen())
        
        # Calibration screen
        self._stack.addWidget(self._create_calibration_screen())
        
        # Verification screen
        self._stack.addWidget(self._create_verification_screen())
        
        # Complete screen
        self._stack.addWidget(self._create_complete_screen())
        
        layout.addWidget(self._stack)
        
        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)
        
        # Button row
        button_layout = QHBoxLayout()
        
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        button_layout.addWidget(self._cancel_btn)
        
        button_layout.addStretch()
        
        self._back_btn = QPushButton("Back")
        self._back_btn.clicked.connect(self._on_back)
        self._back_btn.setVisible(False)
        button_layout.addWidget(self._back_btn)
        
        self._next_btn = QPushButton("Start")
        self._next_btn.clicked.connect(self._on_next)
        button_layout.addWidget(self._next_btn)
        
        layout.addLayout(button_layout)
    
    def _create_intro_screen(self) -> QWidget:
        """Create the introduction screen."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        intro_text = QLabel(
            "Welcome to WavePoint Calibration\n\n"
            "This process will map your hand movements to screen coordinates.\n\n"
            "You will point at 5 markers on the screen.\n"
            "Hold your index finger steady at each marker for about 1.5 seconds.\n\n"
            "Tips:\n"
            "• Ensure good lighting\n"
            "• Keep your hand visible to the camera\n"
            "• Move naturally - don't strain\n\n"
            "Click 'Start' when ready."
        )
        intro_text.setFont(QFont("Segoe UI", 11))
        intro_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(intro_text)
        
        return widget
    
    def _create_calibration_screen(self) -> QWidget:
        """Create the main calibration screen."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Instructions
        self._instruction_label = QLabel("Point at the marker")
        self._instruction_label.setFont(QFont("Segoe UI", 12))
        self._instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._instruction_label)
        
        # Camera preview with target overlay
        preview_frame = QFrame()
        preview_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        preview_layout = QVBoxLayout(preview_frame)
        
        self._preview_label = QLabel()
        self._preview_label.setMinimumSize(640, 480)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet("background-color: #1a1a1a;")
        preview_layout.addWidget(self._preview_label)
        
        layout.addWidget(preview_frame)
        
        # Point progress
        self._point_label = QLabel("Point 1 of 5")
        self._point_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._point_label)
        
        return widget
    
    def _create_verification_screen(self) -> QWidget:
        """Create the verification screen."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        verify_text = QLabel(
            "Calibration Complete!\n\n"
            "Move your hand to verify the cursor follows correctly.\n\n"
            "If the cursor doesn't track well, click 'Retry' to recalibrate.\n"
            "Otherwise, click 'Finish' to save the calibration."
        )
        verify_text.setFont(QFont("Segoe UI", 11))
        verify_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(verify_text)
        
        # Preview for verification
        self._verify_preview = QLabel()
        self._verify_preview.setMinimumSize(320, 240)
        self._verify_preview.setStyleSheet("background-color: #1a1a1a;")
        layout.addWidget(self._verify_preview)
        
        return widget
    
    def _create_complete_screen(self) -> QWidget:
        """Create the completion screen."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        complete_text = QLabel(
            "✓ Calibration Saved!\n\n"
            "Your hand movements are now calibrated to your screen.\n\n"
            "You can recalibrate at any time from the Settings menu."
        )
        complete_text.setFont(QFont("Segoe UI", 12))
        complete_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        complete_text.setStyleSheet("color: #4CAF50;")
        layout.addWidget(complete_text)
        
        return widget
    
    def _setup_callbacks(self):
        """Setup calibration manager callbacks."""
        self.calibration_manager.set_on_step_changed(self._on_step_changed)
        self.calibration_manager.set_on_progress(self._on_progress)
        self.calibration_manager.set_on_complete(self._on_calibration_complete)
    
    def start(self):
        """Start the calibration process."""
        if not self.tracker.is_running:
            if not self.tracker.start():
                logger.error("Failed to start hand tracker for calibration")
                return
        
        self._stack.setCurrentIndex(0)
        self._next_btn.setText("Start")
        self._back_btn.setVisible(False)
        self._progress_bar.setValue(0)
        
        self.show()
    
    def _on_next(self):
        """Handle next button click."""
        current = self._stack.currentIndex()
        
        if current == 0:  # Intro -> Calibration
            self.calibration_manager.start()
            self.calibration_manager.advance()
            self._stack.setCurrentIndex(1)
            self._next_btn.setText("Skip")
            self._back_btn.setVisible(True)
            self._timer.start(33)  # ~30 FPS
            
        elif current == 2:  # Verification -> Complete
            self.calibration_manager.advance()
            self._stack.setCurrentIndex(3)
            self._next_btn.setText("Close")
            self._back_btn.setText("Retry")
            self._timer.stop()
            
            # Emit calibration
            if self.calibration_manager.calibration:
                self.calibration_complete.emit(self.calibration_manager.calibration)
            
        elif current == 3:  # Complete -> Close
            self.accept()
    
    def _on_back(self):
        """Handle back button click."""
        current = self._stack.currentIndex()
        
        if current == 1:  # Calibration -> Intro
            self._timer.stop()
            self.calibration_manager.cancel()
            self._stack.setCurrentIndex(0)
            self._next_btn.setText("Start")
            self._back_btn.setVisible(False)
            
        elif current == 2 or current == 3:  # Verification/Complete -> Restart
            self._stack.setCurrentIndex(0)
            self._next_btn.setText("Start")
            self._back_btn.setVisible(False)
            self._progress_bar.setValue(0)
    
    def _on_cancel(self):
        """Handle cancel button click."""
        self._timer.stop()
        self.calibration_manager.cancel()
        self.reject()
    
    def _on_step_changed(self, step: CalibrationStep):
        """Handle calibration step change."""
        step_names = {
            CalibrationStep.TOP_LEFT: "Top Left",
            CalibrationStep.TOP_RIGHT: "Top Right",
            CalibrationStep.BOTTOM_RIGHT: "Bottom Right",
            CalibrationStep.BOTTOM_LEFT: "Bottom Left",
            CalibrationStep.CENTER: "Center",
        }
        
        if step in step_names:
            point_num = list(step_names.keys()).index(step) + 1
            self._point_label.setText(f"Point {point_num} of 5: {step_names[step]}")
        
        if step == CalibrationStep.VERIFICATION:
            self._stack.setCurrentIndex(2)
            self._next_btn.setText("Finish")
            self._back_btn.setText("Retry")
    
    def _on_progress(self, progress: float):
        """Handle progress update."""
        self._progress_bar.setValue(int(progress * 100))
    
    def _on_calibration_complete(self, calibration: CalibrationSettings):
        """Handle calibration completion."""
        logger.info("Calibration complete")
    
    def _update(self):
        """Update loop for calibration."""
        hand_data = self.tracker.get_latest_result()
        
        if hand_data is None:
            return
        
        # Process through calibration manager
        state = self.calibration_manager.process_frame(hand_data)
        
        # Update instruction
        self._instruction_label.setText(state.get('instruction', ''))
        
        # Create display frame
        if hand_data.raw_frame is not None:
            frame = hand_data.raw_frame.copy()
            
            # Flip for mirror
            frame = np.flip(frame, axis=1).copy()
            
            # Draw landmarks
            if hand_data.is_valid:
                mirrored = hand_data.landmarks.copy()
                mirrored[:, 0] = 1.0 - mirrored[:, 0]
                frame = draw_landmarks(frame, mirrored)
            
            # Draw target marker
            point_screen = state.get('point_screen', (0, 0))
            if point_screen != (0, 0):
                h, w = frame.shape[:2]
                screen_w = self.screen().size().width()
                screen_h = self.screen().size().height()
                
                target_x = int(point_screen[0] / screen_w * w)
                target_y = int(point_screen[1] / screen_h * h)
                
                color = (0, 255, 0) if state.get('hand_detected') else (0, 0, 255)
                
                # Draw crosshair
                import cv2
                cv2.drawMarker(frame, (target_x, target_y), color, 
                              cv2.MARKER_CROSS, 40, 2)
                cv2.circle(frame, (target_x, target_y), 25, color, 2)
            
            # Draw progress
            progress = state.get('progress', 0.0)
            if progress > 0:
                h, w = frame.shape[:2]
                bar_width = int(w * 0.8)
                bar_x = int(w * 0.1)
                bar_y = h - 30
                
                import cv2
                cv2.rectangle(frame, (bar_x, bar_y), 
                             (bar_x + bar_width, bar_y + 15), (50, 50, 50), -1)
                cv2.rectangle(frame, (bar_x, bar_y),
                             (bar_x + int(bar_width * progress), bar_y + 15), 
                             (0, 255, 0), -1)
            
            # Convert to Qt
            import cv2
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            q_img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img)
            
            scaled = pixmap.scaled(
                self._preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self._preview_label.setPixmap(scaled)
    
    def closeEvent(self, event):
        """Handle dialog close."""
        self._timer.stop()
        super().closeEvent(event)
