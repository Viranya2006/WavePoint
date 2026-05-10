"""
WavePoint - Hand Gesture Mouse Control

A production-grade Windows application for controlling your laptop
using hand gestures detected through a webcam.
"""

__version__ = "1.0.0"
__author__ = "WavePoint Team"

from .app import WavePointApp
from .config import Config, UserProfile
from .hand_tracker import HandTracker
from .calibration import CalibrationManager

__all__ = [
    "WavePointApp",
    "Config",
    "UserProfile", 
    "HandTracker",
    "CalibrationManager",
]
