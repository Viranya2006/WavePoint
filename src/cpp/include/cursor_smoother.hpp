#pragma once
/**
 * WavePoint - Cursor Smoother
 * 
 * Implements exponential smoothing, jitter filtering, and acceleration
 * for smooth cursor movement from noisy hand tracking data.
 */

#include "gesture_types.hpp"
#include "config.hpp"
#include <deque>
#include <cmath>

namespace gesture_mouse {

/**
 * Cursor smoother with multiple filtering stages:
 * 1. Jitter filter - ignores tiny movements
 * 2. History averaging - reduces noise
 * 3. Exponential smoothing - smooth transitions
 * 4. Acceleration - faster movement for large gestures
 */
class CursorSmoother {
public:
    CursorSmoother();
    explicit CursorSmoother(const SmoothingConfig& config);
    
    /**
     * Process a raw cursor position and return smoothed position.
     * 
     * @param raw_position Raw position from coordinate mapper
     * @param timestamp_ms Current timestamp
     * @return Smoothed screen position
     */
    ScreenPoint smooth(const Point2D& raw_position, int64_t timestamp_ms);
    
    /**
     * Reset the smoother state (e.g., when tracking is lost).
     */
    void reset();
    
    /**
     * Update configuration.
     */
    void set_config(const SmoothingConfig& config);
    
    /**
     * Get current smoothed position without new input.
     */
    ScreenPoint get_current_position() const;
    
    /**
     * Get current velocity (pixels per second).
     */
    Point2D get_velocity() const;
    
    /**
     * Check if cursor is currently moving.
     */
    bool is_moving() const;

private:
    SmoothingConfig config_;
    
    // Current state
    Point2D smoothed_position_;
    Point2D velocity_;
    int64_t last_timestamp_ms_;
    bool initialized_;
    
    // History for averaging
    std::deque<Point2D> position_history_;
    
    // Apply jitter filter
    Point2D apply_jitter_filter(const Point2D& current, const Point2D& previous);
    
    // Apply exponential smoothing
    Point2D apply_exponential_smoothing(const Point2D& current, const Point2D& smoothed);
    
    // Apply acceleration curve
    Point2D apply_acceleration(const Point2D& delta, float dt);
    
    // Calculate history average
    Point2D calculate_history_average();
};

// ============================================================================
// IMPLEMENTATION
// ============================================================================

inline CursorSmoother::CursorSmoother()
    : config_{}
    , smoothed_position_{0.0f, 0.0f}
    , velocity_{0.0f, 0.0f}
    , last_timestamp_ms_{0}
    , initialized_{false}
{
    config_.alpha = config::DEFAULT_SMOOTHING_ALPHA;
    config_.velocity_scale = config::DEFAULT_VELOCITY_SCALE;
    config_.history_size = config::DEFAULT_HISTORY_SIZE;
    config_.jitter_threshold = config::DEFAULT_JITTER_THRESHOLD;
    config_.acceleration_factor = config::DEFAULT_ACCELERATION;
}

inline CursorSmoother::CursorSmoother(const SmoothingConfig& config)
    : config_(config)
    , smoothed_position_{0.0f, 0.0f}
    , velocity_{0.0f, 0.0f}
    , last_timestamp_ms_{0}
    , initialized_{false}
{}

inline ScreenPoint CursorSmoother::smooth(const Point2D& raw_position, int64_t timestamp_ms) {
    // First frame initialization
    if (!initialized_) {
        smoothed_position_ = raw_position;
        last_timestamp_ms_ = timestamp_ms;
        initialized_ = true;
        position_history_.push_back(raw_position);
        return ScreenPoint(
            static_cast<int>(std::round(raw_position.x)),
            static_cast<int>(std::round(raw_position.y))
        );
    }
    
    // Calculate time delta
    float dt = static_cast<float>(timestamp_ms - last_timestamp_ms_) / 1000.0f;
    if (dt <= 0.0f) dt = 0.033f;  // Default to ~30 FPS
    last_timestamp_ms_ = timestamp_ms;
    
    // Add to history
    position_history_.push_back(raw_position);
    while (static_cast<int>(position_history_.size()) > config_.history_size) {
        position_history_.pop_front();
    }
    
    // Stage 1: History averaging
    Point2D averaged = calculate_history_average();
    
    // Stage 2: Jitter filter
    Point2D filtered = apply_jitter_filter(averaged, smoothed_position_);
    
    // Stage 3: Calculate delta and apply acceleration
    Point2D delta{
        filtered.x - smoothed_position_.x,
        filtered.y - smoothed_position_.y
    };
    Point2D accelerated_delta = apply_acceleration(delta, dt);
    
    // Stage 4: Exponential smoothing
    Point2D target{
        smoothed_position_.x + accelerated_delta.x,
        smoothed_position_.y + accelerated_delta.y
    };
    smoothed_position_ = apply_exponential_smoothing(target, smoothed_position_);
    
    // Update velocity
    velocity_.x = (smoothed_position_.x - position_history_.front().x) / dt;
    velocity_.y = (smoothed_position_.y - position_history_.front().y) / dt;
    
    // Convert to screen coordinates
    return ScreenPoint(
        static_cast<int>(std::round(smoothed_position_.x)),
        static_cast<int>(std::round(smoothed_position_.y))
    );
}

inline void CursorSmoother::reset() {
    smoothed_position_ = {0.0f, 0.0f};
    velocity_ = {0.0f, 0.0f};
    last_timestamp_ms_ = 0;
    initialized_ = false;
    position_history_.clear();
}

inline void CursorSmoother::set_config(const SmoothingConfig& config) {
    config_ = config;
}

inline ScreenPoint CursorSmoother::get_current_position() const {
    return ScreenPoint(
        static_cast<int>(std::round(smoothed_position_.x)),
        static_cast<int>(std::round(smoothed_position_.y))
    );
}

inline Point2D CursorSmoother::get_velocity() const {
    return velocity_;
}

inline bool CursorSmoother::is_moving() const {
    float speed = std::sqrt(velocity_.x * velocity_.x + velocity_.y * velocity_.y);
    return speed > config_.jitter_threshold;
}

inline Point2D CursorSmoother::apply_jitter_filter(const Point2D& current, const Point2D& previous) {
    float dx = current.x - previous.x;
    float dy = current.y - previous.y;
    float distance = std::sqrt(dx * dx + dy * dy);
    
    if (distance < config_.jitter_threshold) {
        // Movement too small, ignore it
        return previous;
    }
    
    return current;
}

inline Point2D CursorSmoother::apply_exponential_smoothing(const Point2D& current, const Point2D& smoothed) {
    float alpha = config_.alpha;
    return Point2D{
        alpha * current.x + (1.0f - alpha) * smoothed.x,
        alpha * current.y + (1.0f - alpha) * smoothed.y
    };
}

inline Point2D CursorSmoother::apply_acceleration(const Point2D& delta, float dt) {
    float distance = std::sqrt(delta.x * delta.x + delta.y * delta.y);
    
    if (distance < 1.0f) {
        return delta;
    }
    
    // Apply acceleration curve: larger movements get amplified
    // Using a simple power curve
    float base_speed = distance / dt;
    float acceleration = 1.0f;
    
    // Threshold-based acceleration
    if (base_speed > 100.0f) {
        acceleration = config_.acceleration_factor;
    } else if (base_speed > 50.0f) {
        // Linear interpolation between 1.0 and acceleration_factor
        float t = (base_speed - 50.0f) / 50.0f;
        acceleration = 1.0f + t * (config_.acceleration_factor - 1.0f);
    }
    
    // Apply velocity scale and acceleration
    float scale = config_.velocity_scale * acceleration;
    
    return Point2D{
        delta.x * scale,
        delta.y * scale
    };
}

inline Point2D CursorSmoother::calculate_history_average() {
    if (position_history_.empty()) {
        return smoothed_position_;
    }
    
    float sum_x = 0.0f;
    float sum_y = 0.0f;
    
    // Weighted average: more recent positions have higher weight
    float total_weight = 0.0f;
    float weight = 1.0f;
    float weight_increment = 1.0f / static_cast<float>(position_history_.size());
    
    for (const auto& pos : position_history_) {
        sum_x += pos.x * weight;
        sum_y += pos.y * weight;
        total_weight += weight;
        weight += weight_increment;
    }
    
    return Point2D{
        sum_x / total_weight,
        sum_y / total_weight
    };
}

} // namespace gesture_mouse
