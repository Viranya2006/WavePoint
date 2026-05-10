#pragma once
/**
 * WavePoint - Core Type Definitions
 * 
 * This file contains all fundamental types used throughout the gesture engine.
 * These types are designed for thread-safety and minimal memory footprint.
 */

#include <cstdint>
#include <array>
#include <chrono>
#include <atomic>

namespace gesture_mouse {

// ============================================================================
// LANDMARK TYPES
// ============================================================================

/**
 * 3D point representing a hand landmark.
 * Coordinates are normalized [0, 1] relative to image dimensions.
 * z represents relative depth (negative = closer to camera).
 */
struct Point3D {
    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
    
    Point3D() = default;
    Point3D(float x_, float y_, float z_) : x(x_), y(y_), z(z_) {}
};

/**
 * 2D point for screen coordinates.
 */
struct Point2D {
    float x = 0.0f;
    float y = 0.0f;
    
    Point2D() = default;
    Point2D(float x_, float y_) : x(x_), y(y_) {}
};

/**
 * Integer screen coordinates for actual cursor positioning.
 */
struct ScreenPoint {
    int x = 0;
    int y = 0;
    
    ScreenPoint() = default;
    ScreenPoint(int x_, int y_) : x(x_), y(y_) {}
};

/**
 * MediaPipe hand landmark indices.
 * These correspond to the 21 landmarks detected by MediaPipe Hands.
 */
enum class LandmarkIndex : uint8_t {
    WRIST = 0,
    THUMB_CMC = 1,
    THUMB_MCP = 2,
    THUMB_IP = 3,
    THUMB_TIP = 4,
    INDEX_MCP = 5,
    INDEX_PIP = 6,
    INDEX_DIP = 7,
    INDEX_TIP = 8,
    MIDDLE_MCP = 9,
    MIDDLE_PIP = 10,
    MIDDLE_DIP = 11,
    MIDDLE_TIP = 12,
    RING_MCP = 13,
    RING_PIP = 14,
    RING_DIP = 15,
    RING_TIP = 16,
    PINKY_MCP = 17,
    PINKY_PIP = 18,
    PINKY_DIP = 19,
    PINKY_TIP = 20,
    COUNT = 21
};

/**
 * Complete hand landmark data from a single frame.
 * Contains all 21 landmarks plus metadata.
 */
struct HandLandmarks {
    std::array<Point3D, 21> landmarks;
    float confidence = 0.0f;           // Overall detection confidence [0, 1]
    bool is_right_hand = true;         // Handedness
    int64_t timestamp_ms = 0;          // Frame timestamp
    int frame_width = 0;               // Source frame dimensions
    int frame_height = 0;
    
    const Point3D& get(LandmarkIndex idx) const {
        return landmarks[static_cast<size_t>(idx)];
    }
    
    bool is_valid() const {
        return confidence > 0.0f && frame_width > 0 && frame_height > 0;
    }
};

// ============================================================================
// GESTURE TYPES
// ============================================================================

/**
 * Recognized gesture types.
 * Each gesture maps to a specific mouse action.
 */
enum class GestureType : uint8_t {
    NONE = 0,           // No hand detected or tracking lost
    NEUTRAL,            // Open palm - no action, cursor follows
    POINTING,           // Index finger extended - cursor movement
    LEFT_CLICK,         // Thumb + index pinch
    RIGHT_CLICK,        // Thumb + middle pinch
    SCROLL,             // Two fingers vertical movement
    DRAG,               // Closed fist - drag mode
    PAUSE,              // Hand removed or uncertain - pause all input
    
    COUNT
};

/**
 * Convert gesture type to human-readable string.
 */
inline const char* gesture_to_string(GestureType type) {
    switch (type) {
        case GestureType::NONE:        return "None";
        case GestureType::NEUTRAL:     return "Neutral";
        case GestureType::POINTING:    return "Pointing";
        case GestureType::LEFT_CLICK:  return "Left Click";
        case GestureType::RIGHT_CLICK: return "Right Click";
        case GestureType::SCROLL:      return "Scroll";
        case GestureType::DRAG:        return "Drag";
        case GestureType::PAUSE:       return "Pause";
        default:                       return "Unknown";
    }
}

/**
 * Gesture state with timing and confidence information.
 * Used by the state machine for temporal filtering.
 */
struct GestureState {
    GestureType type = GestureType::NONE;
    float confidence = 0.0f;           // Gesture-specific confidence [0, 1]
    int64_t start_time_ms = 0;         // When this gesture was first detected
    int64_t last_update_ms = 0;        // Last frame this gesture was seen
    int consecutive_frames = 0;        // Frames in a row with this gesture
    bool is_confirmed = false;         // Has met dwell time requirement
    
    void reset() {
        type = GestureType::NONE;
        confidence = 0.0f;
        start_time_ms = 0;
        last_update_ms = 0;
        consecutive_frames = 0;
        is_confirmed = false;
    }
};

// ============================================================================
// ACTION TYPES
// ============================================================================

/**
 * Mouse action to be injected into the OS.
 */
enum class MouseAction : uint8_t {
    NONE = 0,
    MOVE,
    LEFT_DOWN,
    LEFT_UP,
    LEFT_CLICK,
    RIGHT_DOWN,
    RIGHT_UP,
    RIGHT_CLICK,
    SCROLL_UP,
    SCROLL_DOWN,
    DRAG_START,
    DRAG_END
};

/**
 * Complete mouse command ready for injection.
 */
struct MouseCommand {
    MouseAction action = MouseAction::NONE;
    ScreenPoint position;
    int scroll_delta = 0;              // For scroll actions
    int64_t timestamp_ms = 0;
    
    bool is_valid() const {
        return action != MouseAction::NONE;
    }
};

// ============================================================================
// CONFIGURATION TYPES
// ============================================================================

/**
 * Calibration data for coordinate mapping.
 */
struct CalibrationData {
    // Camera space bounds (normalized coordinates where hand was detected)
    float cam_left = 0.1f;
    float cam_right = 0.9f;
    float cam_top = 0.1f;
    float cam_bottom = 0.9f;
    
    // Screen space bounds (pixels)
    int screen_left = 0;
    int screen_right = 1920;
    int screen_top = 0;
    int screen_bottom = 1080;
    
    // Dead zone (normalized, center of camera space)
    float dead_zone_radius = 0.02f;
    
    bool is_valid() const {
        return cam_right > cam_left && cam_bottom > cam_top &&
               screen_right > screen_left && screen_bottom > screen_top;
    }
};

/**
 * Smoothing configuration for cursor movement.
 */
struct SmoothingConfig {
    float alpha = 0.3f;                // Exponential smoothing factor [0, 1]
    float velocity_scale = 1.0f;       // Cursor speed multiplier
    int history_size = 5;              // Frames to average
    float jitter_threshold = 2.0f;     // Pixels below which movement is ignored
    float acceleration_factor = 1.5f;  // Acceleration for large movements
};

/**
 * Gesture detection thresholds.
 */
struct GestureThresholds {
    // Confidence thresholds
    float min_detection_confidence = 0.7f;
    float min_tracking_confidence = 0.5f;
    float min_gesture_confidence = 0.6f;
    
    // Timing thresholds (milliseconds)
    int64_t dwell_time_click_ms = 100;     // Time to confirm a click
    int64_t dwell_time_drag_ms = 300;      // Time to confirm drag start
    int64_t debounce_time_ms = 200;        // Minimum time between clicks
    int64_t tracking_lost_timeout_ms = 500; // Time before auto-pause
    
    // Distance thresholds (normalized)
    float pinch_threshold = 0.05f;         // Distance for pinch detection
    float pinch_release_threshold = 0.08f; // Hysteresis for pinch release
    float finger_extended_threshold = 0.1f; // Distance for extended finger
};

/**
 * Complete engine configuration.
 */
struct EngineConfig {
    CalibrationData calibration;
    SmoothingConfig smoothing;
    GestureThresholds thresholds;
    
    bool is_enabled = false;           // Master enable/disable
    bool is_right_hand = true;         // Which hand to track
    bool enable_left_click = true;
    bool enable_right_click = true;
    bool enable_scroll = true;
    bool enable_drag = true;
    
    int target_fps = 30;
    bool use_gpu = false;              // GPU acceleration if available
};

// ============================================================================
// PERFORMANCE TYPES
// ============================================================================

/**
 * Performance metrics for monitoring.
 */
struct PerformanceMetrics {
    std::atomic<float> fps{0.0f};
    std::atomic<float> frame_time_ms{0.0f};
    std::atomic<float> inference_time_ms{0.0f};
    std::atomic<float> gesture_time_ms{0.0f};
    std::atomic<float> injection_time_ms{0.0f};
    std::atomic<int> dropped_frames{0};
    std::atomic<int> total_frames{0};
};

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Get current timestamp in milliseconds.
 */
inline int64_t get_timestamp_ms() {
    using namespace std::chrono;
    return duration_cast<milliseconds>(
        steady_clock::now().time_since_epoch()
    ).count();
}

/**
 * Calculate Euclidean distance between two 3D points.
 */
inline float distance_3d(const Point3D& a, const Point3D& b) {
    float dx = a.x - b.x;
    float dy = a.y - b.y;
    float dz = a.z - b.z;
    return std::sqrt(dx * dx + dy * dy + dz * dz);
}

/**
 * Calculate 2D distance (ignoring z).
 */
inline float distance_2d(const Point3D& a, const Point3D& b) {
    float dx = a.x - b.x;
    float dy = a.y - b.y;
    return std::sqrt(dx * dx + dy * dy);
}

} // namespace gesture_mouse
