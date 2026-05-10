/**
 * WavePoint - Python Bindings
 * 
 * pybind11 bindings to expose the C++ gesture engine to Python.
 * This is the bridge between the Python UI/tracking and C++ core.
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>
#include <pybind11/numpy.h>

#include "../include/gesture_engine.hpp"
#include "../include/gesture_types.hpp"
#include "../include/config.hpp"

namespace py = pybind11;
using namespace gesture_mouse;

PYBIND11_MODULE(gesture_mouse_core, m) {
    m.doc() = "WavePoint C++ Core - High-performance gesture processing engine";
    
    // ========================================================================
    // ENUMS
    // ========================================================================
    
    py::enum_<GestureType>(m, "GestureType", "Recognized gesture types")
        .value("NONE", GestureType::NONE, "No hand detected")
        .value("NEUTRAL", GestureType::NEUTRAL, "Open palm - neutral state")
        .value("POINTING", GestureType::POINTING, "Index finger pointing - cursor movement")
        .value("LEFT_CLICK", GestureType::LEFT_CLICK, "Thumb + index pinch")
        .value("RIGHT_CLICK", GestureType::RIGHT_CLICK, "Thumb + middle pinch")
        .value("SCROLL", GestureType::SCROLL, "Two fingers vertical movement")
        .value("DRAG", GestureType::DRAG, "Closed fist - drag mode")
        .value("PAUSE", GestureType::PAUSE, "Tracking lost - paused")
        .export_values();
    
    py::enum_<MouseAction>(m, "MouseAction", "Mouse action types")
        .value("NONE", MouseAction::NONE)
        .value("MOVE", MouseAction::MOVE)
        .value("LEFT_DOWN", MouseAction::LEFT_DOWN)
        .value("LEFT_UP", MouseAction::LEFT_UP)
        .value("LEFT_CLICK", MouseAction::LEFT_CLICK)
        .value("RIGHT_DOWN", MouseAction::RIGHT_DOWN)
        .value("RIGHT_UP", MouseAction::RIGHT_UP)
        .value("RIGHT_CLICK", MouseAction::RIGHT_CLICK)
        .value("SCROLL_UP", MouseAction::SCROLL_UP)
        .value("SCROLL_DOWN", MouseAction::SCROLL_DOWN)
        .value("DRAG_START", MouseAction::DRAG_START)
        .value("DRAG_END", MouseAction::DRAG_END)
        .export_values();
    
    // ========================================================================
    // DATA STRUCTURES
    // ========================================================================
    
    py::class_<Point2D>(m, "Point2D", "2D point for screen coordinates")
        .def(py::init<>())
        .def(py::init<float, float>())
        .def_readwrite("x", &Point2D::x)
        .def_readwrite("y", &Point2D::y)
        .def("__repr__", [](const Point2D& p) {
            return "Point2D(" + std::to_string(p.x) + ", " + std::to_string(p.y) + ")";
        });
    
    py::class_<Point3D>(m, "Point3D", "3D point for hand landmarks")
        .def(py::init<>())
        .def(py::init<float, float, float>())
        .def_readwrite("x", &Point3D::x)
        .def_readwrite("y", &Point3D::y)
        .def_readwrite("z", &Point3D::z)
        .def("__repr__", [](const Point3D& p) {
            return "Point3D(" + std::to_string(p.x) + ", " + 
                   std::to_string(p.y) + ", " + std::to_string(p.z) + ")";
        });
    
    py::class_<ScreenPoint>(m, "ScreenPoint", "Integer screen coordinates")
        .def(py::init<>())
        .def(py::init<int, int>())
        .def_readwrite("x", &ScreenPoint::x)
        .def_readwrite("y", &ScreenPoint::y)
        .def("__repr__", [](const ScreenPoint& p) {
            return "ScreenPoint(" + std::to_string(p.x) + ", " + std::to_string(p.y) + ")";
        });
    
    py::class_<GestureState>(m, "GestureState", "Current gesture state with timing info")
        .def(py::init<>())
        .def_readwrite("type", &GestureState::type)
        .def_readwrite("confidence", &GestureState::confidence)
        .def_readwrite("start_time_ms", &GestureState::start_time_ms)
        .def_readwrite("last_update_ms", &GestureState::last_update_ms)
        .def_readwrite("consecutive_frames", &GestureState::consecutive_frames)
        .def_readwrite("is_confirmed", &GestureState::is_confirmed)
        .def("reset", &GestureState::reset);
    
    py::class_<PerformanceMetrics>(m, "PerformanceMetrics", "Performance monitoring data")
        .def(py::init<>())
        .def_property("fps", 
            [](const PerformanceMetrics& m) { return m.fps.load(); },
            [](PerformanceMetrics& m, float v) { m.fps = v; })
        .def_property("frame_time_ms",
            [](const PerformanceMetrics& m) { return m.frame_time_ms.load(); },
            [](PerformanceMetrics& m, float v) { m.frame_time_ms = v; })
        .def_property("inference_time_ms",
            [](const PerformanceMetrics& m) { return m.inference_time_ms.load(); },
            [](PerformanceMetrics& m, float v) { m.inference_time_ms = v; })
        .def_property("gesture_time_ms",
            [](const PerformanceMetrics& m) { return m.gesture_time_ms.load(); },
            [](PerformanceMetrics& m, float v) { m.gesture_time_ms = v; })
        .def_property("injection_time_ms",
            [](const PerformanceMetrics& m) { return m.injection_time_ms.load(); },
            [](PerformanceMetrics& m, float v) { m.injection_time_ms = v; })
        .def_property("dropped_frames",
            [](const PerformanceMetrics& m) { return m.dropped_frames.load(); },
            [](PerformanceMetrics& m, int v) { m.dropped_frames = v; })
        .def_property("total_frames",
            [](const PerformanceMetrics& m) { return m.total_frames.load(); },
            [](PerformanceMetrics& m, int v) { m.total_frames = v; });
    
    // ========================================================================
    // CONFIGURATION STRUCTURES
    // ========================================================================
    
    py::class_<CalibrationData>(m, "CalibrationData", "Calibration settings for coordinate mapping")
        .def(py::init<>())
        .def_readwrite("cam_left", &CalibrationData::cam_left)
        .def_readwrite("cam_right", &CalibrationData::cam_right)
        .def_readwrite("cam_top", &CalibrationData::cam_top)
        .def_readwrite("cam_bottom", &CalibrationData::cam_bottom)
        .def_readwrite("screen_left", &CalibrationData::screen_left)
        .def_readwrite("screen_right", &CalibrationData::screen_right)
        .def_readwrite("screen_top", &CalibrationData::screen_top)
        .def_readwrite("screen_bottom", &CalibrationData::screen_bottom)
        .def_readwrite("dead_zone_radius", &CalibrationData::dead_zone_radius)
        .def("is_valid", &CalibrationData::is_valid);
    
    py::class_<SmoothingConfig>(m, "SmoothingConfig", "Cursor smoothing configuration")
        .def(py::init<>())
        .def_readwrite("alpha", &SmoothingConfig::alpha, "Exponential smoothing factor [0-1], lower = smoother")
        .def_readwrite("velocity_scale", &SmoothingConfig::velocity_scale, "Cursor speed multiplier")
        .def_readwrite("history_size", &SmoothingConfig::history_size, "Frames to average")
        .def_readwrite("jitter_threshold", &SmoothingConfig::jitter_threshold, "Pixels below which movement is ignored")
        .def_readwrite("acceleration_factor", &SmoothingConfig::acceleration_factor, "Acceleration for large movements");
    
    py::class_<GestureThresholds>(m, "GestureThresholds", "Gesture detection thresholds")
        .def(py::init<>())
        .def_readwrite("min_detection_confidence", &GestureThresholds::min_detection_confidence)
        .def_readwrite("min_tracking_confidence", &GestureThresholds::min_tracking_confidence)
        .def_readwrite("min_gesture_confidence", &GestureThresholds::min_gesture_confidence)
        .def_readwrite("dwell_time_click_ms", &GestureThresholds::dwell_time_click_ms)
        .def_readwrite("dwell_time_drag_ms", &GestureThresholds::dwell_time_drag_ms)
        .def_readwrite("debounce_time_ms", &GestureThresholds::debounce_time_ms)
        .def_readwrite("tracking_lost_timeout_ms", &GestureThresholds::tracking_lost_timeout_ms)
        .def_readwrite("pinch_threshold", &GestureThresholds::pinch_threshold)
        .def_readwrite("pinch_release_threshold", &GestureThresholds::pinch_release_threshold)
        .def_readwrite("finger_extended_threshold", &GestureThresholds::finger_extended_threshold);
    
    py::class_<EngineConfig>(m, "EngineConfig", "Complete engine configuration")
        .def(py::init<>())
        .def_readwrite("calibration", &EngineConfig::calibration)
        .def_readwrite("smoothing", &EngineConfig::smoothing)
        .def_readwrite("thresholds", &EngineConfig::thresholds)
        .def_readwrite("is_enabled", &EngineConfig::is_enabled)
        .def_readwrite("is_right_hand", &EngineConfig::is_right_hand)
        .def_readwrite("enable_left_click", &EngineConfig::enable_left_click)
        .def_readwrite("enable_right_click", &EngineConfig::enable_right_click)
        .def_readwrite("enable_scroll", &EngineConfig::enable_scroll)
        .def_readwrite("enable_drag", &EngineConfig::enable_drag)
        .def_readwrite("target_fps", &EngineConfig::target_fps)
        .def_readwrite("use_gpu", &EngineConfig::use_gpu);
    
    // ========================================================================
    // GESTURE ENGINE
    // ========================================================================
    
    py::class_<GestureEngine>(m, "GestureEngine", "Main gesture processing engine")
        .def(py::init<>())
        
        // Lifecycle
        .def("initialize", &GestureEngine::initialize, 
             py::arg("config"),
             "Initialize the engine with configuration")
        .def("start", &GestureEngine::start, 
             "Start the engine")
        .def("stop", &GestureEngine::stop, 
             "Stop the engine")
        .def("is_running", &GestureEngine::is_running, 
             "Check if engine is running")
        .def("set_input_enabled", &GestureEngine::set_input_enabled, 
             py::arg("enabled"),
             "Enable/disable mouse input injection")
        .def("is_input_enabled", &GestureEngine::is_input_enabled, 
             "Check if input injection is enabled")
        
        // Landmark processing - accepts numpy array
        .def("process_landmarks", 
             [](GestureEngine& self, 
                py::array_t<float> landmarks,
                float confidence,
                bool is_right_hand,
                int64_t timestamp_ms,
                int frame_width,
                int frame_height) {
                 // Ensure contiguous array
                 auto buf = landmarks.request();
                 if (buf.size != 63) {
                     throw std::runtime_error("Landmarks array must have 63 elements (21 landmarks * 3 coordinates)");
                 }
                 self.process_landmarks(
                     static_cast<float*>(buf.ptr),
                     confidence,
                     is_right_hand,
                     timestamp_ms,
                     frame_width,
                     frame_height
                 );
             },
             py::arg("landmarks"),
             py::arg("confidence"),
             py::arg("is_right_hand"),
             py::arg("timestamp_ms"),
             py::arg("frame_width"),
             py::arg("frame_height"),
             "Process hand landmarks from MediaPipe")
        
        .def("process_no_detection", &GestureEngine::process_no_detection,
             "Notify engine that no hand was detected")
        
        // State queries
        .def("get_current_gesture", &GestureEngine::get_current_gesture,
             "Get current gesture type")
        .def("get_current_confidence", &GestureEngine::get_current_confidence,
             "Get current gesture confidence")
        .def("get_current_gesture_name", &GestureEngine::get_current_gesture_name,
             "Get current gesture as string")
        .def("is_tracking", &GestureEngine::is_tracking,
             "Check if hand tracking is active")
        .def("get_cursor_position", &GestureEngine::get_cursor_position,
             "Get current cursor position")
        
        // Configuration
        .def("set_config", &GestureEngine::set_config,
             py::arg("config"),
             "Update engine configuration")
        .def("get_config", &GestureEngine::get_config,
             "Get current configuration")
        .def("set_calibration", &GestureEngine::set_calibration,
             py::arg("calibration"),
             "Update calibration data")
        .def("set_smoothing", &GestureEngine::set_smoothing,
             py::arg("smoothing"),
             "Update smoothing configuration")
        .def("set_thresholds", &GestureEngine::set_thresholds,
             py::arg("thresholds"),
             "Update gesture thresholds")
        .def("set_hand_preference", &GestureEngine::set_hand_preference,
             py::arg("right_hand"),
             "Set which hand to track")
        
        // Performance
        .def("get_fps", &GestureEngine::get_fps,
             "Get current FPS")
        .def("get_performance_metrics", &GestureEngine::get_performance_metrics,
             "Get performance metrics")
        .def("reset_performance_counters", &GestureEngine::reset_performance_counters,
             "Reset performance counters")
        
        // Callbacks
        .def("set_state_change_callback", &GestureEngine::set_state_change_callback,
             py::arg("callback"),
             "Set callback for gesture state changes")
        .def("set_error_callback", &GestureEngine::set_error_callback,
             py::arg("callback"),
             "Set callback for errors");
    
    // ========================================================================
    // UTILITY FUNCTIONS
    // ========================================================================
    
    m.def("gesture_to_string", &gesture_to_string,
          py::arg("type"),
          "Convert gesture type to human-readable string");
    
    m.def("get_timestamp_ms", &get_timestamp_ms,
          "Get current timestamp in milliseconds");
    
    // ========================================================================
    // CONSTANTS
    // ========================================================================
    
    m.attr("VERSION_MAJOR") = config::VERSION_MAJOR;
    m.attr("VERSION_MINOR") = config::VERSION_MINOR;
    m.attr("VERSION_PATCH") = config::VERSION_PATCH;
    
    m.attr("DEFAULT_SMOOTHING_ALPHA") = config::DEFAULT_SMOOTHING_ALPHA;
    m.attr("DEFAULT_VELOCITY_SCALE") = config::DEFAULT_VELOCITY_SCALE;
    m.attr("DEFAULT_JITTER_THRESHOLD") = config::DEFAULT_JITTER_THRESHOLD;
    m.attr("DEFAULT_MIN_DETECTION_CONFIDENCE") = config::DEFAULT_MIN_DETECTION_CONFIDENCE;
    m.attr("DEFAULT_MIN_TRACKING_CONFIDENCE") = config::DEFAULT_MIN_TRACKING_CONFIDENCE;
    m.attr("DWELL_TIME_MS") = config::DWELL_TIME_MS;
    m.attr("CLICK_DEBOUNCE_MS") = config::CLICK_DEBOUNCE_MS;
}
