#pragma once
/**
 * WavePoint - Coordinate Mapper
 * 
 * Maps normalized camera coordinates to screen pixel coordinates.
 * Handles calibration, dead zones, and multi-monitor support.
 */

#include "gesture_types.hpp"
#include "config.hpp"
#include <algorithm>
#include <cmath>

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>

namespace gesture_mouse {

/**
 * Maps hand landmark positions from camera space to screen space.
 * 
 * Camera space: Normalized [0, 1] coordinates from MediaPipe
 * Screen space: Pixel coordinates on the display
 */
class CoordinateMapper {
public:
    CoordinateMapper();
    explicit CoordinateMapper(const CalibrationData& calibration);
    
    /**
     * Map a camera-space point to screen-space.
     * 
     * @param camera_point Normalized point from hand tracking [0, 1]
     * @param mirror If true, mirror the x-axis (for front-facing camera)
     * @return Screen pixel coordinates
     */
    Point2D map_to_screen(const Point3D& camera_point, bool mirror = true) const;
    
    /**
     * Check if a point is within the dead zone.
     */
    bool is_in_dead_zone(const Point3D& camera_point) const;
    
    /**
     * Update calibration data.
     */
    void set_calibration(const CalibrationData& calibration);
    
    /**
     * Get current calibration.
     */
    const CalibrationData& get_calibration() const;
    
    /**
     * Refresh screen dimensions (call when display changes).
     */
    void refresh_screen_bounds();
    
    /**
     * Get the virtual screen bounds (all monitors combined).
     */
    void get_virtual_screen_bounds(int& left, int& top, int& right, int& bottom) const;
    
    /**
     * Get primary monitor bounds.
     */
    void get_primary_monitor_bounds(int& width, int& height) const;
    
    /**
     * Clamp a screen point to valid screen bounds.
     */
    ScreenPoint clamp_to_screen(const Point2D& point) const;

private:
    CalibrationData calibration_;
    
    // Cached screen dimensions
    int virtual_left_;
    int virtual_top_;
    int virtual_right_;
    int virtual_bottom_;
    int primary_width_;
    int primary_height_;
    
    // Calculate dead zone center
    Point2D get_dead_zone_center() const;
};

// ============================================================================
// IMPLEMENTATION
// ============================================================================

inline CoordinateMapper::CoordinateMapper()
    : virtual_left_(0)
    , virtual_top_(0)
    , virtual_right_(1920)
    , virtual_bottom_(1080)
    , primary_width_(1920)
    , primary_height_(1080)
{
    refresh_screen_bounds();
    
    // Set default calibration to use full screen
    calibration_.screen_left = virtual_left_;
    calibration_.screen_top = virtual_top_;
    calibration_.screen_right = virtual_right_;
    calibration_.screen_bottom = virtual_bottom_;
}

inline CoordinateMapper::CoordinateMapper(const CalibrationData& calibration)
    : calibration_(calibration)
    , virtual_left_(0)
    , virtual_top_(0)
    , virtual_right_(1920)
    , virtual_bottom_(1080)
    , primary_width_(1920)
    , primary_height_(1080)
{
    refresh_screen_bounds();
}

inline Point2D CoordinateMapper::map_to_screen(const Point3D& camera_point, bool mirror) const {
    // Get camera coordinates
    float cam_x = camera_point.x;
    float cam_y = camera_point.y;
    
    // Mirror x-axis for front-facing camera (hand appears mirrored)
    if (mirror) {
        cam_x = 1.0f - cam_x;
    }
    
    // Normalize to calibration bounds
    float norm_x = (cam_x - calibration_.cam_left) / 
                   (calibration_.cam_right - calibration_.cam_left);
    float norm_y = (cam_y - calibration_.cam_top) / 
                   (calibration_.cam_bottom - calibration_.cam_top);
    
    // Clamp to [0, 1]
    norm_x = std::clamp(norm_x, 0.0f, 1.0f);
    norm_y = std::clamp(norm_y, 0.0f, 1.0f);
    
    // Map to screen space
    float screen_x = calibration_.screen_left + 
                     norm_x * (calibration_.screen_right - calibration_.screen_left);
    float screen_y = calibration_.screen_top + 
                     norm_y * (calibration_.screen_bottom - calibration_.screen_top);
    
    return Point2D{screen_x, screen_y};
}

inline bool CoordinateMapper::is_in_dead_zone(const Point3D& camera_point) const {
    if (calibration_.dead_zone_radius <= 0.0f) {
        return false;
    }
    
    Point2D center = get_dead_zone_center();
    float dx = camera_point.x - center.x;
    float dy = camera_point.y - center.y;
    float distance = std::sqrt(dx * dx + dy * dy);
    
    return distance < calibration_.dead_zone_radius;
}

inline void CoordinateMapper::set_calibration(const CalibrationData& calibration) {
    calibration_ = calibration;
}

inline const CalibrationData& CoordinateMapper::get_calibration() const {
    return calibration_;
}

inline void CoordinateMapper::refresh_screen_bounds() {
    // Get virtual screen bounds (all monitors)
    virtual_left_ = GetSystemMetrics(SM_XVIRTUALSCREEN);
    virtual_top_ = GetSystemMetrics(SM_YVIRTUALSCREEN);
    virtual_right_ = virtual_left_ + GetSystemMetrics(SM_CXVIRTUALSCREEN);
    virtual_bottom_ = virtual_top_ + GetSystemMetrics(SM_CYVIRTUALSCREEN);
    
    // Get primary monitor dimensions
    primary_width_ = GetSystemMetrics(SM_CXSCREEN);
    primary_height_ = GetSystemMetrics(SM_CYSCREEN);
    
    // Update calibration screen bounds if using defaults
    if (calibration_.screen_right == 1920 && calibration_.screen_bottom == 1080) {
        calibration_.screen_left = virtual_left_;
        calibration_.screen_top = virtual_top_;
        calibration_.screen_right = virtual_right_;
        calibration_.screen_bottom = virtual_bottom_;
    }
}

inline void CoordinateMapper::get_virtual_screen_bounds(int& left, int& top, int& right, int& bottom) const {
    left = virtual_left_;
    top = virtual_top_;
    right = virtual_right_;
    bottom = virtual_bottom_;
}

inline void CoordinateMapper::get_primary_monitor_bounds(int& width, int& height) const {
    width = primary_width_;
    height = primary_height_;
}

inline ScreenPoint CoordinateMapper::clamp_to_screen(const Point2D& point) const {
    int x = static_cast<int>(std::round(point.x));
    int y = static_cast<int>(std::round(point.y));
    
    x = std::clamp(x, virtual_left_, virtual_right_ - 1);
    y = std::clamp(y, virtual_top_, virtual_bottom_ - 1);
    
    return ScreenPoint{x, y};
}

inline Point2D CoordinateMapper::get_dead_zone_center() const {
    // Dead zone is at the center of the camera space
    return Point2D{
        (calibration_.cam_left + calibration_.cam_right) / 2.0f,
        (calibration_.cam_top + calibration_.cam_bottom) / 2.0f
    };
}

} // namespace gesture_mouse
