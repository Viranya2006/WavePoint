#pragma once
/**
 * WavePoint - Performance Monitor
 * 
 * Real-time performance monitoring for FPS, latency, and resource usage.
 * Thread-safe and lock-free where possible.
 */

#include "gesture_types.hpp"
#include "config.hpp"
#include <atomic>
#include <chrono>
#include <deque>
#include <mutex>
#include <numeric>

namespace gesture_mouse {

/**
 * Monitors and reports performance metrics.
 * 
 * Tracks:
 * - Frame rate (FPS)
 * - Frame processing time
 * - Individual stage latencies
 * - Dropped frames
 */
class PerformanceMonitor {
public:
    PerformanceMonitor();
    
    /**
     * Mark the start of a new frame.
     */
    void frame_start();
    
    /**
     * Mark the end of the current frame.
     */
    void frame_end();
    
    /**
     * Record inference time for current frame.
     */
    void record_inference_time(float ms);
    
    /**
     * Record gesture processing time.
     */
    void record_gesture_time(float ms);
    
    /**
     * Record input injection time.
     */
    void record_injection_time(float ms);
    
    /**
     * Record a dropped frame.
     */
    void record_dropped_frame();
    
    /**
     * Get current FPS (averaged over recent frames).
     */
    float get_fps() const;
    
    /**
     * Get average frame time in milliseconds.
     */
    float get_frame_time_ms() const;
    
    /**
     * Get average inference time.
     */
    float get_inference_time_ms() const;
    
    /**
     * Get average gesture processing time.
     */
    float get_gesture_time_ms() const;
    
    /**
     * Get average injection time.
     */
    float get_injection_time_ms() const;
    
    /**
     * Get total frame count.
     */
    int get_total_frames() const;
    
    /**
     * Get dropped frame count.
     */
    int get_dropped_frames() const;
    
    /**
     * Get drop rate as percentage.
     */
    float get_drop_rate() const;
    
    /**
     * Get complete metrics snapshot.
     */
    PerformanceMetrics get_metrics() const;
    
    /**
     * Reset all counters.
     */
    void reset();
    
    /**
     * Check if performance is acceptable.
     * Returns false if FPS is too low or drop rate is too high.
     */
    bool is_performance_acceptable(float min_fps = 20.0f, float max_drop_rate = 0.1f) const;

private:
    using Clock = std::chrono::steady_clock;
    using TimePoint = Clock::time_point;
    
    // Frame timing
    TimePoint frame_start_time_;
    std::atomic<int> total_frames_{0};
    std::atomic<int> dropped_frames_{0};
    
    // Rolling averages (protected by mutex)
    mutable std::mutex metrics_mutex_;
    std::deque<float> frame_times_;
    std::deque<float> inference_times_;
    std::deque<float> gesture_times_;
    std::deque<float> injection_times_;
    
    static constexpr size_t HISTORY_SIZE = 60;  // ~2 seconds at 30 FPS
    
    // Helper to calculate average
    float calculate_average(const std::deque<float>& values) const;
    
    // Helper to add value to rolling buffer
    void add_to_buffer(std::deque<float>& buffer, float value);
};

// ============================================================================
// IMPLEMENTATION
// ============================================================================

inline PerformanceMonitor::PerformanceMonitor()
    : frame_start_time_(Clock::now())
{}

inline void PerformanceMonitor::frame_start() {
    frame_start_time_ = Clock::now();
}

inline void PerformanceMonitor::frame_end() {
    auto now = Clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(
        now - frame_start_time_
    );
    float frame_time_ms = duration.count() / 1000.0f;
    
    {
        std::lock_guard<std::mutex> lock(metrics_mutex_);
        add_to_buffer(frame_times_, frame_time_ms);
    }
    
    total_frames_++;
}

inline void PerformanceMonitor::record_inference_time(float ms) {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    add_to_buffer(inference_times_, ms);
}

inline void PerformanceMonitor::record_gesture_time(float ms) {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    add_to_buffer(gesture_times_, ms);
}

inline void PerformanceMonitor::record_injection_time(float ms) {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    add_to_buffer(injection_times_, ms);
}

inline void PerformanceMonitor::record_dropped_frame() {
    dropped_frames_++;
}

inline float PerformanceMonitor::get_fps() const {
    float frame_time = get_frame_time_ms();
    if (frame_time <= 0.0f) return 0.0f;
    return 1000.0f / frame_time;
}

inline float PerformanceMonitor::get_frame_time_ms() const {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    return calculate_average(frame_times_);
}

inline float PerformanceMonitor::get_inference_time_ms() const {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    return calculate_average(inference_times_);
}

inline float PerformanceMonitor::get_gesture_time_ms() const {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    return calculate_average(gesture_times_);
}

inline float PerformanceMonitor::get_injection_time_ms() const {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    return calculate_average(injection_times_);
}

inline int PerformanceMonitor::get_total_frames() const {
    return total_frames_;
}

inline int PerformanceMonitor::get_dropped_frames() const {
    return dropped_frames_;
}

inline float PerformanceMonitor::get_drop_rate() const {
    int total = total_frames_.load();
    if (total == 0) return 0.0f;
    return static_cast<float>(dropped_frames_.load()) / total;
}

inline PerformanceMetrics PerformanceMonitor::get_metrics() const {
    PerformanceMetrics metrics;
    metrics.fps = get_fps();
    metrics.frame_time_ms = get_frame_time_ms();
    metrics.inference_time_ms = get_inference_time_ms();
    metrics.gesture_time_ms = get_gesture_time_ms();
    metrics.injection_time_ms = get_injection_time_ms();
    metrics.dropped_frames = dropped_frames_.load();
    metrics.total_frames = total_frames_.load();
    return metrics;
}

inline void PerformanceMonitor::reset() {
    std::lock_guard<std::mutex> lock(metrics_mutex_);
    frame_times_.clear();
    inference_times_.clear();
    gesture_times_.clear();
    injection_times_.clear();
    total_frames_ = 0;
    dropped_frames_ = 0;
}

inline bool PerformanceMonitor::is_performance_acceptable(float min_fps, float max_drop_rate) const {
    return get_fps() >= min_fps && get_drop_rate() <= max_drop_rate;
}

inline float PerformanceMonitor::calculate_average(const std::deque<float>& values) const {
    if (values.empty()) return 0.0f;
    float sum = std::accumulate(values.begin(), values.end(), 0.0f);
    return sum / values.size();
}

inline void PerformanceMonitor::add_to_buffer(std::deque<float>& buffer, float value) {
    buffer.push_back(value);
    while (buffer.size() > HISTORY_SIZE) {
        buffer.pop_front();
    }
}

/**
 * RAII timer for automatic timing of code blocks.
 */
class ScopedTimer {
public:
    using Callback = std::function<void(float)>;
    
    explicit ScopedTimer(Callback callback)
        : callback_(std::move(callback))
        , start_(std::chrono::steady_clock::now())
    {}
    
    ~ScopedTimer() {
        auto end = std::chrono::steady_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end - start_);
        float ms = duration.count() / 1000.0f;
        if (callback_) {
            callback_(ms);
        }
    }
    
    // Non-copyable
    ScopedTimer(const ScopedTimer&) = delete;
    ScopedTimer& operator=(const ScopedTimer&) = delete;

private:
    Callback callback_;
    std::chrono::steady_clock::time_point start_;
};

} // namespace gesture_mouse
