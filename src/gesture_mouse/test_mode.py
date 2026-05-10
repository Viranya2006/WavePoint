"""
WavePoint - Test Mode

Safe testing environment where users can verify gesture detection
without any mouse input being injected. Essential for:
- Verifying lighting conditions
- Testing gesture recognition
- Checking camera setup
- Building user confidence before enabling live control
"""

import cv2
import numpy as np
import time
from typing import Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

from .hand_tracker import HandTracker, HandData, draw_landmarks
from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class TestModeStats:
    """Statistics from test mode session."""
    total_frames: int = 0
    detected_frames: int = 0
    avg_confidence: float = 0.0
    avg_fps: float = 0.0
    gesture_counts: dict = None
    
    def __post_init__(self):
        if self.gesture_counts is None:
            self.gesture_counts = {}
    
    @property
    def detection_rate(self) -> float:
        if self.total_frames == 0:
            return 0.0
        return self.detected_frames / self.total_frames


class TestMode:
    """
    Test mode for safe gesture verification.
    
    Features:
    - Camera preview with landmark overlay
    - Gesture name display
    - Confidence score display
    - FPS monitoring
    - NO mouse input injection
    - Statistics collection
    """
    
    def __init__(
        self,
        hand_tracker: HandTracker,
        config: Config
    ):
        """
        Initialize test mode.
        
        Args:
            hand_tracker: Hand tracker instance
            config: Application configuration
        """
        self.tracker = hand_tracker
        self.config = config
        
        # State
        self._running = False
        self._window_name = "WavePoint - Test Mode"
        
        # Statistics
        self.stats = TestModeStats()
        self._confidence_history = []
        self._fps_history = []
        
        # Current detection state
        self._current_gesture = "None"
        self._current_confidence = 0.0
        self._hand_detected = False
        
        # Gesture classifier (simplified for test mode)
        self._gesture_names = {
            'none': 'No Hand',
            'neutral': 'Open Palm (Neutral)',
            'pointing': 'Pointing',
            'left_click': 'Left Click (Pinch)',
            'right_click': 'Right Click',
            'scroll': 'Scroll',
            'drag': 'Fist (Drag)',
            'pause': 'Paused'
        }
        
        # Callbacks
        self._on_frame: Optional[Callable[[np.ndarray, dict], None]] = None
    
    def start(self) -> bool:
        """
        Start test mode.
        
        Returns:
            True if started successfully
        """
        if self._running:
            return True
        
        # Ensure tracker is running
        if not self.tracker.is_running:
            if not self.tracker.start():
                logger.error("Failed to start hand tracker")
                return False
        
        # Reset statistics
        self.stats = TestModeStats()
        self._confidence_history.clear()
        self._fps_history.clear()
        
        self._running = True
        logger.info("Test mode started")
        return True
    
    def stop(self) -> None:
        """Stop test mode."""
        self._running = False
        try:
            cv2.destroyWindow(self._window_name)
        except cv2.error:
            pass  # Window may not exist
        logger.info("Test mode stopped")
    
    def process_frame(self) -> Optional[Tuple[np.ndarray, dict]]:
        """
        Process a single frame in test mode.
        
        Returns:
            Tuple of (display_frame, info_dict) or None if not running
        """
        if not self._running:
            return None
        
        # Get latest hand data
        hand_data = self.tracker.get_latest_result()
        
        if hand_data is None or hand_data.raw_frame is None:
            return None
        
        # Update statistics
        self.stats.total_frames += 1
        
        if hand_data.is_valid:
            self.stats.detected_frames += 1
            self._confidence_history.append(hand_data.confidence)
            if len(self._confidence_history) > 100:
                self._confidence_history.pop(0)
            
            # Classify gesture
            gesture = self._classify_gesture(hand_data)
            self._current_gesture = gesture
            self._current_confidence = hand_data.confidence
            self._hand_detected = True
            
            # Update gesture counts
            if gesture not in self.stats.gesture_counts:
                self.stats.gesture_counts[gesture] = 0
            self.stats.gesture_counts[gesture] += 1
        else:
            self._current_gesture = "No Hand"
            self._current_confidence = 0.0
            self._hand_detected = False
        
        # Update FPS
        self._fps_history.append(self.tracker.fps)
        if len(self._fps_history) > 30:
            self._fps_history.pop(0)
        
        # Calculate averages
        if self._confidence_history:
            self.stats.avg_confidence = sum(self._confidence_history) / len(self._confidence_history)
        if self._fps_history:
            self.stats.avg_fps = sum(self._fps_history) / len(self._fps_history)
        
        # Create display frame
        display_frame = self._create_display_frame(hand_data)
        
        # Create info dict
        info = {
            'gesture': self._current_gesture,
            'confidence': self._current_confidence,
            'fps': self.tracker.fps,
            'hand_detected': self._hand_detected,
            'detection_rate': self.stats.detection_rate,
            'is_right_hand': hand_data.is_right_hand if hand_data.is_valid else None,
        }
        
        # Notify callback
        if self._on_frame:
            self._on_frame(display_frame, info)
        
        return display_frame, info
    
    def _classify_gesture(self, hand_data: HandData) -> str:
        """
        Classify gesture from hand landmarks.
        Simplified version for test mode display.
        """
        if not hand_data.is_valid:
            return "No Hand"
        
        landmarks = hand_data.landmarks
        
        # Get key landmarks
        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        middle_tip = landmarks[12]
        ring_tip = landmarks[16]
        pinky_tip = landmarks[20]
        
        index_mcp = landmarks[5]
        middle_mcp = landmarks[9]
        ring_mcp = landmarks[13]
        pinky_mcp = landmarks[17]
        
        wrist = landmarks[0]
        
        # Calculate distances
        def dist(a, b):
            return np.sqrt((a[0] - b[0])**2 + (a[1] - b[1])**2)
        
        thumb_index_dist = dist(thumb_tip, index_tip)
        thumb_middle_dist = dist(thumb_tip, middle_tip)
        
        # Check for pinch (left click)
        if thumb_index_dist < 0.05:
            return "Left Click (Pinch)"
        
        # Check for right click pinch
        if thumb_middle_dist < 0.05:
            return "Right Click"
        
        # Check finger extension
        def is_extended(tip, mcp, wrist):
            tip_to_wrist = dist(tip, wrist)
            mcp_to_wrist = dist(mcp, wrist)
            return tip_to_wrist > mcp_to_wrist
        
        index_ext = is_extended(index_tip, index_mcp, wrist)
        middle_ext = is_extended(middle_tip, middle_mcp, wrist)
        ring_ext = is_extended(ring_tip, ring_mcp, wrist)
        pinky_ext = is_extended(pinky_tip, pinky_mcp, wrist)
        
        extended_count = sum([index_ext, middle_ext, ring_ext, pinky_ext])
        
        # Check for scroll (index + middle extended)
        if index_ext and middle_ext and not ring_ext and not pinky_ext:
            index_middle_dist = dist(index_tip, middle_tip)
            if index_middle_dist < 0.1:
                return "Scroll"
        
        # Check for fist (drag)
        if extended_count <= 1:
            return "Fist (Drag)"
        
        # Check for pointing
        if index_ext and not middle_ext and not ring_ext:
            return "Pointing"
        
        # Check for open palm
        if extended_count >= 3:
            return "Open Palm (Neutral)"
        
        return "Unknown"
    
    def _create_display_frame(self, hand_data: HandData) -> np.ndarray:
        """Create the display frame with overlays."""
        frame = hand_data.raw_frame.copy()
        
        # Flip for mirror effect
        frame = cv2.flip(frame, 1)
        
        h, w = frame.shape[:2]
        
        # Draw landmarks if detected
        if hand_data.is_valid:
            # Mirror landmarks for display
            mirrored_landmarks = hand_data.landmarks.copy()
            mirrored_landmarks[:, 0] = 1.0 - mirrored_landmarks[:, 0]
            frame = draw_landmarks(frame, mirrored_landmarks)
        
        # Draw info panel background
        panel_height = 120
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, panel_height), (0, 0, 0), -1)
        frame = cv2.addWeighted(overlay, 0.7, frame, 0.3, 0)
        
        # Draw gesture name
        gesture_color = (0, 255, 0) if self._hand_detected else (0, 0, 255)
        cv2.putText(
            frame, f"Gesture: {self._current_gesture}",
            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, gesture_color, 2
        )
        
        # Draw confidence
        conf_text = f"Confidence: {self._current_confidence:.1%}"
        conf_color = (0, 255, 0) if self._current_confidence > 0.7 else (0, 255, 255)
        if self._current_confidence < 0.5:
            conf_color = (0, 0, 255)
        cv2.putText(
            frame, conf_text,
            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, conf_color, 2
        )
        
        # Draw FPS
        fps_text = f"FPS: {self.tracker.fps:.1f}"
        fps_color = (0, 255, 0) if self.tracker.fps >= 25 else (0, 255, 255)
        if self.tracker.fps < 15:
            fps_color = (0, 0, 255)
        cv2.putText(
            frame, fps_text,
            (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, fps_color, 2
        )
        
        # Draw detection rate
        det_rate = self.stats.detection_rate
        det_text = f"Detection: {det_rate:.1%}"
        cv2.putText(
            frame, det_text,
            (w - 180, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
        )
        
        # Draw hand type
        if hand_data.is_valid:
            hand_type = "Right Hand" if hand_data.is_right_hand else "Left Hand"
            cv2.putText(
                frame, hand_type,
                (w - 180, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
            )
        
        # Draw "TEST MODE" watermark
        cv2.putText(
            frame, "TEST MODE - No Mouse Control",
            (w // 2 - 180, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
        )
        
        # Draw confidence bar
        bar_x = 10
        bar_y = 105
        bar_width = 200
        bar_height = 10
        
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), (50, 50, 50), -1)
        conf_width = int(bar_width * self._current_confidence)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + conf_width, bar_y + bar_height), conf_color, -1)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), (255, 255, 255), 1)
        
        return frame
    
    def show_window(self) -> bool:
        """
        Show test mode in OpenCV window.
        
        Returns:
            False if window was closed (ESC pressed)
        """
        result = self.process_frame()
        if result is None:
            return True
        
        frame, info = result
        cv2.imshow(self._window_name, frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            return False
        
        return True
    
    def get_frame_for_qt(self) -> Optional[Tuple[np.ndarray, dict]]:
        """
        Get frame for Qt display (no OpenCV window).
        
        Returns:
            Tuple of (RGB frame, info dict) or None
        """
        result = self.process_frame()
        if result is None:
            return None
        
        frame, info = result
        # Convert BGR to RGB for Qt
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return rgb_frame, info
    
    def set_on_frame(self, callback: Callable[[np.ndarray, dict], None]) -> None:
        """Set callback for each processed frame."""
        self._on_frame = callback
    
    def get_stats(self) -> TestModeStats:
        """Get current statistics."""
        return self.stats
    
    def get_recommendations(self) -> list:
        """
        Get recommendations based on test session.
        
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        # Check detection rate
        if self.stats.detection_rate < 0.5:
            recommendations.append(
                "⚠️ Low detection rate. Try improving lighting or "
                "positioning your hand closer to the camera."
            )
        elif self.stats.detection_rate < 0.8:
            recommendations.append(
                "💡 Detection rate could be improved. Ensure good, "
                "even lighting on your hand."
            )
        
        # Check confidence
        if self.stats.avg_confidence < 0.6:
            recommendations.append(
                "⚠️ Low confidence scores. Try a plain background "
                "and avoid wearing rings or gloves."
            )
        
        # Check FPS
        if self.stats.avg_fps < 20:
            recommendations.append(
                "⚠️ Low FPS. Close other applications or reduce "
                "camera resolution in settings."
            )
        elif self.stats.avg_fps < 25:
            recommendations.append(
                "💡 FPS is acceptable but could be improved for "
                "smoother tracking."
            )
        
        # Check gesture variety
        if len(self.stats.gesture_counts) < 3:
            recommendations.append(
                "💡 Try practicing different gestures: pointing, "
                "pinching, and open palm."
            )
        
        if not recommendations:
            recommendations.append(
                "✅ Everything looks good! You're ready to enable "
                "mouse control."
            )
        
        return recommendations
    
    @property
    def is_running(self) -> bool:
        return self._running
