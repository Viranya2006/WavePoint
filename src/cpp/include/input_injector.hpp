#pragma once
/**
 * WavePoint - Input Injector
 * 
 * Windows-specific mouse input injection using SendInput API.
 * Thread-safe and designed for low-latency operation.
 */

#include "gesture_types.hpp"
#include "config.hpp"

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <Windows.h>

#include <atomic>
#include <mutex>

namespace gesture_mouse {

/**
 * Injects mouse input into the Windows input stream.
 * 
 * Uses SendInput for reliable, low-latency input injection.
 * All methods are thread-safe.
 */
class InputInjector {
public:
    InputInjector();
    ~InputInjector();
    
    // Non-copyable
    InputInjector(const InputInjector&) = delete;
    InputInjector& operator=(const InputInjector&) = delete;
    
    /**
     * Enable or disable input injection.
     * When disabled, all injection calls are no-ops.
     */
    void set_enabled(bool enabled);
    bool is_enabled() const;
    
    /**
     * Move cursor to absolute screen position.
     * 
     * @param position Screen coordinates
     * @return true if injection succeeded
     */
    bool move_cursor(const ScreenPoint& position);
    
    /**
     * Move cursor relative to current position.
     * 
     * @param delta_x Horizontal movement in pixels
     * @param delta_y Vertical movement in pixels
     * @return true if injection succeeded
     */
    bool move_cursor_relative(int delta_x, int delta_y);
    
    /**
     * Perform left mouse button down.
     */
    bool left_down();
    
    /**
     * Perform left mouse button up.
     */
    bool left_up();
    
    /**
     * Perform complete left click (down + up).
     */
    bool left_click();
    
    /**
     * Perform right mouse button down.
     */
    bool right_down();
    
    /**
     * Perform right mouse button up.
     */
    bool right_up();
    
    /**
     * Perform complete right click (down + up).
     */
    bool right_click();
    
    /**
     * Perform mouse wheel scroll.
     * 
     * @param delta Scroll amount (positive = up, negative = down)
     *              One "click" is typically WHEEL_DELTA (120)
     */
    bool scroll(int delta);
    
    /**
     * Execute a complete mouse command.
     * 
     * @param command The command to execute
     * @return true if injection succeeded
     */
    bool execute(const MouseCommand& command);
    
    /**
     * Get current cursor position from OS.
     */
    ScreenPoint get_cursor_position() const;
    
    /**
     * Get statistics.
     */
    uint64_t get_injection_count() const;
    uint64_t get_failure_count() const;

private:
    std::atomic<bool> enabled_;
    std::atomic<uint64_t> injection_count_;
    std::atomic<uint64_t> failure_count_;
    
    // Mutex for compound operations (click = down + up)
    mutable std::mutex injection_mutex_;
    
    // Last known position for relative movement
    ScreenPoint last_position_;
    
    // Internal injection helpers
    bool inject_mouse_event(DWORD flags, int dx, int dy, DWORD data = 0);
    bool inject_absolute_move(int x, int y);
    
    // Convert screen coordinates to normalized absolute coordinates
    void screen_to_absolute(int screen_x, int screen_y, int& abs_x, int& abs_y) const;
};

// ============================================================================
// IMPLEMENTATION
// ============================================================================

inline InputInjector::InputInjector()
    : enabled_(false)
    , injection_count_(0)
    , failure_count_(0)
    , last_position_{0, 0}
{
    // Get initial cursor position
    POINT pt;
    if (GetCursorPos(&pt)) {
        last_position_.x = pt.x;
        last_position_.y = pt.y;
    }
}

inline InputInjector::~InputInjector() {
    // Ensure no buttons are stuck down
    if (enabled_) {
        left_up();
        right_up();
    }
}

inline void InputInjector::set_enabled(bool enabled) {
    // If disabling, release any held buttons
    if (enabled_ && !enabled) {
        left_up();
        right_up();
    }
    enabled_ = enabled;
}

inline bool InputInjector::is_enabled() const {
    return enabled_;
}

inline bool InputInjector::move_cursor(const ScreenPoint& position) {
    if (!enabled_) return false;
    
    bool result = inject_absolute_move(position.x, position.y);
    if (result) {
        last_position_ = position;
    }
    return result;
}

inline bool InputInjector::move_cursor_relative(int delta_x, int delta_y) {
    if (!enabled_) return false;
    
    return inject_mouse_event(MOUSEEVENTF_MOVE, delta_x, delta_y);
}

inline bool InputInjector::left_down() {
    if (!enabled_) return false;
    return inject_mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0);
}

inline bool InputInjector::left_up() {
    if (!enabled_) return false;
    return inject_mouse_event(MOUSEEVENTF_LEFTUP, 0, 0);
}

inline bool InputInjector::left_click() {
    if (!enabled_) return false;
    
    std::lock_guard<std::mutex> lock(injection_mutex_);
    bool down = inject_mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0);
    bool up = inject_mouse_event(MOUSEEVENTF_LEFTUP, 0, 0);
    return down && up;
}

inline bool InputInjector::right_down() {
    if (!enabled_) return false;
    return inject_mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0);
}

inline bool InputInjector::right_up() {
    if (!enabled_) return false;
    return inject_mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0);
}

inline bool InputInjector::right_click() {
    if (!enabled_) return false;
    
    std::lock_guard<std::mutex> lock(injection_mutex_);
    bool down = inject_mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0);
    bool up = inject_mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0);
    return down && up;
}

inline bool InputInjector::scroll(int delta) {
    if (!enabled_) return false;
    return inject_mouse_event(MOUSEEVENTF_WHEEL, 0, 0, static_cast<DWORD>(delta));
}

inline bool InputInjector::execute(const MouseCommand& command) {
    if (!enabled_ || !command.is_valid()) return false;
    
    switch (command.action) {
        case MouseAction::MOVE:
            return move_cursor(command.position);
            
        case MouseAction::LEFT_DOWN:
            return left_down();
            
        case MouseAction::LEFT_UP:
            return left_up();
            
        case MouseAction::LEFT_CLICK:
            return left_click();
            
        case MouseAction::RIGHT_DOWN:
            return right_down();
            
        case MouseAction::RIGHT_UP:
            return right_up();
            
        case MouseAction::RIGHT_CLICK:
            return right_click();
            
        case MouseAction::SCROLL_UP:
            return scroll(WHEEL_DELTA * config::SCROLL_LINES_PER_TICK);
            
        case MouseAction::SCROLL_DOWN:
            return scroll(-WHEEL_DELTA * config::SCROLL_LINES_PER_TICK);
            
        case MouseAction::DRAG_START:
            return left_down();
            
        case MouseAction::DRAG_END:
            return left_up();
            
        default:
            return false;
    }
}

inline ScreenPoint InputInjector::get_cursor_position() const {
    POINT pt;
    if (GetCursorPos(&pt)) {
        return ScreenPoint{pt.x, pt.y};
    }
    return last_position_;
}

inline uint64_t InputInjector::get_injection_count() const {
    return injection_count_;
}

inline uint64_t InputInjector::get_failure_count() const {
    return failure_count_;
}

inline bool InputInjector::inject_mouse_event(DWORD flags, int dx, int dy, DWORD data) {
    INPUT input = {};
    input.type = INPUT_MOUSE;
    input.mi.dx = dx;
    input.mi.dy = dy;
    input.mi.dwFlags = flags;
    input.mi.mouseData = data;
    input.mi.time = 0;
    input.mi.dwExtraInfo = 0;
    
    UINT result = SendInput(1, &input, sizeof(INPUT));
    
    if (result == 1) {
        injection_count_++;
        return true;
    } else {
        failure_count_++;
        return false;
    }
}

inline bool InputInjector::inject_absolute_move(int x, int y) {
    int abs_x, abs_y;
    screen_to_absolute(x, y, abs_x, abs_y);
    
    INPUT input = {};
    input.type = INPUT_MOUSE;
    input.mi.dx = abs_x;
    input.mi.dy = abs_y;
    input.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK;
    input.mi.mouseData = 0;
    input.mi.time = 0;
    input.mi.dwExtraInfo = 0;
    
    UINT result = SendInput(1, &input, sizeof(INPUT));
    
    if (result == 1) {
        injection_count_++;
        return true;
    } else {
        failure_count_++;
        return false;
    }
}

inline void InputInjector::screen_to_absolute(int screen_x, int screen_y, int& abs_x, int& abs_y) const {
    // Get virtual screen dimensions
    int virt_left = GetSystemMetrics(SM_XVIRTUALSCREEN);
    int virt_top = GetSystemMetrics(SM_YVIRTUALSCREEN);
    int virt_width = GetSystemMetrics(SM_CXVIRTUALSCREEN);
    int virt_height = GetSystemMetrics(SM_CYVIRTUALSCREEN);
    
    // Convert to normalized absolute coordinates (0-65535)
    // Account for virtual screen offset
    abs_x = static_cast<int>(
        (static_cast<float>(screen_x - virt_left) / virt_width) * 65535.0f
    );
    abs_y = static_cast<int>(
        (static_cast<float>(screen_y - virt_top) / virt_height) * 65535.0f
    );
    
    // Clamp to valid range
    abs_x = std::max(0, std::min(65535, abs_x));
    abs_y = std::max(0, std::min(65535, abs_y));
}

} // namespace gesture_mouse
