"""
WavePoint - Python Mouse Controller

Pure Python mouse control using pynput for when C++ core is not available.
"""

import time
import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import threading

try:
    from pynput.mouse import Button, Controller as MouseController
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

import numpy as np

logger = logging.getLogger(__name__)


class GestureType(Enum):
    """Gesture types."""
    NONE = 0
    POINTING = 1
    LEFT_CLICK = 2
    RIGHT_CLICK = 3
    SCROLL = 4
    DRAG = 5
    NEUTRAL = 6


@dataclass
class MouseState:
    """Current mouse control state."""
    enabled: bool = False
    gesture: GestureType = GestureType.NONE
    cursor_x: float = 0.0
    cursor_y: float = 0.0
    is_dragging: bool = False
    last_click_time: float = 0.0


class PythonMouseController:
    """
    Pure Python mouse controller using pynput.

    Provides gesture-based mouse control when C++ core is unavailable.
    """

    def __init__(self, config=None):
        self.config = config
        self._enabled = False
        self._mouse: Optional[MouseController] = None
        self._state = MouseState()

        # Screen dimensions
        self._screen_width = 1920
        self._screen_height = 1080
        self._get_screen_size()

        # Calibration
        self._cam_x_min = 0.1
        self._cam_x_max = 0.9
        self._cam_y_min = 0.1
        self._cam_y_max = 0.9

        # Smoothing
        self._smoothing_alpha = 0.3
        self._last_x = 0.0
        self._last_y = 0.0
        self._initialized_pos = False

        # Gesture detection - larger thresholds for easier detection
        self._pinch_threshold = 0.12  # Distance for pinch detection
        self._pinch_release_threshold = 0.15
        self._dwell_time_ms = 80  # Faster click response
        self._debounce_ms = 300  # Prevent double clicks

        # Scroll tracking
        self._last_scroll_y = 0.0
        self._scroll_sensitivity = 50

        # State tracking
        self._gesture_start_time = 0.0
        self._current_gesture = GestureType.NONE
        self._pending_gesture = GestureType.NONE
        self._is_clicking = False
        self._is_dragging = False

        # Initialize mouse controller
        if PYNPUT_AVAILABLE:
            self._mouse = MouseController()
            logger.info("Python mouse controller initialized")
        else:
            logger.error("pynput not available - mouse control disabled")

    def _get_screen_size(self):
        """Get screen dimensions."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            self._screen_width = user32.GetSystemMetrics(0)
            self._screen_height = user32.GetSystemMetrics(1)
            logger.info(
                f"Screen size: {self._screen_width}x{self._screen_height}")
        except Exception as e:
            logger.warning(f"Could not get screen size: {e}")

    def set_calibration(self, cam_x_min: float, cam_x_max: float,
                        cam_y_min: float, cam_y_max: float):
        """Set calibration bounds."""
        self._cam_x_min = cam_x_min
        self._cam_x_max = cam_x_max
        self._cam_y_min = cam_y_min
        self._cam_y_max = cam_y_max
        logger.info(
            f"Calibration set: x=[{cam_x_min:.2f}, {cam_x_max:.2f}], y=[{cam_y_min:.2f}, {cam_y_max:.2f}]")

    def set_enabled(self, enabled: bool):
        """Enable/disable mouse control."""
        self._enabled = enabled
        if not enabled:
            # Release any held buttons
            if self._is_clicking and self._mouse:
                self._mouse.release(Button.left)
                self._is_clicking = False
            if self._is_dragging and self._mouse:
                self._mouse.release(Button.left)
                self._is_dragging = False
        logger.info(f"Mouse control {'enabled' if enabled else 'disabled'}")

    def process_landmarks(self, landmarks: np.ndarray, confidence: float,
                          is_right_hand: bool) -> Tuple[str, float]:
        """
        Process hand landmarks and control mouse.

        Args:
            landmarks: 21x3 array of hand landmarks
            confidence: Detection confidence
            is_right_hand: True if right hand

        Returns:
            Tuple of (gesture_name, confidence)
        """
        if not self._enabled or self._mouse is None:
            return "Disabled", 0.0

        if landmarks is None or len(landmarks) < 21:
            self._handle_no_detection()
            return "None", 0.0

        logger.debug(f"Processing landmarks, index_tip: {landmarks[8][:2]}")

        # Get key landmarks
        wrist = landmarks[0]
        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        index_mcp = landmarks[5]
        middle_tip = landmarks[12]
        middle_mcp = landmarks[9]
        ring_tip = landmarks[16]
        pinky_tip = landmarks[20]

        # Detect gesture
        gesture = self._classify_gesture(landmarks)

        # Get cursor position from index finger
        cursor_x, cursor_y = self._map_to_screen(index_tip[0], index_tip[1])

        # Store index y for scroll tracking
        self._scroll_index_y = index_tip[1]

        # Apply smoothing
        if not self._initialized_pos:
            self._last_x = cursor_x
            self._last_y = cursor_y
            self._initialized_pos = True

        smooth_x = self._last_x + self._smoothing_alpha * \
            (cursor_x - self._last_x)
        smooth_y = self._last_y + self._smoothing_alpha * \
            (cursor_y - self._last_y)
        self._last_x = smooth_x
        self._last_y = smooth_y

        # Move cursor for pointing/neutral gestures - ALWAYS move when enabled
        self._move_cursor(int(smooth_x), int(smooth_y))

        # Handle gesture actions
        self._handle_gesture(gesture)

        return gesture.name, confidence

    def _classify_gesture(self, landmarks: np.ndarray) -> GestureType:
        """Classify the current gesture from landmarks."""
        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]  # Thumb interphalangeal joint
        index_tip = landmarks[8]
        index_pip = landmarks[6]  # Index proximal interphalangeal
        middle_tip = landmarks[12]
        middle_pip = landmarks[10]
        ring_tip = landmarks[16]
        ring_pip = landmarks[14]
        pinky_tip = landmarks[20]
        pinky_pip = landmarks[18]

        index_mcp = landmarks[5]
        middle_mcp = landmarks[9]
        ring_mcp = landmarks[13]
        pinky_mcp = landmarks[17]

        wrist = landmarks[0]

        # Calculate pinch distances (thumb to fingertips)
        thumb_index_dist = np.linalg.norm(thumb_tip[:2] - index_tip[:2])
        thumb_middle_dist = np.linalg.norm(thumb_tip[:2] - middle_tip[:2])

        # Check finger extension using tip vs PIP (more reliable than MCP)
        # A finger is extended if tip is further from wrist than PIP
        def is_finger_extended(tip, pip, mcp):
            # Check if fingertip is above (lower y value) the pip joint
            return tip[1] < pip[1]

        index_extended = is_finger_extended(index_tip, index_pip, index_mcp)
        middle_extended = is_finger_extended(
            middle_tip, middle_pip, middle_mcp)
        ring_extended = is_finger_extended(ring_tip, ring_pip, ring_mcp)
        pinky_extended = is_finger_extended(pinky_tip, pinky_pip, pinky_mcp)

        # Count extended fingers
        extended_count = sum(
            [index_extended, middle_extended, ring_extended, pinky_extended])

        # LEFT CLICK: thumb + index pinch (thumb tip close to index tip)
        if thumb_index_dist < self._pinch_threshold:
            return GestureType.LEFT_CLICK

        # RIGHT CLICK: thumb + middle pinch
        if thumb_middle_dist < self._pinch_threshold:
            return GestureType.RIGHT_CLICK

        # DRAG: closed fist (no fingers extended)
        if extended_count == 0:
            return GestureType.DRAG

        # NEUTRAL: open palm (all 4 fingers extended)
        if extended_count >= 4:
            return GestureType.NEUTRAL

        # SCROLL: exactly 2 fingers extended (index + middle), others curled
        if index_extended and middle_extended and not ring_extended and not pinky_extended:
            return GestureType.SCROLL

        # POINTING: only index extended (or index + thumb)
        if index_extended and not middle_extended:
            return GestureType.POINTING

        # Default to pointing if index is up
        if index_extended:
            return GestureType.POINTING

        return GestureType.NONE

    def _map_to_screen(self, cam_x: float, cam_y: float) -> Tuple[float, float]:
        """Map camera coordinates to screen coordinates."""
        # Mirror x for natural movement
        cam_x = 1.0 - cam_x

        # Normalize to calibration bounds
        norm_x = (cam_x - self._cam_x_min) / \
            (self._cam_x_max - self._cam_x_min)
        norm_y = (cam_y - self._cam_y_min) / \
            (self._cam_y_max - self._cam_y_min)

        # Clamp to [0, 1]
        norm_x = max(0.0, min(1.0, norm_x))
        norm_y = max(0.0, min(1.0, norm_y))

        # Map to screen
        screen_x = norm_x * self._screen_width
        screen_y = norm_y * self._screen_height

        return screen_x, screen_y

    def _move_cursor(self, x: int, y: int):
        """Move cursor to position."""
        if self._mouse:
            try:
                self._mouse.position = (x, y)
            except Exception as e:
                logger.error(f"Failed to move cursor: {e}")

    def _handle_gesture(self, gesture: GestureType):
        """Handle gesture state machine and actions."""
        current_time = time.time() * 1000  # ms

        # Track gesture timing for dwell
        if gesture != self._pending_gesture:
            self._pending_gesture = gesture
            self._gesture_start_time = current_time
            logger.info(f"Gesture changed to: {gesture.name}")

        dwell_elapsed = current_time - self._gesture_start_time

        # Left click with dwell time
        if gesture == GestureType.LEFT_CLICK:
            if dwell_elapsed >= self._dwell_time_ms and not self._is_clicking:
                if current_time - self._state.last_click_time >= self._debounce_ms:
                    logger.info("Performing LEFT CLICK")
                    self._do_click(Button.left)
                    self._state.last_click_time = current_time
                    self._is_clicking = True
        else:
            self._is_clicking = False

        # Right click with dwell time
        if gesture == GestureType.RIGHT_CLICK:
            if dwell_elapsed >= self._dwell_time_ms:
                if current_time - self._state.last_click_time >= self._debounce_ms:
                    logger.info("Performing RIGHT CLICK")
                    self._do_click(Button.right)
                    self._state.last_click_time = current_time

        # Drag handling
        if gesture == GestureType.DRAG:
            if dwell_elapsed >= 300 and not self._is_dragging:  # Longer dwell for drag
                self._start_drag()
        elif self._is_dragging:
            self._end_drag()

        # Scroll handling
        if gesture == GestureType.SCROLL:
            # Scroll based on vertical hand position change
            if hasattr(self, '_scroll_index_y'):
                delta_y = self._scroll_index_y - self._last_scroll_y
                if abs(delta_y) > 0.02:  # Minimum movement threshold
                    scroll_amount = int(delta_y * self._scroll_sensitivity)
                    if scroll_amount != 0:
                        # Negative for natural scroll
                        self._mouse.scroll(0, -scroll_amount)
                        logger.info(f"Scrolling: {scroll_amount}")
                self._last_scroll_y = self._scroll_index_y

        self._current_gesture = gesture

    def _do_click(self, button: Button):
        """Perform a mouse click."""
        if self._mouse:
            self._mouse.click(button)
            logger.debug(f"Click: {button}")

    def _start_drag(self):
        """Start dragging."""
        if self._mouse and not self._is_dragging:
            self._mouse.press(Button.left)
            self._is_dragging = True
            logger.debug("Drag started")

    def _end_drag(self):
        """End dragging."""
        if self._mouse and self._is_dragging:
            self._mouse.release(Button.left)
            self._is_dragging = False
            logger.debug("Drag ended")

    def _handle_no_detection(self):
        """Handle when hand is not detected."""
        # Release any held buttons
        if self._is_dragging:
            self._end_drag()
        self._current_gesture = GestureType.NONE
        self._pending_gesture = GestureType.NONE
