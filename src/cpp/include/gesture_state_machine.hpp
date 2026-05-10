#pragma once
/**
 * WavePoint - Gesture State Machine
 * 
 * Implements a robust state machine for gesture recognition with:
 * - Temporal filtering (dwell time)
 * - Hysteresis to prevent flickering
 * - Confidence-based transitions
 * - Safe failure modes
 */

#include "gesture_types.hpp"
#include "config.hpp"
#include <array>
#include <functional>

namespace gesture_mouse {

/**
 * Gesture classifier result from analyzing hand landmarks.
 */
struct GestureClassification {
    GestureType type = GestureType::NONE;
    float confidence = 0.0f;
    Point3D cursor_point;      // Point to use for cursor (usually index tip)
    float scroll_delta = 0.0f; // For scroll gesture
};

/**
 * State machine for robust gesture recognition.
 * 
 * Features:
 * - Requires multiple consecutive frames to confirm a gesture
 * - Uses hysteresis to prevent rapid state changes
 * - Implements dwell time for click actions
 * - Auto-pauses on tracking loss
 */
class GestureStateMachine {
public:
    GestureStateMachine();
    explicit GestureStateMachine(const GestureThresholds& thresholds);
    
    /**
     * Process hand landmarks and return the current gesture state.
     * 
     * @param landmarks Hand landmark data from MediaPipe
     * @return Current gesture state after temporal filtering
     */
    GestureState process(const HandLandmarks& landmarks);
    
    /**
     * Process when no hand is detected.
     * Handles tracking loss timeout.
     */
    GestureState process_no_detection();
    
    /**
     * Get the current confirmed gesture state.
     */
    const GestureState& get_current_state() const;
    
    /**
     * Get the raw (unfiltered) gesture classification.
     */
    const GestureClassification& get_raw_classification() const;
    
    /**
     * Reset the state machine.
     */
    void reset();
    
    /**
     * Update thresholds.
     */
    void set_thresholds(const GestureThresholds& thresholds);
    
    /**
     * Check if currently in a click-pending state.
     */
    bool is_click_pending() const;
    
    /**
     * Check if tracking is considered lost.
     */
    bool is_tracking_lost() const;
    
    /**
     * Get the cursor point from the current gesture.
     */
    Point3D get_cursor_point() const;
    
    /**
     * Get scroll delta if in scroll gesture.
     */
    float get_scroll_delta() const;

private:
    GestureThresholds thresholds_;
    
    // Current states
    GestureState current_state_;
    GestureState pending_state_;
    GestureClassification raw_classification_;
    
    // Tracking state
    int64_t last_detection_time_ms_;
    int frames_without_detection_;
    bool tracking_lost_;
    
    // Click debouncing
    int64_t last_click_time_ms_;
    GestureType last_click_type_;
    
    // Scroll state
    float last_scroll_y_;
    float accumulated_scroll_;
    
    // Previous landmarks for velocity calculation
    HandLandmarks previous_landmarks_;
    bool has_previous_landmarks_;
    
    // Classify gesture from landmarks
    GestureClassification classify_gesture(const HandLandmarks& landmarks);
    
    // Individual gesture detectors
    bool detect_pinch(const HandLandmarks& landmarks, 
                      LandmarkIndex finger_tip, 
                      float& confidence);
    bool detect_pointing(const HandLandmarks& landmarks, float& confidence);
    bool detect_fist(const HandLandmarks& landmarks, float& confidence);
    bool detect_open_palm(const HandLandmarks& landmarks, float& confidence);
    bool detect_scroll(const HandLandmarks& landmarks, float& confidence, float& delta);
    
    // Helper functions
    bool is_finger_extended(const HandLandmarks& landmarks, 
                            LandmarkIndex mcp, 
                            LandmarkIndex pip, 
                            LandmarkIndex tip);
    bool is_finger_curled(const HandLandmarks& landmarks,
                          LandmarkIndex mcp,
                          LandmarkIndex pip,
                          LandmarkIndex tip);
    float calculate_pinch_distance(const HandLandmarks& landmarks,
                                   LandmarkIndex tip1,
                                   LandmarkIndex tip2);
    
    // State transition logic
    bool should_transition(const GestureClassification& classification);
    void update_state(const GestureClassification& classification, int64_t timestamp_ms);
};

// ============================================================================
// IMPLEMENTATION
// ============================================================================

inline GestureStateMachine::GestureStateMachine()
    : last_detection_time_ms_(0)
    , frames_without_detection_(0)
    , tracking_lost_(true)
    , last_click_time_ms_(0)
    , last_click_type_(GestureType::NONE)
    , last_scroll_y_(0.0f)
    , accumulated_scroll_(0.0f)
    , has_previous_landmarks_(false)
{
    thresholds_.min_detection_confidence = config::DEFAULT_MIN_DETECTION_CONFIDENCE;
    thresholds_.min_tracking_confidence = config::DEFAULT_MIN_TRACKING_CONFIDENCE;
    thresholds_.min_gesture_confidence = config::DEFAULT_MIN_GESTURE_CONFIDENCE;
    thresholds_.dwell_time_click_ms = config::DWELL_TIME_MS;
    thresholds_.dwell_time_drag_ms = config::DRAG_DWELL_TIME_MS;
    thresholds_.debounce_time_ms = config::CLICK_DEBOUNCE_MS;
    thresholds_.tracking_lost_timeout_ms = config::TRACKING_TIMEOUT_MS;
    thresholds_.pinch_threshold = config::PINCH_THRESHOLD;
    thresholds_.pinch_release_threshold = config::PINCH_RELEASE_THRESHOLD;
    thresholds_.finger_extended_threshold = config::FINGER_EXTENDED_THRESHOLD;
}

inline GestureStateMachine::GestureStateMachine(const GestureThresholds& thresholds)
    : thresholds_(thresholds)
    , last_detection_time_ms_(0)
    , frames_without_detection_(0)
    , tracking_lost_(true)
    , last_click_time_ms_(0)
    , last_click_type_(GestureType::NONE)
    , last_scroll_y_(0.0f)
    , accumulated_scroll_(0.0f)
    , has_previous_landmarks_(false)
{}

inline GestureState GestureStateMachine::process(const HandLandmarks& landmarks) {
    int64_t now = landmarks.timestamp_ms;
    if (now == 0) {
        now = get_timestamp_ms();
    }
    
    // Check detection confidence
    if (landmarks.confidence < thresholds_.min_detection_confidence) {
        return process_no_detection();
    }
    
    // Update tracking state
    last_detection_time_ms_ = now;
    frames_without_detection_ = 0;
    tracking_lost_ = false;
    
    // Classify the gesture
    raw_classification_ = classify_gesture(landmarks);
    
    // Update state machine
    update_state(raw_classification_, now);
    
    // Store for next frame
    previous_landmarks_ = landmarks;
    has_previous_landmarks_ = true;
    
    return current_state_;
}

inline GestureState GestureStateMachine::process_no_detection() {
    int64_t now = get_timestamp_ms();
    frames_without_detection_++;
    
    // Check for tracking loss timeout
    if (last_detection_time_ms_ > 0) {
        int64_t elapsed = now - last_detection_time_ms_;
        if (elapsed > thresholds_.tracking_lost_timeout_ms) {
            tracking_lost_ = true;
            current_state_.type = GestureType::PAUSE;
            current_state_.confidence = 0.0f;
            current_state_.is_confirmed = true;
        }
    } else {
        tracking_lost_ = true;
        current_state_.type = GestureType::PAUSE;
        current_state_.is_confirmed = true;
    }
    
    // Clear raw classification
    raw_classification_.type = GestureType::NONE;
    raw_classification_.confidence = 0.0f;
    
    return current_state_;
}

inline const GestureState& GestureStateMachine::get_current_state() const {
    return current_state_;
}

inline const GestureClassification& GestureStateMachine::get_raw_classification() const {
    return raw_classification_;
}

inline void GestureStateMachine::reset() {
    current_state_.reset();
    pending_state_.reset();
    raw_classification_ = GestureClassification{};
    last_detection_time_ms_ = 0;
    frames_without_detection_ = 0;
    tracking_lost_ = true;
    last_click_time_ms_ = 0;
    last_click_type_ = GestureType::NONE;
    last_scroll_y_ = 0.0f;
    accumulated_scroll_ = 0.0f;
    has_previous_landmarks_ = false;
}

inline void GestureStateMachine::set_thresholds(const GestureThresholds& thresholds) {
    thresholds_ = thresholds;
}

inline bool GestureStateMachine::is_click_pending() const {
    return (pending_state_.type == GestureType::LEFT_CLICK ||
            pending_state_.type == GestureType::RIGHT_CLICK) &&
           !pending_state_.is_confirmed;
}

inline bool GestureStateMachine::is_tracking_lost() const {
    return tracking_lost_;
}

inline Point3D GestureStateMachine::get_cursor_point() const {
    return raw_classification_.cursor_point;
}

inline float GestureStateMachine::get_scroll_delta() const {
    return raw_classification_.scroll_delta;
}

inline GestureClassification GestureStateMachine::classify_gesture(const HandLandmarks& landmarks) {
    GestureClassification result;
    result.cursor_point = landmarks.get(LandmarkIndex::INDEX_TIP);
    
    float confidence = 0.0f;
    
    // Priority order for gesture detection:
    // 1. Pinch gestures (clicks)
    // 2. Scroll gesture
    // 3. Fist (drag)
    // 4. Pointing
    // 5. Open palm (neutral)
    
    // Check for left click (thumb + index pinch)
    if (detect_pinch(landmarks, LandmarkIndex::INDEX_TIP, confidence)) {
        result.type = GestureType::LEFT_CLICK;
        result.confidence = confidence;
        return result;
    }
    
    // Check for right click (thumb + middle pinch)
    if (detect_pinch(landmarks, LandmarkIndex::MIDDLE_TIP, confidence)) {
        result.type = GestureType::RIGHT_CLICK;
        result.confidence = confidence;
        return result;
    }
    
    // Check for scroll (index + middle extended, vertical movement)
    float scroll_delta = 0.0f;
    if (detect_scroll(landmarks, confidence, scroll_delta)) {
        result.type = GestureType::SCROLL;
        result.confidence = confidence;
        result.scroll_delta = scroll_delta;
        // Use middle point between index and middle for cursor
        const auto& index_tip = landmarks.get(LandmarkIndex::INDEX_TIP);
        const auto& middle_tip = landmarks.get(LandmarkIndex::MIDDLE_TIP);
        result.cursor_point = Point3D{
            (index_tip.x + middle_tip.x) / 2.0f,
            (index_tip.y + middle_tip.y) / 2.0f,
            (index_tip.z + middle_tip.z) / 2.0f
        };
        return result;
    }
    
    // Check for fist (drag)
    if (detect_fist(landmarks, confidence)) {
        result.type = GestureType::DRAG;
        result.confidence = confidence;
        // Use wrist for more stable drag tracking
        result.cursor_point = landmarks.get(LandmarkIndex::WRIST);
        return result;
    }
    
    // Check for pointing (index extended, others curled)
    if (detect_pointing(landmarks, confidence)) {
        result.type = GestureType::POINTING;
        result.confidence = confidence;
        return result;
    }
    
    // Check for open palm (neutral)
    if (detect_open_palm(landmarks, confidence)) {
        result.type = GestureType::NEUTRAL;
        result.confidence = confidence;
        return result;
    }
    
    // Default to neutral with low confidence
    result.type = GestureType::NEUTRAL;
    result.confidence = 0.5f;
    return result;
}

inline bool GestureStateMachine::detect_pinch(const HandLandmarks& landmarks,
                                               LandmarkIndex finger_tip,
                                               float& confidence) {
    float distance = calculate_pinch_distance(landmarks, LandmarkIndex::THUMB_TIP, finger_tip);
    
    // Use hysteresis based on current state
    float threshold = thresholds_.pinch_threshold;
    if (current_state_.type == GestureType::LEFT_CLICK || 
        current_state_.type == GestureType::RIGHT_CLICK) {
        threshold = thresholds_.pinch_release_threshold;
    }
    
    if (distance < threshold) {
        // Calculate confidence based on how close the pinch is
        confidence = 1.0f - (distance / threshold);
        confidence = std::min(1.0f, confidence * 1.5f); // Boost confidence
        return true;
    }
    
    return false;
}

inline bool GestureStateMachine::detect_pointing(const HandLandmarks& landmarks, float& confidence) {
    // Index finger must be extended
    bool index_extended = is_finger_extended(landmarks,
        LandmarkIndex::INDEX_MCP, LandmarkIndex::INDEX_PIP, LandmarkIndex::INDEX_TIP);
    
    if (!index_extended) return false;
    
    // Other fingers should be curled
    bool middle_curled = is_finger_curled(landmarks,
        LandmarkIndex::MIDDLE_MCP, LandmarkIndex::MIDDLE_PIP, LandmarkIndex::MIDDLE_TIP);
    bool ring_curled = is_finger_curled(landmarks,
        LandmarkIndex::RING_MCP, LandmarkIndex::RING_PIP, LandmarkIndex::RING_TIP);
    bool pinky_curled = is_finger_curled(landmarks,
        LandmarkIndex::PINKY_MCP, LandmarkIndex::PINKY_PIP, LandmarkIndex::PINKY_TIP);
    
    int curled_count = (middle_curled ? 1 : 0) + (ring_curled ? 1 : 0) + (pinky_curled ? 1 : 0);
    
    if (curled_count >= 2) {
        confidence = 0.6f + 0.13f * curled_count;
        return true;
    }
    
    return false;
}

inline bool GestureStateMachine::detect_fist(const HandLandmarks& landmarks, float& confidence) {
    // All fingers should be curled
    bool index_curled = is_finger_curled(landmarks,
        LandmarkIndex::INDEX_MCP, LandmarkIndex::INDEX_PIP, LandmarkIndex::INDEX_TIP);
    bool middle_curled = is_finger_curled(landmarks,
        LandmarkIndex::MIDDLE_MCP, LandmarkIndex::MIDDLE_PIP, LandmarkIndex::MIDDLE_TIP);
    bool ring_curled = is_finger_curled(landmarks,
        LandmarkIndex::RING_MCP, LandmarkIndex::RING_PIP, LandmarkIndex::RING_TIP);
    bool pinky_curled = is_finger_curled(landmarks,
        LandmarkIndex::PINKY_MCP, LandmarkIndex::PINKY_PIP, LandmarkIndex::PINKY_TIP);
    
    int curled_count = (index_curled ? 1 : 0) + (middle_curled ? 1 : 0) + 
                       (ring_curled ? 1 : 0) + (pinky_curled ? 1 : 0);
    
    if (curled_count >= 3) {
        confidence = 0.5f + 0.125f * curled_count;
        return true;
    }
    
    return false;
}

inline bool GestureStateMachine::detect_open_palm(const HandLandmarks& landmarks, float& confidence) {
    // All fingers should be extended
    bool index_ext = is_finger_extended(landmarks,
        LandmarkIndex::INDEX_MCP, LandmarkIndex::INDEX_PIP, LandmarkIndex::INDEX_TIP);
    bool middle_ext = is_finger_extended(landmarks,
        LandmarkIndex::MIDDLE_MCP, LandmarkIndex::MIDDLE_PIP, LandmarkIndex::MIDDLE_TIP);
    bool ring_ext = is_finger_extended(landmarks,
        LandmarkIndex::RING_MCP, LandmarkIndex::RING_PIP, LandmarkIndex::RING_TIP);
    bool pinky_ext = is_finger_extended(landmarks,
        LandmarkIndex::PINKY_MCP, LandmarkIndex::PINKY_PIP, LandmarkIndex::PINKY_TIP);
    
    int extended_count = (index_ext ? 1 : 0) + (middle_ext ? 1 : 0) + 
                         (ring_ext ? 1 : 0) + (pinky_ext ? 1 : 0);
    
    if (extended_count >= 3) {
        confidence = 0.5f + 0.125f * extended_count;
        return true;
    }
    
    return false;
}

inline bool GestureStateMachine::detect_scroll(const HandLandmarks& landmarks, 
                                                float& confidence, 
                                                float& delta) {
    // Index and middle fingers must be extended
    bool index_ext = is_finger_extended(landmarks,
        LandmarkIndex::INDEX_MCP, LandmarkIndex::INDEX_PIP, LandmarkIndex::INDEX_TIP);
    bool middle_ext = is_finger_extended(landmarks,
        LandmarkIndex::MIDDLE_MCP, LandmarkIndex::MIDDLE_PIP, LandmarkIndex::MIDDLE_TIP);
    
    if (!index_ext || !middle_ext) return false;
    
    // Ring and pinky should be curled
    bool ring_curled = is_finger_curled(landmarks,
        LandmarkIndex::RING_MCP, LandmarkIndex::RING_PIP, LandmarkIndex::RING_TIP);
    bool pinky_curled = is_finger_curled(landmarks,
        LandmarkIndex::PINKY_MCP, LandmarkIndex::PINKY_PIP, LandmarkIndex::PINKY_TIP);
    
    if (!ring_curled && !pinky_curled) return false;
    
    // Index and middle should be close together (parallel)
    const auto& index_tip = landmarks.get(LandmarkIndex::INDEX_TIP);
    const auto& middle_tip = landmarks.get(LandmarkIndex::MIDDLE_TIP);
    float finger_distance = distance_2d(index_tip, middle_tip);
    
    if (finger_distance > 0.1f) return false; // Fingers too far apart
    
    // Calculate vertical movement for scroll delta
    float current_y = (index_tip.y + middle_tip.y) / 2.0f;
    
    if (has_previous_landmarks_ && current_state_.type == GestureType::SCROLL) {
        delta = (last_scroll_y_ - current_y) * config::SCROLL_SENSITIVITY;
    } else {
        delta = 0.0f;
    }
    
    last_scroll_y_ = current_y;
    confidence = 0.8f;
    return true;
}

inline bool GestureStateMachine::is_finger_extended(const HandLandmarks& landmarks,
                                                     LandmarkIndex mcp,
                                                     LandmarkIndex pip,
                                                     LandmarkIndex tip) {
    const auto& mcp_pt = landmarks.get(mcp);
    const auto& pip_pt = landmarks.get(pip);
    const auto& tip_pt = landmarks.get(tip);
    
    // Finger is extended if tip is farther from wrist than MCP
    const auto& wrist = landmarks.get(LandmarkIndex::WRIST);
    
    float mcp_to_wrist = distance_2d(mcp_pt, wrist);
    float tip_to_wrist = distance_2d(tip_pt, wrist);
    
    // Also check that tip is farther from palm than PIP
    float pip_to_mcp = distance_2d(pip_pt, mcp_pt);
    float tip_to_pip = distance_2d(tip_pt, pip_pt);
    
    return tip_to_wrist > mcp_to_wrist && tip_to_pip > pip_to_mcp * 0.5f;
}

inline bool GestureStateMachine::is_finger_curled(const HandLandmarks& landmarks,
                                                   LandmarkIndex mcp,
                                                   LandmarkIndex pip,
                                                   LandmarkIndex tip) {
    const auto& mcp_pt = landmarks.get(mcp);
    const auto& pip_pt = landmarks.get(pip);
    const auto& tip_pt = landmarks.get(tip);
    const auto& wrist = landmarks.get(LandmarkIndex::WRIST);
    
    // Finger is curled if tip is closer to wrist than PIP
    float tip_to_wrist = distance_2d(tip_pt, wrist);
    float pip_to_wrist = distance_2d(pip_pt, wrist);
    
    // Or if tip is close to MCP (finger folded back)
    float tip_to_mcp = distance_2d(tip_pt, mcp_pt);
    float pip_to_mcp = distance_2d(pip_pt, mcp_pt);
    
    return tip_to_wrist < pip_to_wrist || tip_to_mcp < pip_to_mcp;
}

inline float GestureStateMachine::calculate_pinch_distance(const HandLandmarks& landmarks,
                                                            LandmarkIndex tip1,
                                                            LandmarkIndex tip2) {
    return distance_2d(landmarks.get(tip1), landmarks.get(tip2));
}

inline bool GestureStateMachine::should_transition(const GestureClassification& classification) {
    // Don't transition if confidence is too low
    if (classification.confidence < thresholds_.min_gesture_confidence) {
        return false;
    }
    
    // Always allow transition to PAUSE
    if (classification.type == GestureType::PAUSE) {
        return true;
    }
    
    // Check if this is a new gesture type
    if (classification.type != pending_state_.type) {
        return true;
    }
    
    return false;
}

inline void GestureStateMachine::update_state(const GestureClassification& classification,
                                               int64_t timestamp_ms) {
    // Check if gesture type changed
    if (classification.type != pending_state_.type) {
        // Start tracking new gesture
        pending_state_.type = classification.type;
        pending_state_.confidence = classification.confidence;
        pending_state_.start_time_ms = timestamp_ms;
        pending_state_.last_update_ms = timestamp_ms;
        pending_state_.consecutive_frames = 1;
        pending_state_.is_confirmed = false;
    } else {
        // Same gesture, update tracking
        pending_state_.confidence = classification.confidence;
        pending_state_.last_update_ms = timestamp_ms;
        pending_state_.consecutive_frames++;
    }
    
    // Check if gesture should be confirmed
    int64_t elapsed = timestamp_ms - pending_state_.start_time_ms;
    int64_t required_dwell = thresholds_.dwell_time_click_ms;
    
    if (pending_state_.type == GestureType::DRAG) {
        required_dwell = thresholds_.dwell_time_drag_ms;
    }
    
    bool meets_time = elapsed >= required_dwell;
    bool meets_frames = pending_state_.consecutive_frames >= config::MIN_CONSECUTIVE_FRAMES;
    bool meets_confidence = pending_state_.confidence >= thresholds_.min_gesture_confidence;
    
    if (meets_time && meets_frames && meets_confidence) {
        // Check click debouncing
        if (pending_state_.type == GestureType::LEFT_CLICK ||
            pending_state_.type == GestureType::RIGHT_CLICK) {
            int64_t since_last_click = timestamp_ms - last_click_time_ms_;
            if (since_last_click < thresholds_.debounce_time_ms &&
                last_click_type_ == pending_state_.type) {
                // Too soon after last click of same type
                return;
            }
        }
        
        // Confirm the gesture
        pending_state_.is_confirmed = true;
        current_state_ = pending_state_;
        
        // Track click timing
        if (current_state_.type == GestureType::LEFT_CLICK ||
            current_state_.type == GestureType::RIGHT_CLICK) {
            last_click_time_ms_ = timestamp_ms;
            last_click_type_ = current_state_.type;
        }
    }
}

} // namespace gesture_mouse
