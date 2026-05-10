"""
WavePoint - Configuration Management

Handles loading, saving, and validating configuration settings.
Supports user profiles for different environments/preferences.
"""

import json
import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class HandPreference(str, Enum):
    """Which hand to track."""
    LEFT = "left"
    RIGHT = "right"


@dataclass
class CalibrationSettings:
    """Calibration data for coordinate mapping."""
    cam_left: float = 0.1
    cam_right: float = 0.9
    cam_top: float = 0.1
    cam_bottom: float = 0.9
    screen_left: int = 0
    screen_right: int = 1920
    screen_top: int = 0
    screen_bottom: int = 1080
    dead_zone_radius: float = 0.02

    def is_valid(self) -> bool:
        return (self.cam_right > self.cam_left and
                self.cam_bottom > self.cam_top and
                self.screen_right > self.screen_left and
                self.screen_bottom > self.screen_top)


@dataclass
class SmoothingSettings:
    """Cursor smoothing configuration."""
    alpha: float = 0.3  # Exponential smoothing factor [0-1], lower = smoother
    velocity_scale: float = 1.0  # Cursor speed multiplier
    history_size: int = 5  # Frames to average
    jitter_threshold: float = 2.0  # Pixels below which movement is ignored
    acceleration_factor: float = 1.5  # Acceleration for large movements


@dataclass
class GestureSettings:
    """Gesture detection thresholds."""
    min_detection_confidence: float = 0.7
    min_tracking_confidence: float = 0.5
    min_gesture_confidence: float = 0.6
    dwell_time_click_ms: int = 100
    dwell_time_drag_ms: int = 300
    debounce_time_ms: int = 200
    tracking_lost_timeout_ms: int = 500
    pinch_threshold: float = 0.05
    pinch_release_threshold: float = 0.08
    finger_extended_threshold: float = 0.1


@dataclass
class GestureEnableSettings:
    """Which gestures are enabled."""
    left_click: bool = True
    right_click: bool = True
    scroll: bool = True
    drag: bool = True


@dataclass
class CameraSettings:
    """Camera configuration."""
    device_index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30
    auto_exposure: bool = True
    brightness_normalization: bool = True


@dataclass
class UserProfile:
    """Complete user profile with all settings."""
    name: str = "Default"
    hand_preference: HandPreference = HandPreference.RIGHT
    calibration: CalibrationSettings = field(
        default_factory=CalibrationSettings)
    smoothing: SmoothingSettings = field(default_factory=SmoothingSettings)
    gestures: GestureSettings = field(default_factory=GestureSettings)
    gesture_enable: GestureEnableSettings = field(
        default_factory=GestureEnableSettings)
    camera: CameraSettings = field(default_factory=CameraSettings)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['hand_preference'] = self.hand_preference.value
        # Convert numpy float32 to Python float for JSON serialization
        data = self._convert_numpy_types(data)
        return data

    def _convert_numpy_types(self, obj: Any) -> Any:
        """Recursively convert numpy types to Python native types."""
        import numpy as np
        if isinstance(obj, dict):
            return {k: self._convert_numpy_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(v) for v in obj]
        elif isinstance(obj, (np.floating, np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, (np.integer, np.int32, np.int64)):
            return int(obj)
        return obj

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserProfile':
        """Create from dictionary."""
        if 'hand_preference' in data:
            data['hand_preference'] = HandPreference(data['hand_preference'])

        # Convert nested dicts to dataclasses
        if 'calibration' in data and isinstance(data['calibration'], dict):
            data['calibration'] = CalibrationSettings(**data['calibration'])
        if 'smoothing' in data and isinstance(data['smoothing'], dict):
            data['smoothing'] = SmoothingSettings(**data['smoothing'])
        if 'gestures' in data and isinstance(data['gestures'], dict):
            data['gestures'] = GestureSettings(**data['gestures'])
        if 'gesture_enable' in data and isinstance(data['gesture_enable'], dict):
            data['gesture_enable'] = GestureEnableSettings(
                **data['gesture_enable'])
        if 'camera' in data and isinstance(data['camera'], dict):
            data['camera'] = CameraSettings(**data['camera'])

        return cls(**data)


@dataclass
class AppSettings:
    """Application-level settings."""
    start_minimized: bool = False
    start_with_windows: bool = False
    show_notifications: bool = True
    check_updates: bool = False  # Disabled - no cloud
    last_profile: str = "Default"
    test_mode_on_start: bool = True  # Safety: always start in test mode


class Config:
    """
    Configuration manager for WavePoint.

    Handles:
    - Loading/saving configuration
    - Managing user profiles
    - Providing defaults
    - Validating settings
    """

    CONFIG_DIR_NAME = "WavePoint"
    LEGACY_CONFIG_DIR_NAME = "GestureMouse"
    CONFIG_FILE_NAME = "config.json"
    PROFILES_DIR_NAME = "profiles"

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize configuration manager.

        Args:
            config_dir: Override config directory (for testing)
        """
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            # Use %APPDATA%\WavePoint on Windows
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            self.config_dir = Path(appdata) / self.CONFIG_DIR_NAME
            legacy_config_dir = Path(appdata) / self.LEGACY_CONFIG_DIR_NAME
            if not self.config_dir.exists() and legacy_config_dir.exists():
                try:
                    shutil.copytree(legacy_config_dir, self.config_dir, dirs_exist_ok=True)
                except Exception:
                    pass

        self.config_file = self.config_dir / self.CONFIG_FILE_NAME
        self.profiles_dir = self.config_dir / self.PROFILES_DIR_NAME

        # Current state
        self.app_settings = AppSettings()
        self.current_profile = UserProfile()
        self.profiles: Dict[str, UserProfile] = {}

        # Ensure directories exist
        self._ensure_directories()

        # Load configuration
        self.load()

    def _ensure_directories(self) -> None:
        """Create config directories if they don't exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> bool:
        """
        Load configuration from disk.

        Returns:
            True if loaded successfully, False if using defaults
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Load app settings
                if 'app_settings' in data:
                    self.app_settings = AppSettings(**data['app_settings'])

                # Load profiles
                self._load_profiles()

                # Set current profile
                if self.app_settings.last_profile in self.profiles:
                    self.current_profile = self.profiles[self.app_settings.last_profile]
                elif self.profiles:
                    self.current_profile = next(iter(self.profiles.values()))

                logger.info(f"Configuration loaded from {self.config_file}")
                return True
            else:
                # Create default configuration
                self._create_defaults()
                self.save()
                logger.info("Created default configuration")
                return False

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            self._create_defaults()
            return False

    def save(self) -> bool:
        """
        Save configuration to disk.

        Returns:
            True if saved successfully
        """
        try:
            # Save app settings
            data = {
                'app_settings': asdict(self.app_settings),
                'version': '1.0.0'
            }

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            # Save profiles
            self._save_profiles()

            logger.info(f"Configuration saved to {self.config_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False

    def _load_profiles(self) -> None:
        """Load all user profiles from profiles directory."""
        self.profiles.clear()

        for profile_file in self.profiles_dir.glob("*.json"):
            try:
                with open(profile_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                profile = UserProfile.from_dict(data)
                self.profiles[profile.name] = profile
            except Exception as e:
                logger.warning(f"Failed to load profile {profile_file}: {e}")

        # Ensure at least default profile exists
        if "Default" not in self.profiles:
            self.profiles["Default"] = UserProfile()

    def _save_profiles(self) -> None:
        """Save all user profiles to profiles directory."""
        for name, profile in self.profiles.items():
            profile_file = self.profiles_dir / f"{name}.json"
            try:
                with open(profile_file, 'w', encoding='utf-8') as f:
                    json.dump(profile.to_dict(), f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save profile {name}: {e}")

    def _create_defaults(self) -> None:
        """Create default configuration."""
        self.app_settings = AppSettings()
        self.profiles = {"Default": UserProfile()}
        self.current_profile = self.profiles["Default"]

    def get_profile(self, name: str) -> Optional[UserProfile]:
        """Get a profile by name."""
        return self.profiles.get(name)

    def set_current_profile(self, name: str) -> bool:
        """
        Set the current active profile.

        Args:
            name: Profile name

        Returns:
            True if profile exists and was set
        """
        if name in self.profiles:
            self.current_profile = self.profiles[name]
            self.app_settings.last_profile = name
            return True
        return False

    def create_profile(self, name: str, copy_from: Optional[str] = None) -> UserProfile:
        """
        Create a new profile.

        Args:
            name: New profile name
            copy_from: Optional profile to copy settings from

        Returns:
            The new profile
        """
        if copy_from and copy_from in self.profiles:
            # Deep copy by serializing/deserializing
            data = self.profiles[copy_from].to_dict()
            data['name'] = name
            profile = UserProfile.from_dict(data)
        else:
            profile = UserProfile(name=name)

        self.profiles[name] = profile
        return profile

    def delete_profile(self, name: str) -> bool:
        """
        Delete a profile.

        Args:
            name: Profile name (cannot delete "Default")

        Returns:
            True if deleted
        """
        if name == "Default":
            logger.warning("Cannot delete Default profile")
            return False

        if name in self.profiles:
            del self.profiles[name]

            # Delete file
            profile_file = self.profiles_dir / f"{name}.json"
            if profile_file.exists():
                profile_file.unlink()

            # Switch to default if current was deleted
            if self.current_profile.name == name:
                self.set_current_profile("Default")

            return True
        return False

    def list_profiles(self) -> List[str]:
        """Get list of profile names."""
        return list(self.profiles.keys())

    def update_calibration(self, calibration: CalibrationSettings) -> None:
        """Update calibration in current profile."""
        self.current_profile.calibration = calibration
        self.save()

    def update_smoothing(self, smoothing: SmoothingSettings) -> None:
        """Update smoothing settings in current profile."""
        self.current_profile.smoothing = smoothing
        self.save()

    def update_gestures(self, gestures: GestureSettings) -> None:
        """Update gesture settings in current profile."""
        self.current_profile.gestures = gestures
        self.save()

    def get_engine_config(self):
        """
        Get configuration formatted for the C++ engine.

        Returns:
            EngineConfig object for the C++ core
        """
        try:
            from . import gesture_mouse_core as core

            config = core.EngineConfig()

            # Calibration
            config.calibration.cam_left = self.current_profile.calibration.cam_left
            config.calibration.cam_right = self.current_profile.calibration.cam_right
            config.calibration.cam_top = self.current_profile.calibration.cam_top
            config.calibration.cam_bottom = self.current_profile.calibration.cam_bottom
            config.calibration.screen_left = self.current_profile.calibration.screen_left
            config.calibration.screen_right = self.current_profile.calibration.screen_right
            config.calibration.screen_top = self.current_profile.calibration.screen_top
            config.calibration.screen_bottom = self.current_profile.calibration.screen_bottom
            config.calibration.dead_zone_radius = self.current_profile.calibration.dead_zone_radius

            # Smoothing
            config.smoothing.alpha = self.current_profile.smoothing.alpha
            config.smoothing.velocity_scale = self.current_profile.smoothing.velocity_scale
            config.smoothing.history_size = self.current_profile.smoothing.history_size
            config.smoothing.jitter_threshold = self.current_profile.smoothing.jitter_threshold
            config.smoothing.acceleration_factor = self.current_profile.smoothing.acceleration_factor

            # Thresholds
            config.thresholds.min_detection_confidence = self.current_profile.gestures.min_detection_confidence
            config.thresholds.min_tracking_confidence = self.current_profile.gestures.min_tracking_confidence
            config.thresholds.min_gesture_confidence = self.current_profile.gestures.min_gesture_confidence
            config.thresholds.dwell_time_click_ms = self.current_profile.gestures.dwell_time_click_ms
            config.thresholds.dwell_time_drag_ms = self.current_profile.gestures.dwell_time_drag_ms
            config.thresholds.debounce_time_ms = self.current_profile.gestures.debounce_time_ms
            config.thresholds.tracking_lost_timeout_ms = self.current_profile.gestures.tracking_lost_timeout_ms
            config.thresholds.pinch_threshold = self.current_profile.gestures.pinch_threshold
            config.thresholds.pinch_release_threshold = self.current_profile.gestures.pinch_release_threshold
            config.thresholds.finger_extended_threshold = self.current_profile.gestures.finger_extended_threshold

            # General
            config.is_right_hand = self.current_profile.hand_preference == HandPreference.RIGHT
            config.enable_left_click = self.current_profile.gesture_enable.left_click
            config.enable_right_click = self.current_profile.gesture_enable.right_click
            config.enable_scroll = self.current_profile.gesture_enable.scroll
            config.enable_drag = self.current_profile.gesture_enable.drag
            config.target_fps = self.current_profile.camera.fps

            return config

        except ImportError:
            logger.warning("C++ core not available, returning None")
            return None
