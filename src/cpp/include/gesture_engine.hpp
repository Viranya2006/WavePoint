#pragma once
/**
 * WavePoint - Gesture Engine
 * 
 * Main engine that coordinates all components:
 * - Receives landmarks from Python
 * - Processes through state machine
 * - Smooths cursor movement
 * - Injects mouse input
 * 
 * This is the primary interface exposed to Python via pybind11.
 */

#include "gesture_types.hpp"
#include "gesture_state_machine.hpp"
#include "cursor_smoother.hpp"
#include "coordinate_mapper.hpp"
#include "input_injector.hpp"
#include "performance_monitor.hpp"
#include "config.hpp"

#include <atomic>
#include <mutex>
#include <thread>
#include <functional>

namespace gesture_mouse {

/**
 * Callback types for Python integration.
 */
using StateChangeCallback = std::function<void(GestureType, float)>;
using ErrorCallback = std::function<void(const std::string&)>;

/**
 * Main gesture processing engine.
 * 
 * Thread-safe interface for:
 * - Receiving hand landmarks from Python
 * - Processing gestures
 * - Controlling mouse input
 */
class GestureEngine {
public:
    GestureEngine();
    ~GestureEngine();
    
    // Non-copyable
    GestureEngine(const GestureEngine&) = delete;
    GestureEngine& operator=(const GestureEngine&) = delete;
    
    // ========================================================================
    // LIFECYCLE
    // ========================================================================
    
    /**
     * Initialize the engine with configuration.
     */
    bool initialize(const EngineConfig& config);
    
    /**
     * Start the engine (enables processing but not input injection).
     */
    bool start();
    
    /**
     * Stop the engine.
     */
    void stop();
    
    /**
     * Check if engine is running.
     */
    bool is_running() const;
    
    /**
     * Enable/disable mouse input injection.
     * When disabled, gestures are still processed but no mouse events are sent.
     */
    void set_input_enabled(bool enabled);
    bool is_input_enabled() const;
    
    // ========================================================================
    // LANDMARK PROCESSING
    // ========================================================================
    
    /**
     * Process hand landmarks from MediaPipe.
     * This is the main entry point called from Python.
     * 
     * @param landmarks Array of 21 landmarks (x, y, z for each)
     * @param confidence Detection confidence [0, 1]
     * @param is_right_hand True if right hand
     * @param timestamp_ms Frame timestamp
     * @param frame_width Source frame width
     * @param frame_height Source frame height
     */
    void process_landmarks(
        const float* landmarks,  // 21 * 3 = 63 floats
        float confidence,
        bool is_right_hand,
        int64_t timestamp_ms,
        int frame_width,
        int frame_height
    );
    
    /**
     * Notify engine that no hand was detected in current frame.
     */
    void process_no_detection();
    
    // ========================================================================
    // STATE QUERIES
    // ========================================================================
    
    /**
     * Get current gesture type.
     */
    GestureType get_current_gesture() const;
    
    /**
     * Get current gesture confidence.
     */
    float get_current_confidence() const;
    
    /**
     * Get current gesture as string.
     */
    const char* get_current_gesture_name() const;
    
    /**
     * Check if tracking is active.
     */
    bool is_tracking() const;
    
    /**
     * Get current cursor position (screen coordinates).
     */
    ScreenPoint get_cursor_position() const;
    
    // ========================================================================
    // CONFIGURATION
    // ========================================================================
    
    /**
     * Update engine configuration.
     */
    void set_config(const EngineConfig& config);
    
    /**
     * Get current configuration.
     */
    EngineConfig get_config() const;
    
    /**
     * Update calibration data.
     */
    void set_calibration(const CalibrationData& calibration);
    
    /**
     * Update smoothing configuration.
     */
    void set_smoothing(const SmoothingConfig& smoothing);
    
    /**
     * Update gesture thresholds.
     */
    void set_thresholds(const GestureThresholds& thresholds);
    
    /**
     * Set which hand to track.
     */
    void set_hand_preference(bool right_hand);
    
    // ========================================================================
    // PERFORMANCE
    // ========================================================================
    
    /**
     * Get current FPS.
     */
    float get_fps() const;
    
    /**
     * Get performance metrics.
     */
    PerformanceMetrics get_performance_metrics() const;
    
    /**
     * Reset performance counters.
     */
    void reset_performance_counters();
    
    // ========================================================================
    // CALLBACKS
    // ========================================================================
    
    /**
     * Set callback for gesture state changes.
     */
    void set_state_change_callback(StateChangeCallback callback);
    
    /**
     * Set callback for errors.
     */
    void set_error_callback(ErrorCallback callback);

private:
    // Configuration
    EngineConfig config_;
    mutable std::mutex config_mutex_;
    
    // Components
    GestureStateMachine state_machine_;
    CursorSmoother smoother_;
    CoordinateMapper mapper_;
    InputInjector injector_;
    PerformanceMonitor monitor_;
    
    // State
    std::atomic<bool> running_{false};
    std::atomic<bool> input_enabled_{false};
    GestureState current_state_;
    mutable std::mutex state_mutex_;
    
    // Previous state for change detection
    GestureType previous_gesture_{GestureType::NONE};
    
    // Drag state
    bool is_dragging_{false};
    
    // Callbacks
    StateChangeCallback state_change_callback_;
    ErrorCallback error_callback_;
    std::mutex callback_mutex_;
    
    // Internal processing
    void process_gesture_state(const GestureState& state, const Point3D& cursor_point);
    void handle_click(GestureType type);
    void handle_scroll(float delta);
    void handle_drag(bool start);
    void notify_state_change(GestureType type, float confidence);
    void notify_error(const std::string& message);
};

// ============================================================================
// IMPLEMENTATION
// ============================================================================

inline GestureEngine::GestureEngine() = default;

inline GestureEngine::~GestureEngine() {
    stop();
}

inline bool GestureEngine::initialize(const EngineConfig& config) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    config_ = config;
    
    // Initialize components
    mapper_.set_calibration(config.calibration);
    mapper_.refresh_screen_bounds();
    smoother_.set_config(config.smoothing);
    state_machine_.set_thresholds(config.thresholds);
    
    return true;
}

inline bool GestureEngine::start() {
    if (running_) return true;
    
    running_ = true;
    monitor_.reset();
    state_machine_.reset();
    smoother_.reset();
    
    return true;
}

inline void GestureEngine::stop() {
    if (!running_) return;
    
    running_ = false;
    
    // Ensure clean state - release any held buttons
    if (is_dragging_) {
        injector_.left_up();
        is_dragging_ = false;
    }
    
    injector_.set_enabled(false);
}

inline bool GestureEngine::is_running() const {
    return running_;
}

inline void GestureEngine::set_input_enabled(bool enabled) {
    input_enabled_ = enabled;
    injector_.set_enabled(enabled);
    
    if (!enabled && is_dragging_) {
        injector_.left_up();
        is_dragging_ = false;
    }
}

inline bool GestureEngine::is_input_enabled() const {
    return input_enabled_;
}

inline void GestureEngine::process_landmarks(
    const float* landmarks,
    float confidence,
    bool is_right_hand,
    int64_t timestamp_ms,
    int frame_width,
    int frame_height
) {
    if (!running_) return;
    
    monitor_.frame_start();
    
    // Check hand preference
    {
        std::lock_guard<std::mutex> lock(config_mutex_);
        if (is_right_hand != config_.is_right_hand) {
            // Wrong hand, treat as no detection
            process_no_detection();
            return;
        }
    }
    
    // Convert raw landmarks to HandLandmarks struct
    HandLandmarks hand;
    hand.confidence = confidence;
    hand.is_right_hand = is_right_hand;
    hand.timestamp_ms = timestamp_ms > 0 ? timestamp_ms : get_timestamp_ms();
    hand.frame_width = frame_width;
    hand.frame_height = frame_height;
    
    for (int i = 0; i < 21; i++) {
        hand.landmarks[i].x = landmarks[i * 3];
        hand.landmarks[i].y = landmarks[i * 3 + 1];
        hand.landmarks[i].z = landmarks[i * 3 + 2];
    }
    
    // Process through state machine
    auto start_gesture = std::chrono::steady_clock::now();
    GestureState state = state_machine_.process(hand);
    auto end_gesture = std::chrono::steady_clock::now();
    
    float gesture_ms = std::chrono::duration_cast<std::chrono::microseconds>(
        end_gesture - start_gesture
    ).count() / 1000.0f;
    monitor_.record_gesture_time(gesture_ms);
    
    // Get cursor point
    Point3D cursor_point = state_machine_.get_cursor_point();
    
    // Process the gesture state
    process_gesture_state(state, cursor_point);
    
    // Update current state
    {
        std::lock_guard<std::mutex> lock(state_mutex_);
        current_state_ = state;
    }
    
    // Notify if gesture changed
    if (state.type != previous_gesture_ && state.is_confirmed) {
        notify_state_change(state.type, state.confidence);
        previous_gesture_ = state.type;
    }
    
    monitor_.frame_end();
}

inline void GestureEngine::process_no_detection() {
    if (!running_) return;
    
    monitor_.frame_start();
    
    GestureState state = state_machine_.process_no_detection();
    
    {
        std::lock_guard<std::mutex> lock(state_mutex_);
        current_state_ = state;
    }
    
    // End drag if tracking lost
    if (is_dragging_ && state_machine_.is_tracking_lost()) {
        handle_drag(false);
    }
    
    if (state.type != previous_gesture_) {
        notify_state_change(state.type, state.confidence);
        previous_gesture_ = state.type;
    }
    
    monitor_.frame_end();
}

inline GestureType GestureEngine::get_current_gesture() const {
    std::lock_guard<std::mutex> lock(state_mutex_);
    return current_state_.type;
}

inline float GestureEngine::get_current_confidence() const {
    std::lock_guard<std::mutex> lock(state_mutex_);
    return current_state_.confidence;
}

inline const char* GestureEngine::get_current_gesture_name() const {
    return gesture_to_string(get_current_gesture());
}

inline bool GestureEngine::is_tracking() const {
    return !state_machine_.is_tracking_lost();
}

inline ScreenPoint GestureEngine::get_cursor_position() const {
    return smoother_.get_current_position();
}

inline void GestureEngine::set_config(const EngineConfig& config) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    config_ = config;
    
    mapper_.set_calibration(config.calibration);
    smoother_.set_config(config.smoothing);
    state_machine_.set_thresholds(config.thresholds);
}

inline EngineConfig GestureEngine::get_config() const {
    std::lock_guard<std::mutex> lock(config_mutex_);
    return config_;
}

inline void GestureEngine::set_calibration(const CalibrationData& calibration) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    config_.calibration = calibration;
    mapper_.set_calibration(calibration);
}

inline void GestureEngine::set_smoothing(const SmoothingConfig& smoothing) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    config_.smoothing = smoothing;
    smoother_.set_config(smoothing);
}

inline void GestureEngine::set_thresholds(const GestureThresholds& thresholds) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    config_.thresholds = thresholds;
    state_machine_.set_thresholds(thresholds);
}

inline void GestureEngine::set_hand_preference(bool right_hand) {
    std::lock_guard<std::mutex> lock(config_mutex_);
    config_.is_right_hand = right_hand;
}

inline float GestureEngine::get_fps() const {
    return monitor_.get_fps();
}

inline PerformanceMetrics GestureEngine::get_performance_metrics() const {
    return monitor_.get_metrics();
}

inline void GestureEngine::reset_performance_counters() {
    monitor_.reset();
}

inline void GestureEngine::set_state_change_callback(StateChangeCallback callback) {
    std::lock_guard<std::mutex> lock(callback_mutex_);
    state_change_callback_ = std::move(callback);
}

inline void GestureEngine::set_error_callback(ErrorCallback callback) {
    std::lock_guard<std::mutex> lock(callback_mutex_);
    error_callback_ = std::move(callback);
}

inline void GestureEngine::process_gesture_state(const GestureState& state, const Point3D& cursor_point) {
    if (!state.is_confirmed) return;
    
    // Map cursor position
    Point2D screen_pos = mapper_.map_to_screen(cursor_point, true);
    
    // Check dead zone
    if (mapper_.is_in_dead_zone(cursor_point)) {
        return;
    }
    
    // Smooth cursor position
    ScreenPoint smoothed = smoother_.smooth(screen_pos, state.last_update_ms);
    
    // Handle based on gesture type
    switch (state.type) {
        case GestureType::POINTING:
        case GestureType::NEUTRAL:
            // Just move cursor
            if (input_enabled_ && !is_dragging_) {
                auto start = std::chrono::steady_clock::now();
                injector_.move_cursor(smoothed);
                auto end = std::chrono::steady_clock::now();
                float ms = std::chrono::duration_cast<std::chrono::microseconds>(
                    end - start
                ).count() / 1000.0f;
                monitor_.record_injection_time(ms);
            }
            break;
            
        case GestureType::LEFT_CLICK:
            if (input_enabled_) {
                injector_.move_cursor(smoothed);
                handle_click(GestureType::LEFT_CLICK);
            }
            break;
            
        case GestureType::RIGHT_CLICK:
            if (input_enabled_) {
                injector_.move_cursor(smoothed);
                handle_click(GestureType::RIGHT_CLICK);
            }
            break;
            
        case GestureType::SCROLL:
            if (input_enabled_) {
                float delta = state_machine_.get_scroll_delta();
                handle_scroll(delta);
            }
            break;
            
        case GestureType::DRAG:
            if (input_enabled_) {
                if (!is_dragging_) {
                    handle_drag(true);
                }
                injector_.move_cursor(smoothed);
            }
            break;
            
        case GestureType::PAUSE:
        case GestureType::NONE:
            // End drag if active
            if (is_dragging_) {
                handle_drag(false);
            }
            break;
            
        default:
            break;
    }
}

inline void GestureEngine::handle_click(GestureType type) {
    auto start = std::chrono::steady_clock::now();
    
    if (type == GestureType::LEFT_CLICK) {
        injector_.left_click();
    } else if (type == GestureType::RIGHT_CLICK) {
        injector_.right_click();
    }
    
    auto end = std::chrono::steady_clock::now();
    float ms = std::chrono::duration_cast<std::chrono::microseconds>(
        end - start
    ).count() / 1000.0f;
    monitor_.record_injection_time(ms);
}

inline void GestureEngine::handle_scroll(float delta) {
    if (std::abs(delta) < 0.1f) return;
    
    int scroll_amount = static_cast<int>(delta * WHEEL_DELTA);
    injector_.scroll(scroll_amount);
}

inline void GestureEngine::handle_drag(bool start) {
    if (start && !is_dragging_) {
        injector_.left_down();
        is_dragging_ = true;
    } else if (!start && is_dragging_) {
        injector_.left_up();
        is_dragging_ = false;
    }
}

inline void GestureEngine::notify_state_change(GestureType type, float confidence) {
    std::lock_guard<std::mutex> lock(callback_mutex_);
    if (state_change_callback_) {
        state_change_callback_(type, confidence);
    }
}

inline void GestureEngine::notify_error(const std::string& message) {
    std::lock_guard<std::mutex> lock(callback_mutex_);
    if (error_callback_) {
        error_callback_(message);
    }
}

} // namespace gesture_mouse
