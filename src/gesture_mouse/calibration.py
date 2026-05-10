"""
WavePoint - Calibration Module

Provides guided calibration workflow for mapping camera space to screen space.
Ensures accurate cursor positioning across different setups.
"""

import cv2
import numpy as np
import time
import logging
from typing import Optional, Callable, List, Tuple
from dataclasses import dataclass
from enum import Enum, auto

from .config import CalibrationSettings
from .hand_tracker import HandTracker, HandData, draw_landmarks

logger = logging.getLogger(__name__)


class CalibrationStep(Enum):
    """Steps in the calibration process."""
    NOT_STARTED = auto()
    INTRO = auto()
    TOP_LEFT = auto()
    TOP_RIGHT = auto()
    BOTTOM_RIGHT = auto()
    BOTTOM_LEFT = auto()
    CENTER = auto()
    VERIFICATION = auto()
    COMPLETE = auto()
    CANCELLED = auto()


@dataclass
class CalibrationPoint:
    """A single calibration point."""
    name: str
    screen_x: int
    screen_y: int
    cam_x: float = 0.0
    cam_y: float = 0.0
    samples: List[Tuple[float, float]] = None
    
    def __post_init__(self):
        if self.samples is None:
            self.samples = []
    
    def add_sample(self, x: float, y: float) -> None:
        """Add a sample point."""
        self.samples.append((x, y))
    
    def get_average(self) -> Tuple[float, float]:
        """Get average of all samples."""
        if not self.samples:
            return (0.0, 0.0)
        x_avg = sum(s[0] for s in self.samples) / len(self.samples)
        y_avg = sum(s[1] for s in self.samples) / len(self.samples)
        return (x_avg, y_avg)
    
    def is_complete(self, min_samples: int = 30) -> bool:
        """Check if enough samples collected."""
        return len(self.samples) >= min_samples


class CalibrationManager:
    """
    Manages the calibration workflow.
    
    The calibration process:
    1. User points at corners of their usable camera space
    2. System records hand positions at each corner
    3. Mapping is calculated from camera space to screen space
    4. User verifies by moving cursor to targets
    """
    
    SAMPLES_PER_POINT = 30  # Frames to collect per calibration point
    HOLD_TIME_MS = 1500     # Time to hold position
    
    def __init__(
        self,
        hand_tracker: HandTracker,
        screen_width: int = 1920,
        screen_height: int = 1080
    ):
        """
        Initialize calibration manager.
        
        Args:
            hand_tracker: Hand tracker instance
            screen_width: Screen width in pixels
            screen_height: Screen height in pixels
        """
        self.tracker = hand_tracker
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        # Calibration state
        self.current_step = CalibrationStep.NOT_STARTED
        self.points: List[CalibrationPoint] = []
        self.current_point_index = 0
        self.hold_start_time: Optional[float] = None
        
        # Results
        self.calibration: Optional[CalibrationSettings] = None
        
        # Callbacks
        self._on_step_changed: Optional[Callable[[CalibrationStep], None]] = None
        self._on_progress: Optional[Callable[[float], None]] = None
        self._on_complete: Optional[Callable[[CalibrationSettings], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        
        # Initialize calibration points
        self._init_points()
    
    def _init_points(self) -> None:
        """Initialize calibration points at screen corners."""
        margin = 100  # Pixels from edge
        
        self.points = [
            CalibrationPoint(
                name="Top Left",
                screen_x=margin,
                screen_y=margin
            ),
            CalibrationPoint(
                name="Top Right",
                screen_x=self.screen_width - margin,
                screen_y=margin
            ),
            CalibrationPoint(
                name="Bottom Right",
                screen_x=self.screen_width - margin,
                screen_y=self.screen_height - margin
            ),
            CalibrationPoint(
                name="Bottom Left",
                screen_x=margin,
                screen_y=self.screen_height - margin
            ),
            CalibrationPoint(
                name="Center",
                screen_x=self.screen_width // 2,
                screen_y=self.screen_height // 2
            ),
        ]
    
    def start(self) -> bool:
        """
        Start calibration process.
        
        Returns:
            True if started successfully
        """
        if not self.tracker.is_running:
            logger.error("Hand tracker must be running to calibrate")
            return False
        
        # Reset state
        self._init_points()
        self.current_point_index = 0
        self.hold_start_time = None
        self.calibration = None
        
        self._set_step(CalibrationStep.INTRO)
        logger.info("Calibration started")
        return True
    
    def cancel(self) -> None:
        """Cancel calibration."""
        self._set_step(CalibrationStep.CANCELLED)
        logger.info("Calibration cancelled")
    
    def advance(self) -> None:
        """Advance to next step (for intro/verification screens)."""
        if self.current_step == CalibrationStep.INTRO:
            self._set_step(CalibrationStep.TOP_LEFT)
        elif self.current_step == CalibrationStep.VERIFICATION:
            self._set_step(CalibrationStep.COMPLETE)
            if self._on_complete and self.calibration:
                self._on_complete(self.calibration)
    
    def process_frame(self, hand_data: HandData) -> dict:
        """
        Process a frame during calibration.
        
        Args:
            hand_data: Hand detection data
            
        Returns:
            Dict with calibration state info for UI
        """
        result = {
            'step': self.current_step,
            'point_name': '',
            'point_screen': (0, 0),
            'progress': 0.0,
            'instruction': '',
            'hand_detected': hand_data.is_valid,
        }
        
        # Handle non-collection steps
        if self.current_step in (
            CalibrationStep.NOT_STARTED,
            CalibrationStep.INTRO,
            CalibrationStep.VERIFICATION,
            CalibrationStep.COMPLETE,
            CalibrationStep.CANCELLED
        ):
            result['instruction'] = self._get_instruction()
            return result
        
        # Get current point
        point = self._get_current_point()
        if not point:
            return result
        
        result['point_name'] = point.name
        result['point_screen'] = (point.screen_x, point.screen_y)
        result['instruction'] = f"Point at the {point.name} marker and hold steady"
        
        if not hand_data.is_valid:
            self.hold_start_time = None
            result['instruction'] = "Show your hand to the camera"
            return result
        
        # Get index finger tip position
        index_tip = hand_data.landmarks[8]  # Index tip is landmark 8
        cam_x, cam_y = index_tip[0], index_tip[1]
        
        # Check if hand is relatively stable
        if self.hold_start_time is None:
            self.hold_start_time = time.time()
        
        elapsed_ms = (time.time() - self.hold_start_time) * 1000
        
        if elapsed_ms >= self.HOLD_TIME_MS:
            # Collect sample
            point.add_sample(cam_x, cam_y)
            
            if point.is_complete(self.SAMPLES_PER_POINT):
                # Calculate average and move to next point
                avg_x, avg_y = point.get_average()
                point.cam_x = avg_x
                point.cam_y = avg_y
                
                logger.info(f"Calibration point {point.name}: cam=({avg_x:.3f}, {avg_y:.3f})")
                
                self._advance_to_next_point()
                self.hold_start_time = None
        
        # Calculate progress
        samples_collected = len(point.samples)
        hold_progress = min(1.0, elapsed_ms / self.HOLD_TIME_MS)
        
        if samples_collected > 0:
            result['progress'] = samples_collected / self.SAMPLES_PER_POINT
        else:
            result['progress'] = hold_progress * 0.1  # Show hold progress
        
        if self._on_progress:
            total_progress = (
                self.current_point_index + result['progress']
            ) / len(self.points)
            self._on_progress(total_progress)
        
        return result
    
    def _get_current_point(self) -> Optional[CalibrationPoint]:
        """Get current calibration point."""
        if 0 <= self.current_point_index < len(self.points):
            return self.points[self.current_point_index]
        return None
    
    def _advance_to_next_point(self) -> None:
        """Move to next calibration point."""
        self.current_point_index += 1
        
        if self.current_point_index >= len(self.points):
            # All points collected, calculate calibration
            self._calculate_calibration()
            self._set_step(CalibrationStep.VERIFICATION)
        else:
            # Map step enum to point index
            step_map = {
                0: CalibrationStep.TOP_LEFT,
                1: CalibrationStep.TOP_RIGHT,
                2: CalibrationStep.BOTTOM_RIGHT,
                3: CalibrationStep.BOTTOM_LEFT,
                4: CalibrationStep.CENTER,
            }
            self._set_step(step_map.get(
                self.current_point_index, 
                CalibrationStep.VERIFICATION
            ))
    
    def _calculate_calibration(self) -> None:
        """Calculate calibration settings from collected points."""
        if len(self.points) < 4:
            logger.error("Not enough calibration points")
            return
        
        # Get corner points
        tl = self.points[0]  # Top left
        tr = self.points[1]  # Top right
        br = self.points[2]  # Bottom right
        bl = self.points[3]  # Bottom left
        
        # Calculate camera space bounds
        # Use average of corners for more robust bounds
        cam_left = (tl.cam_x + bl.cam_x) / 2
        cam_right = (tr.cam_x + br.cam_x) / 2
        cam_top = (tl.cam_y + tr.cam_y) / 2
        cam_bottom = (bl.cam_y + br.cam_y) / 2
        
        # Ensure proper ordering (camera may be mirrored)
        if cam_left > cam_right:
            cam_left, cam_right = cam_right, cam_left
        if cam_top > cam_bottom:
            cam_top, cam_bottom = cam_bottom, cam_top
        
        # Add small margin
        margin = 0.02
        cam_left = max(0.0, cam_left - margin)
        cam_right = min(1.0, cam_right + margin)
        cam_top = max(0.0, cam_top - margin)
        cam_bottom = min(1.0, cam_bottom + margin)
        
        # Calculate dead zone from center point variance
        if len(self.points) > 4:
            center = self.points[4]
            if center.samples:
                x_var = np.var([s[0] for s in center.samples])
                y_var = np.var([s[1] for s in center.samples])
                dead_zone = max(0.01, min(0.05, np.sqrt(x_var + y_var) * 2))
            else:
                dead_zone = 0.02
        else:
            dead_zone = 0.02
        
        self.calibration = CalibrationSettings(
            cam_left=cam_left,
            cam_right=cam_right,
            cam_top=cam_top,
            cam_bottom=cam_bottom,
            screen_left=0,
            screen_right=self.screen_width,
            screen_top=0,
            screen_bottom=self.screen_height,
            dead_zone_radius=dead_zone
        )
        
        logger.info(f"Calibration calculated: cam=({cam_left:.3f}-{cam_right:.3f}, "
                   f"{cam_top:.3f}-{cam_bottom:.3f}), dead_zone={dead_zone:.3f}")
    
    def _set_step(self, step: CalibrationStep) -> None:
        """Set current step and notify callback."""
        self.current_step = step
        if self._on_step_changed:
            self._on_step_changed(step)
    
    def _get_instruction(self) -> str:
        """Get instruction text for current step."""
        instructions = {
            CalibrationStep.NOT_STARTED: "Click 'Start Calibration' to begin",
            CalibrationStep.INTRO: (
                "Calibration will map your hand movements to screen coordinates.\n\n"
                "You will point at 5 markers on screen.\n"
                "Hold your index finger steady at each marker for 1.5 seconds.\n\n"
                "Click 'Next' to begin."
            ),
            CalibrationStep.VERIFICATION: (
                "Calibration complete!\n\n"
                "Move your hand to verify cursor follows correctly.\n"
                "Click 'Finish' to save, or 'Retry' to recalibrate."
            ),
            CalibrationStep.COMPLETE: "Calibration saved successfully!",
            CalibrationStep.CANCELLED: "Calibration cancelled",
        }
        return instructions.get(self.current_step, "")
    
    def get_calibration(self) -> Optional[CalibrationSettings]:
        """Get calculated calibration settings."""
        return self.calibration
    
    def set_on_step_changed(self, callback: Callable[[CalibrationStep], None]) -> None:
        """Set callback for step changes."""
        self._on_step_changed = callback
    
    def set_on_progress(self, callback: Callable[[float], None]) -> None:
        """Set callback for progress updates."""
        self._on_progress = callback
    
    def set_on_complete(self, callback: Callable[[CalibrationSettings], None]) -> None:
        """Set callback for calibration completion."""
        self._on_complete = callback
    
    def set_on_error(self, callback: Callable[[str], None]) -> None:
        """Set callback for errors."""
        self._on_error = callback


def draw_calibration_overlay(
    frame: np.ndarray,
    calibration_state: dict,
    screen_size: Tuple[int, int]
) -> np.ndarray:
    """
    Draw calibration overlay on frame.
    
    Args:
        frame: Frame to draw on
        calibration_state: State dict from CalibrationManager.process_frame()
        screen_size: (width, height) of screen
        
    Returns:
        Frame with overlay
    """
    frame = frame.copy()
    h, w = frame.shape[:2]
    
    # Draw instruction text
    instruction = calibration_state.get('instruction', '')
    if instruction:
        # Draw background for text
        cv2.rectangle(frame, (10, 10), (w - 10, 80), (0, 0, 0), -1)
        cv2.rectangle(frame, (10, 10), (w - 10, 80), (255, 255, 255), 1)
        
        # Draw text (handle multi-line)
        y = 35
        for line in instruction.split('\n')[:2]:  # Max 2 lines
            cv2.putText(
                frame, line, (20, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1
            )
            y += 25
    
    # Draw target point if in collection mode
    point_screen = calibration_state.get('point_screen', (0, 0))
    if point_screen != (0, 0):
        # Map screen coordinates to frame coordinates
        screen_w, screen_h = screen_size
        target_x = int(point_screen[0] / screen_w * w)
        target_y = int(point_screen[1] / screen_h * h)
        
        # Draw target crosshair
        color = (0, 255, 0) if calibration_state.get('hand_detected') else (0, 0, 255)
        cv2.drawMarker(
            frame, (target_x, target_y),
            color, cv2.MARKER_CROSS, 40, 2
        )
        cv2.circle(frame, (target_x, target_y), 25, color, 2)
    
    # Draw progress bar
    progress = calibration_state.get('progress', 0.0)
    if progress > 0:
        bar_width = w - 40
        bar_height = 20
        bar_x = 20
        bar_y = h - 40
        
        # Background
        cv2.rectangle(
            frame, 
            (bar_x, bar_y), 
            (bar_x + bar_width, bar_y + bar_height),
            (50, 50, 50), -1
        )
        
        # Progress
        progress_width = int(bar_width * progress)
        cv2.rectangle(
            frame,
            (bar_x, bar_y),
            (bar_x + progress_width, bar_y + bar_height),
            (0, 255, 0), -1
        )
        
        # Border
        cv2.rectangle(
            frame,
            (bar_x, bar_y),
            (bar_x + bar_width, bar_y + bar_height),
            (255, 255, 255), 1
        )
    
    return frame
