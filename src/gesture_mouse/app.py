"""
WavePoint - Main Application

Application lifecycle management and component coordination.
"""

import sys
import logging
import time
import threading
from typing import Optional
import numpy as np

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, QObject

from .config import Config
from .hand_tracker import HandTracker, HandData
from .test_mode import TestMode
from .mouse_controller import PythonMouseController
from .ui.main_window import MainWindow
from .ui.tray_icon import TrayIcon

logger = logging.getLogger(__name__)


class GestureProcessor(QObject):
    """
    Worker for processing gestures in a separate thread.
    Bridges hand tracking to the C++ gesture engine or Python fallback.
    """

    gesture_updated = pyqtSignal(str, float)  # gesture_name, confidence
    tracking_changed = pyqtSignal(bool)
    frame_ready = pyqtSignal(object, dict)  # frame, info

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self._engine = None
        self._python_controller: Optional[PythonMouseController] = None
        self._use_python_fallback = False
        self._enabled = False
        self._running = False

    def initialize(self) -> bool:
        """Initialize the gesture engine (C++ or Python fallback)."""
        try:
            from . import gesture_mouse_core as core

            self._engine = core.GestureEngine()
            engine_config = self.config.get_engine_config()

            if engine_config:
                self._engine.initialize(engine_config)
                logger.info("C++ gesture engine initialized")
                return True
            else:
                logger.warning("Could not get engine config")
                return False

        except ImportError as e:
            logger.warning(f"C++ core not available: {e}")
            logger.info("Using Python mouse controller fallback")
            self._use_python_fallback = True
            self._python_controller = PythonMouseController(self.config)

            # Apply calibration from config
            cal = self.config.current_profile.calibration
            self._python_controller.set_calibration(
                cal.cam_left, cal.cam_right,
                cal.cam_top, cal.cam_bottom
            )
            return True
        except Exception as e:
            logger.error(f"Failed to initialize gesture engine: {e}")
            return False

    def start(self):
        """Start the gesture engine."""
        if self._engine:
            self._engine.start()
        self._running = True

    def stop(self):
        """Stop the gesture engine."""
        if self._engine:
            self._engine.stop()
        if self._python_controller:
            self._python_controller.set_enabled(False)
        self._running = False

    def set_enabled(self, enabled: bool):
        """Enable/disable mouse input injection."""
        self._enabled = enabled
        if self._engine:
            self._engine.set_input_enabled(enabled)
        if self._python_controller:
            self._python_controller.set_enabled(enabled)

    def process_hand_data(self, hand_data: HandData):
        """Process hand tracking data through the gesture engine."""
        # Use Python fallback if C++ not available
        if self._use_python_fallback and self._python_controller:
            if hand_data.is_valid and self._enabled:
                gesture_name, confidence = self._python_controller.process_landmarks(
                    hand_data.landmarks,
                    hand_data.confidence,
                    hand_data.is_right_hand
                )
                self.gesture_updated.emit(gesture_name, confidence)
                self.tracking_changed.emit(True)
            elif hand_data.is_valid and not self._enabled:
                # Hand detected but control disabled - just emit for UI
                self.tracking_changed.emit(True)
            elif not hand_data.is_valid:
                if self._enabled:
                    self._python_controller._handle_no_detection()
                self.gesture_updated.emit("None", 0.0)
                self.tracking_changed.emit(False)
            return

        # C++ engine path
        if not self._engine:
            return

        if hand_data.is_valid:
            landmarks_flat = hand_data.landmarks.flatten().astype(np.float32)

            self._engine.process_landmarks(
                landmarks_flat,
                hand_data.confidence,
                hand_data.is_right_hand,
                hand_data.timestamp_ms,
                hand_data.frame_width,
                hand_data.frame_height
            )

            gesture = self._engine.get_current_gesture_name()
            confidence = self._engine.get_current_confidence()
            self.gesture_updated.emit(gesture, confidence)
            self.tracking_changed.emit(True)
        else:
            self._engine.process_no_detection()
            self.gesture_updated.emit("None", 0.0)
            self.tracking_changed.emit(False)

    def get_fps(self) -> float:
        """Get engine FPS."""
        if self._engine:
            return self._engine.get_fps()
        return 30.0  # Assume 30 FPS for Python fallback

    def update_config(self):
        """Update engine configuration."""
        if self._engine:
            engine_config = self.config.get_engine_config()
            if engine_config:
                self._engine.set_config(engine_config)
        if self._python_controller:
            cal = self.config.current_profile.calibration
            self._python_controller.set_calibration(
                cal.cam_left, cal.cam_right,
                cal.cam_top, cal.cam_bottom
            )


class WavePointApp:
    """
    Main application class.

    Coordinates all components:
    - Configuration
    - Hand tracking
    - Gesture processing
    - UI (main window + tray)
    """

    def __init__(self):
        self._app: Optional[QApplication] = None
        self._config: Optional[Config] = None
        self._tracker: Optional[HandTracker] = None
        self._processor: Optional[GestureProcessor] = None
        self._test_mode: Optional[TestMode] = None
        self._main_window: Optional[MainWindow] = None
        self._tray: Optional[TrayIcon] = None

        self._enabled = False
        self._update_timer: Optional[QTimer] = None

        # Setup logging
        self._setup_logging()

    def _setup_logging(self):
        """Configure logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
            ]
        )
        # Reduce noise from other loggers
        logging.getLogger('PIL').setLevel(logging.WARNING)
        logging.getLogger('matplotlib').setLevel(logging.WARNING)

    def initialize(self) -> bool:
        """
        Initialize all application components.

        Returns:
            True if initialization successful
        """
        logger.info("Initializing WavePoint...")

        # Create Qt application
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)  # Keep running in tray

        # Load configuration
        self._config = Config()
        logger.info(
            f"Configuration loaded, profile: {self._config.current_profile.name}")

        # Initialize hand tracker
        camera = self._config.current_profile.camera
        self._tracker = HandTracker(
            camera_index=camera.device_index,
            width=camera.width,
            height=camera.height,
            fps=camera.fps,
            min_detection_confidence=self._config.current_profile.gestures.min_detection_confidence,
            min_tracking_confidence=self._config.current_profile.gestures.min_tracking_confidence,
            brightness_normalization=camera.brightness_normalization
        )

        # Initialize gesture processor
        self._processor = GestureProcessor(self._config)
        self._processor.initialize()

        # Initialize test mode
        self._test_mode = TestMode(self._tracker, self._config)

        # Create UI
        self._create_ui()

        # Setup update timer
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_loop)

        # Connect hand tracker to processor
        self._tracker.set_on_hand_detected(self._on_hand_detected)
        self._tracker.set_on_no_detection(self._on_no_detection)

        logger.info("WavePoint initialized successfully")
        return True

    def _create_ui(self):
        """Create UI components."""
        # Main window
        self._main_window = MainWindow()
        self._main_window.set_config(self._config)
        self._main_window.set_tracker(self._tracker)
        self._main_window.set_test_mode(self._test_mode)

        # Connect signals
        self._main_window.enable_requested.connect(self._on_enable_requested)
        self._main_window.close_to_tray.connect(self._on_close_to_tray)

        # System tray
        self._tray = TrayIcon()
        self._tray.toggle_requested.connect(self._on_enable_requested)
        self._tray.test_mode_requested.connect(self._on_test_mode_requested)
        self._tray.calibration_requested.connect(
            self._on_calibration_requested)
        self._tray.settings_requested.connect(self._on_settings_requested)
        self._tray.show_window_requested.connect(self._on_show_window)
        self._tray.exit_requested.connect(self._on_exit)

        # Connect test mode frame updates
        self._test_mode.set_on_frame(self._on_test_frame)

    def run(self) -> int:
        """
        Run the application.

        Returns:
            Exit code
        """
        logger.info("Starting WavePoint...")

        # Show tray icon
        self._tray.show()

        # Show main window or start minimized
        if self._config.app_settings.start_minimized:
            self._tray.show_notification(
                "WavePoint is running in the system tray")
        else:
            self._main_window.show()

        # Start in test mode if configured
        if self._config.app_settings.test_mode_on_start:
            self._main_window._on_test_start()

        # Run event loop
        return self._app.exec()

    def shutdown(self):
        """Shutdown the application cleanly."""
        logger.info("Shutting down WavePoint...")

        # Stop everything
        self._enabled = False
        self._update_timer.stop()

        if self._processor:
            self._processor.set_enabled(False)
            self._processor.stop()

        if self._test_mode:
            self._test_mode.stop()

        if self._tracker:
            self._tracker.stop()

        # Save configuration
        if self._config:
            self._config.save()

        logger.info("WavePoint shutdown complete")

    def _on_enable_requested(self, enabled: bool):
        """Handle enable/disable request."""
        self._enabled = enabled

        if enabled:
            # Start tracking and processing
            if not self._tracker.is_running:
                self._tracker.start()

            self._processor.start()
            self._processor.set_enabled(True)
            self._update_timer.start(33)  # ~30 FPS

            self._tray.set_enabled(True)
            self._main_window.set_enabled(True)

            if self._config.app_settings.show_notifications:
                self._tray.show_notification("Mouse control enabled")

            logger.info("Mouse control enabled")
        else:
            # Stop processing (but keep tracker for test mode)
            self._processor.set_enabled(False)
            self._update_timer.stop()

            self._tray.set_enabled(False)
            self._main_window.set_enabled(False)

            if self._config.app_settings.show_notifications:
                self._tray.show_notification("Mouse control disabled")

            logger.info("Mouse control disabled")

    def _on_hand_detected(self, hand_data: HandData):
        """Handle hand detection from tracker."""
        if self._processor:
            self._processor.process_hand_data(hand_data)

    def _on_no_detection(self):
        """Handle no hand detection."""
        if self._enabled:
            self._processor.process_hand_data(HandData(
                landmarks=None,
                confidence=0.0,
                is_right_hand=True,
                timestamp_ms=int(time.time() * 1000),
                frame_width=640,
                frame_height=480
            ))

    def _update_loop(self):
        """Periodic update for UI."""
        if self._enabled and self._processor:
            fps = self._processor.get_fps()
            # Stats are updated via signals from processor

    def _on_test_frame(self, frame, info):
        """Handle test mode frame update."""
        self._main_window.update_test_frame(frame, info)

    def _on_test_mode_requested(self):
        """Handle test mode request from tray."""
        self._main_window.show()
        self._main_window._tabs.setCurrentIndex(0)
        self._main_window._on_test_start()

    def _on_calibration_requested(self):
        """Handle calibration request from tray."""
        self._main_window.show()
        self._main_window._on_calibrate()

    def _on_settings_requested(self):
        """Handle settings request from tray."""
        self._main_window.show()
        self._main_window._on_settings()

    def _on_show_window(self):
        """Show main window."""
        self._main_window.show()
        self._main_window.raise_()
        self._main_window.activateWindow()

    def _on_close_to_tray(self):
        """Handle close to tray."""
        if self._config.app_settings.show_notifications:
            self._tray.show_notification("WavePoint minimized to tray")

    def _on_exit(self):
        """Handle exit request."""
        self.shutdown()
        self._app.quit()


def main():
    """Application entry point."""
    app = WavePointApp()

    if not app.initialize():
        logger.error("Failed to initialize application")
        return 1

    try:
        return app.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        app.shutdown()
        return 0
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        app.shutdown()
        return 1


if __name__ == "__main__":
    sys.exit(main())


GestureMouseApp = WavePointApp
