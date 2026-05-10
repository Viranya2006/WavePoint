#pragma once
/**
 * WavePoint - Configuration Constants
 * 
 * Compile-time constants and default values for the gesture engine.
 */

#include <cstdint>

namespace gesture_mouse {
namespace config {

// ============================================================================
// VERSION
// ============================================================================

constexpr int VERSION_MAJOR = 1;
constexpr int VERSION_MINOR = 0;
constexpr int VERSION_PATCH = 0;

// ============================================================================
// THREADING
// ============================================================================

constexpr int QUEUE_CAPACITY = 8;              // Thread-safe queue size
constexpr int MAX_FRAME_SKIP = 3;              // Max frames to skip if behind

// ============================================================================
// TIMING (milliseconds)
// ============================================================================

constexpr int64_t DEFAULT_FRAME_BUDGET_MS = 33;    // ~30 FPS
constexpr int64_t MIN_FRAME_TIME_MS = 16;          // ~60 FPS max
constexpr int64_t TRACKING_TIMEOUT_MS = 500;       // Auto-pause after this
constexpr int64_t CLICK_DEBOUNCE_MS = 200;         // Min time between clicks
constexpr int64_t DWELL_TIME_MS = 100;             // Gesture confirmation time
constexpr int64_t DRAG_DWELL_TIME_MS = 300;        // Drag confirmation time

// ============================================================================
// GESTURE DETECTION
// ============================================================================

constexpr float DEFAULT_MIN_DETECTION_CONFIDENCE = 0.7f;
constexpr float DEFAULT_MIN_TRACKING_CONFIDENCE = 0.5f;
constexpr float DEFAULT_MIN_GESTURE_CONFIDENCE = 0.6f;

constexpr float PINCH_THRESHOLD = 0.05f;           // Normalized distance
constexpr float PINCH_RELEASE_THRESHOLD = 0.08f;   // Hysteresis
constexpr float FINGER_EXTENDED_THRESHOLD = 0.1f;
constexpr float FIST_THRESHOLD = 0.08f;            // All fingers curled

constexpr int MIN_CONSECUTIVE_FRAMES = 3;          // Frames to confirm gesture

// ============================================================================
// CURSOR SMOOTHING
// ============================================================================

constexpr float DEFAULT_SMOOTHING_ALPHA = 0.3f;    // Lower = smoother
constexpr float DEFAULT_VELOCITY_SCALE = 1.0f;
constexpr int DEFAULT_HISTORY_SIZE = 5;
constexpr float DEFAULT_JITTER_THRESHOLD = 2.0f;   // Pixels
constexpr float DEFAULT_ACCELERATION = 1.5f;

// ============================================================================
// COORDINATE MAPPING
// ============================================================================

constexpr float DEFAULT_CAM_MARGIN = 0.1f;         // Edge margin in camera space
constexpr float DEFAULT_DEAD_ZONE = 0.02f;         // Center dead zone radius

// ============================================================================
// SCROLL
// ============================================================================

constexpr int SCROLL_LINES_PER_TICK = 3;           // Lines per scroll event
constexpr float SCROLL_SENSITIVITY = 100.0f;       // Pixels of movement per tick
constexpr int64_t SCROLL_DEBOUNCE_MS = 50;         // Min time between scrolls

// ============================================================================
// SAFETY
// ============================================================================

constexpr int MAX_CURSOR_JUMP_PIXELS = 500;        // Max single-frame movement
constexpr float CONFIDENCE_HYSTERESIS = 0.1f;      // Prevent confidence flicker
constexpr int LOST_TRACKING_GRACE_FRAMES = 5;      // Frames before pause

} // namespace config
} // namespace gesture_mouse
