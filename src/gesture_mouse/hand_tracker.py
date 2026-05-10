"""
WavePoint - Hand Tracking Module

MediaPipe-based hand landmark detection with preprocessing optimizations
for low-quality webcams and varying lighting conditions.
"""

import cv2
import numpy as np
import mediapipe as mp
import threading
import queue
import time
import logging
from typing import Optional, Tuple, Callable, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class HandData:
    """Hand detection result from a single frame."""
    landmarks: Optional[np.ndarray]  # 21x3 array of landmarks
    confidence: float
    is_right_hand: bool
    timestamp_ms: int
    frame_width: int
    frame_height: int
    raw_frame: Optional[np.ndarray] = None  # For visualization
    
    @property
    def is_valid(self) -> bool:
        return self.landmarks is not None and self.confidence > 0


class TrackingState(Enum):
    """Current state of hand tracking."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


class HandTracker:
    """
    Real-time hand tracking using MediaPipe Hands.
    
    Features:
    - Threaded camera capture for low latency
    - Brightness normalization for low-light conditions
    - Confidence scoring and tracking loss detection
    - FPS monitoring
    - GPU acceleration when available
    """
    
    def __init__(
        self,
        camera_index: int = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        min_detection_confidence: float = 0.7,
        min_tracking_confidence: float = 0.5,
        use_gpu: bool = False,
        brightness_normalization: bool = True
    ):
        """
        Initialize hand tracker.
        
        Args:
            camera_index: Camera device index
            width: Capture width
            height: Capture height
            fps: Target FPS
            min_detection_confidence: MediaPipe detection confidence
            min_tracking_confidence: MediaPipe tracking confidence
            use_gpu: Enable GPU acceleration (requires TensorFlow GPU)
            brightness_normalization: Enable adaptive brightness
        """
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.target_fps = fps
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.use_gpu = use_gpu
        self.brightness_normalization = brightness_normalization
        
        # State
        self.state = TrackingState.STOPPED
        self._running = False
        self._capture: Optional[cv2.VideoCapture] = None
        self._hands: Optional[mp.solutions.hands.Hands] = None
        
        # Threading
        self._capture_thread: Optional[threading.Thread] = None
        self._process_thread: Optional[threading.Thread] = None
        self._frame_queue: queue.Queue = queue.Queue(maxsize=2)
        self._result_queue: queue.Queue = queue.Queue(maxsize=2)
        self._stop_event = threading.Event()
        
        # Callbacks
        self._on_hand_detected: Optional[Callable[[HandData], None]] = None
        self._on_no_detection: Optional[Callable[[], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        
        # Performance tracking
        self._fps = 0.0
        self._frame_times: List[float] = []
        self._last_frame_time = 0.0
        self._total_frames = 0
        self._dropped_frames = 0
        
        # Preprocessing state
        self._brightness_history: List[float] = []
        self._target_brightness = 127.0
    
    def start(self) -> bool:
        """
        Start hand tracking.
        
        Returns:
            True if started successfully
        """
        if self._running:
            return True
        
        self.state = TrackingState.STARTING
        
        try:
            # Initialize camera
            self._capture = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not self._capture.isOpened():
                # Try without DirectShow
                self._capture = cv2.VideoCapture(self.camera_index)
            
            if not self._capture.isOpened():
                raise RuntimeError(f"Failed to open camera {self.camera_index}")
            
            # Configure camera
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self._capture.set(cv2.CAP_PROP_FPS, self.target_fps)
            self._capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency
            
            # Get actual dimensions
            self.width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            logger.info(f"Camera opened: {self.width}x{self.height}")
            
            # Initialize MediaPipe Hands
            self._hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
                model_complexity=0  # 0 = lite model for speed
            )
            
            # Start threads
            self._stop_event.clear()
            self._running = True
            
            self._capture_thread = threading.Thread(
                target=self._capture_loop,
                name="CaptureThread",
                daemon=True
            )
            self._process_thread = threading.Thread(
                target=self._process_loop,
                name="ProcessThread",
                daemon=True
            )
            
            self._capture_thread.start()
            self._process_thread.start()
            
            self.state = TrackingState.RUNNING
            logger.info("Hand tracking started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start hand tracking: {e}")
            self.state = TrackingState.ERROR
            self._cleanup()
            if self._on_error:
                self._on_error(str(e))
            return False
    
    def stop(self) -> None:
        """Stop hand tracking."""
        if not self._running:
            return
        
        logger.info("Stopping hand tracking...")
        self._running = False
        self._stop_event.set()
        
        # Wait for threads
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=1.0)
        if self._process_thread and self._process_thread.is_alive():
            self._process_thread.join(timeout=1.0)
        
        self._cleanup()
        self.state = TrackingState.STOPPED
        logger.info("Hand tracking stopped")
    
    def _cleanup(self) -> None:
        """Release resources."""
        if self._capture:
            self._capture.release()
            self._capture = None
        
        if self._hands:
            self._hands.close()
            self._hands = None
        
        # Clear queues
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                break
        
        while not self._result_queue.empty():
            try:
                self._result_queue.get_nowait()
            except queue.Empty:
                break
    
    def _capture_loop(self) -> None:
        """Camera capture thread - grabs frames as fast as possible."""
        frame_interval = 1.0 / self.target_fps
        
        while self._running and not self._stop_event.is_set():
            try:
                start_time = time.perf_counter()
                
                ret, frame = self._capture.read()
                if not ret or frame is None:
                    self._dropped_frames += 1
                    continue
                
                timestamp_ms = int(time.time() * 1000)
                
                # Try to put frame in queue (non-blocking)
                try:
                    # Drop old frame if queue is full
                    if self._frame_queue.full():
                        try:
                            self._frame_queue.get_nowait()
                            self._dropped_frames += 1
                        except queue.Empty:
                            pass
                    
                    self._frame_queue.put_nowait((frame, timestamp_ms))
                except queue.Full:
                    self._dropped_frames += 1
                
                # Maintain target FPS
                elapsed = time.perf_counter() - start_time
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                logger.error(f"Capture error: {e}")
                if self._on_error:
                    self._on_error(f"Capture error: {e}")
    
    def _process_loop(self) -> None:
        """Processing thread - runs MediaPipe inference."""
        while self._running and not self._stop_event.is_set():
            try:
                # Get frame from queue
                try:
                    frame, timestamp_ms = self._frame_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                start_time = time.perf_counter()
                
                # Preprocess frame
                processed_frame = self._preprocess_frame(frame)
                
                # Convert to RGB for MediaPipe
                rgb_frame = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                
                # Run inference
                results = self._hands.process(rgb_frame)
                
                # Process results
                hand_data = self._process_results(
                    results, 
                    frame, 
                    timestamp_ms
                )
                
                # Update FPS
                self._update_fps(time.perf_counter() - start_time)
                
                # Notify callbacks
                if hand_data.is_valid:
                    if self._on_hand_detected:
                        self._on_hand_detected(hand_data)
                else:
                    if self._on_no_detection:
                        self._on_no_detection()
                
                # Put result in queue for external access
                try:
                    if self._result_queue.full():
                        self._result_queue.get_nowait()
                    self._result_queue.put_nowait(hand_data)
                except queue.Full:
                    pass
                    
            except Exception as e:
                logger.error(f"Processing error: {e}")
    
    def _preprocess_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Preprocess frame for better detection in low-light conditions.
        
        Args:
            frame: Raw BGR frame
            
        Returns:
            Preprocessed frame
        """
        if not self.brightness_normalization:
            return frame
        
        # Convert to LAB color space for brightness adjustment
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel = lab[:, :, 0]
        
        # Calculate current brightness
        current_brightness = np.mean(l_channel)
        
        # Update brightness history for smoothing
        self._brightness_history.append(current_brightness)
        if len(self._brightness_history) > 30:
            self._brightness_history.pop(0)
        
        avg_brightness = np.mean(self._brightness_history)
        
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # if brightness is low
        if avg_brightness < 100:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            lab[:, :, 0] = clahe.apply(l_channel)
            frame = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        # Slight Gaussian blur to reduce noise
        frame = cv2.GaussianBlur(frame, (3, 3), 0)
        
        return frame
    
    def _process_results(
        self, 
        results, 
        frame: np.ndarray,
        timestamp_ms: int
    ) -> HandData:
        """
        Process MediaPipe results into HandData.
        
        Args:
            results: MediaPipe Hands results
            frame: Original frame
            timestamp_ms: Frame timestamp
            
        Returns:
            HandData with detection results
        """
        if not results.multi_hand_landmarks:
            return HandData(
                landmarks=None,
                confidence=0.0,
                is_right_hand=True,
                timestamp_ms=timestamp_ms,
                frame_width=frame.shape[1],
                frame_height=frame.shape[0],
                raw_frame=frame
            )
        
        # Get first hand (we only track one)
        hand_landmarks = results.multi_hand_landmarks[0]
        handedness = results.multi_handedness[0]
        
        # Extract landmarks as numpy array
        landmarks = np.array([
            [lm.x, lm.y, lm.z] 
            for lm in hand_landmarks.landmark
        ], dtype=np.float32)
        
        # Get confidence and handedness
        confidence = handedness.classification[0].score
        is_right = handedness.classification[0].label == "Right"
        
        return HandData(
            landmarks=landmarks,
            confidence=confidence,
            is_right_hand=is_right,
            timestamp_ms=timestamp_ms,
            frame_width=frame.shape[1],
            frame_height=frame.shape[0],
            raw_frame=frame
        )
    
    def _update_fps(self, frame_time: float) -> None:
        """Update FPS calculation."""
        self._frame_times.append(frame_time)
        if len(self._frame_times) > 30:
            self._frame_times.pop(0)
        
        if self._frame_times:
            avg_time = sum(self._frame_times) / len(self._frame_times)
            self._fps = 1.0 / avg_time if avg_time > 0 else 0.0
        
        self._total_frames += 1
    
    def get_latest_result(self) -> Optional[HandData]:
        """
        Get the latest hand detection result.
        
        Returns:
            Latest HandData or None if no result available
        """
        try:
            # Get latest, discarding older results
            result = None
            while not self._result_queue.empty():
                result = self._result_queue.get_nowait()
            return result
        except queue.Empty:
            return None
    
    def set_on_hand_detected(self, callback: Callable[[HandData], None]) -> None:
        """Set callback for when hand is detected."""
        self._on_hand_detected = callback
    
    def set_on_no_detection(self, callback: Callable[[], None]) -> None:
        """Set callback for when no hand is detected."""
        self._on_no_detection = callback
    
    def set_on_error(self, callback: Callable[[str], None]) -> None:
        """Set callback for errors."""
        self._on_error = callback
    
    @property
    def fps(self) -> float:
        """Current FPS."""
        return self._fps
    
    @property
    def total_frames(self) -> int:
        """Total frames processed."""
        return self._total_frames
    
    @property
    def dropped_frames(self) -> int:
        """Number of dropped frames."""
        return self._dropped_frames
    
    @property
    def drop_rate(self) -> float:
        """Frame drop rate as percentage."""
        if self._total_frames == 0:
            return 0.0
        return self._dropped_frames / (self._total_frames + self._dropped_frames)
    
    @property
    def is_running(self) -> bool:
        """Check if tracker is running."""
        return self._running and self.state == TrackingState.RUNNING
    
    def update_confidence_thresholds(
        self, 
        detection: float, 
        tracking: float
    ) -> None:
        """
        Update confidence thresholds.
        Requires restart to take effect.
        """
        self.min_detection_confidence = detection
        self.min_tracking_confidence = tracking
    
    def get_camera_info(self) -> dict:
        """Get camera information."""
        if not self._capture:
            return {}
        
        return {
            'width': int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': self._capture.get(cv2.CAP_PROP_FPS),
            'backend': self._capture.getBackendName(),
        }


def draw_landmarks(
    frame: np.ndarray,
    landmarks: np.ndarray,
    connections: bool = True
) -> np.ndarray:
    """
    Draw hand landmarks on frame for visualization.
    
    Args:
        frame: BGR frame to draw on
        landmarks: 21x3 landmark array (normalized coordinates)
        connections: Draw connections between landmarks
        
    Returns:
        Frame with landmarks drawn
    """
    if landmarks is None:
        return frame
    
    frame = frame.copy()
    h, w = frame.shape[:2]
    
    # Convert normalized to pixel coordinates
    points = []
    for lm in landmarks:
        x = int(lm[0] * w)
        y = int(lm[1] * h)
        points.append((x, y))
    
    # Draw connections
    if connections:
        # MediaPipe hand connections
        connections_list = [
            (0, 1), (1, 2), (2, 3), (3, 4),  # Thumb
            (0, 5), (5, 6), (6, 7), (7, 8),  # Index
            (0, 9), (9, 10), (10, 11), (11, 12),  # Middle
            (0, 13), (13, 14), (14, 15), (15, 16),  # Ring
            (0, 17), (17, 18), (18, 19), (19, 20),  # Pinky
            (5, 9), (9, 13), (13, 17),  # Palm
        ]
        
        for start, end in connections_list:
            cv2.line(frame, points[start], points[end], (0, 255, 0), 2)
    
    # Draw landmarks
    for i, point in enumerate(points):
        # Different colors for different fingers
        if i == 0:  # Wrist
            color = (255, 255, 255)
        elif i <= 4:  # Thumb
            color = (255, 0, 0)
        elif i <= 8:  # Index
            color = (0, 255, 0)
        elif i <= 12:  # Middle
            color = (0, 0, 255)
        elif i <= 16:  # Ring
            color = (255, 255, 0)
        else:  # Pinky
            color = (255, 0, 255)
        
        cv2.circle(frame, point, 5, color, -1)
        cv2.circle(frame, point, 7, (0, 0, 0), 1)
    
    return frame
