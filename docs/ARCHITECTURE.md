# Architecture Details

WavePoint is a hybrid Python/C++ application designed for real-time hand gesture recognition and mouse control. The architecture prioritizes low latency, stability, and safety.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER INTERFACE                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────────┐   │
│  │  System     │  │    Main     │  │  Settings   │  │  Calibration  │   │
│  │   Tray      │  │   Window    │  │   Dialog    │  │    Dialog     │   │ 
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └───────┬───────┘   │
│         │                │                │                 │           │
│         └────────────────┴────────────────┴─────────────────┘           │
│                                   │                                     │
│                          ┌────────┴─────────┐                           │
│                          │   WavePointApp   │                           │
│                          │   (Coordinator)  │                           │
│                          └────────┬─────────┘                           │
└───────────────────────────────────┼─────────────────────────────────────┘
                                    │
┌───────────────────────────────────┼─────────────────────────────────────┐
│                           PYTHON LAYER                                   │
│                                   │                                      │
│  ┌────────────────────────────────┼────────────────────────────────┐    │
│  │                                │                                │    │
│  │  ┌─────────────┐    ┌─────────┴─────────┐    ┌─────────────┐   │    │
│  │  │    Hand     │    │     Test Mode     │    │ Calibration │   │    │
│  │  │   Tracker   │    │                   │    │   Manager   │   │    │
│  │  │ (MediaPipe) │    │                   │    │             │   │    │
│  │  └──────┬──────┘    └───────────────────┘    └─────────────┘   │    │
│  │         │                                                       │    │
│  │         │  HandData                                             │    │
│  │         ▼                                                       │    │
│  │  ┌─────────────────────────────────────────────────────────┐   │    │
│  │  │              Gesture Processor (Bridge)                  │   │    │
│  │  │                                                          │   │    │
│  │  │  - Converts HandData to C++ format                       │   │    │
│  │  │  - Manages engine lifecycle                              │   │    │
│  │  │  - Emits Qt signals for UI updates                       │   │    │
│  │  └──────────────────────────┬──────────────────────────────┘   │    │
│  │                             │                                   │    │
│  └─────────────────────────────┼───────────────────────────────────┘    │
│                                │                                         │
└────────────────────────────────┼─────────────────────────────────────────┘
                                 │ pybind11
┌────────────────────────────────┼─────────────────────────────────────────┐
│                            C++ CORE                                       │
│                                │                                          │
│  ┌─────────────────────────────┴─────────────────────────────────────┐   │
│  │                        GestureEngine                               │   │
│  │                                                                    │   │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────┐  │   │
│  │  │  GestureState    │  │  CursorSmoother  │  │ CoordinateMapper│  │   │
│  │  │    Machine       │  │                  │  │                 │  │   │
│  │  │                  │  │  - Exponential   │  │  - Camera to    │  │   │
│  │  │  - Gesture       │  │    smoothing     │  │    screen       │  │   │
│  │  │    classification│  │  - Jitter filter │  │  - Dead zones   │  │   │
│  │  │  - Dwell time    │  │  - Acceleration  │  │  - Multi-monitor│  │   │
│  │  │  - Hysteresis    │  │                  │  │                 │  │   │
│  │  └────────┬─────────┘  └────────┬─────────┘  └────────┬────────┘  │   │
│  │           │                     │                     │           │   │
│  │           └─────────────────────┼─────────────────────┘           │   │
│  │                                 │                                  │   │
│  │                                 ▼                                  │   │
│  │                    ┌────────────────────────┐                     │   │
│  │                    │    InputInjector       │                     │   │
│  │                    │                        │                     │   │
│  │                    │  - SendInput API       │                     │   │
│  │                    │  - Absolute positioning│                     │   │
│  │                    │  - Click/scroll/drag   │                     │   │
│  │                    └────────────┬───────────┘                     │   │
│  │                                 │                                  │   │
│  └─────────────────────────────────┼──────────────────────────────────┘   │
│                                    │                                      │
└────────────────────────────────────┼──────────────────────────────────────┘
                                     │
                                     ▼
                            ┌────────────────┐
                            │  Windows OS    │
                            │  Input System  │
                            └────────────────┘
```

## Threading Model

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          THREADING MODEL                                 │
│                                                                          │
│  ┌─────────────────┐                                                    │
│  │  Main Thread    │  Qt Event Loop, UI updates                         │
│  │  (Python)       │                                                    │
│  └────────┬────────┘                                                    │
│           │                                                              │
│  ┌────────┴────────┐                                                    │
│  │                 │                                                    │
│  ▼                 ▼                                                    │
│  ┌─────────────────┐  ┌─────────────────┐                              │
│  │ Capture Thread  │  │ Process Thread  │                              │
│  │ (Python)        │  │ (Python)        │                              │
│  │                 │  │                 │                              │
│  │ - cv2.read()    │  │ - MediaPipe     │                              │
│  │ - Frame queue   │  │ - Preprocessing │                              │
│  └────────┬────────┘  └────────┬────────┘                              │
│           │                    │                                        │
│           │  Frame             │  HandData                              │
│           ▼                    ▼                                        │
│  ┌─────────────────────────────────────────┐                           │
│  │         Thread-Safe Queues              │                           │
│  │         (Lock-free SPSC)                │                           │
│  └─────────────────────────────────────────┘                           │
│                        │                                                │
│                        ▼                                                │
│  ┌─────────────────────────────────────────┐                           │
│  │      C++ Gesture Processing             │                           │
│  │      (Called from Python thread)        │                           │
│  │                                         │                           │
│  │  - State machine update                 │                           │
│  │  - Cursor smoothing                     │                           │
│  │  - Input injection (SendInput)          │                           │
│  └─────────────────────────────────────────┘                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Frame Processing Pipeline

```
Camera Frame (BGR)
       │
       ▼
┌──────────────────┐
│  Preprocessing   │
│  - Brightness    │
│    normalization │
│  - CLAHE         │
│  - Blur          │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  MediaPipe       │
│  Hands           │
│  - 21 landmarks  │
│  - Confidence    │
│  - Handedness    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  HandData        │
│  - landmarks[21] │
│  - confidence    │
│  - timestamp     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  C++ Engine      │
│  process_        │
│  landmarks()     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Gesture State   │
│  Machine         │
│  - Classify      │
│  - Temporal      │
│    filter        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Coordinate      │
│  Mapper          │
│  - Camera→Screen │
│  - Dead zone     │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Cursor          │
│  Smoother        │
│  - History avg   │
│  - Jitter filter │
│  - Acceleration  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Input           │
│  Injector        │
│  - SendInput()   │
└──────────────────┘
```

## Gesture State Machine

```
                    ┌─────────────────┐
                    │      NONE       │
                    │  (No detection) │
                    └────────┬────────┘
                             │
                    Hand detected
                             │
                             ▼
              ┌──────────────────────────────┐
              │           NEUTRAL            │
              │        (Open palm)           │
              │    Cursor moves, no action   │
              └──────────────┬───────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐  ┌─────────────────┐  ┌───────────────┐
│   POINTING    │  │   LEFT_CLICK    │  │  RIGHT_CLICK  │
│ (Index only)  │  │ (Thumb+Index)   │  │ (Thumb+Middle)│
│               │  │                 │  │               │
│ Cursor moves  │  │ Dwell → Click   │  │ Dwell → Click │
└───────────────┘  └─────────────────┘  └───────────────┘
        │                    │                    │
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐  ┌─────────────────┐  ┌───────────────┐
│    SCROLL     │  │      DRAG       │  │     PAUSE     │
│ (2 fingers)   │  │    (Fist)       │  │ (Hand lost)   │
│               │  │                 │  │               │
│ Vertical move │  │ Hold + move     │  │ No action     │
│ → scroll      │  │                 │  │               │
└───────────────┘  └─────────────────┘  └───────────────┘
```

## Safety Mechanisms

### 1. Confidence Thresholds

- Detection confidence: 0.7 minimum
- Tracking confidence: 0.5 minimum
- Gesture confidence: 0.6 minimum

### 2. Temporal Filtering

- Dwell time: 100ms for clicks
- Drag dwell: 300ms
- Debounce: 200ms between clicks

### 3. Hysteresis

- Pinch threshold: 0.05
- Release threshold: 0.08 (prevents flicker)

### 4. Auto-Pause

- Tracking lost timeout: 500ms
- Automatic button release on pause

### 5. Dead Zones

- Configurable center dead zone
- Edge clamping

## Configuration System

```
%APPDATA%\WavePoint\
├── config.json           # App settings
└── profiles\
    ├── Default.json      # Default profile
    └── Custom.json       # User profiles
```

## Performance Targets

| Metric                 | Target | Rationale            |
| ---------------------- | ------ | -------------------- |
| End-to-end latency     | <50ms  | Responsive feel      |
| Frame processing       | <20ms  | 30+ FPS              |
| Gesture classification | <5ms   | Real-time            |
| Input injection        | <1ms   | Immediate response   |
| Memory usage           | <200MB | Low footprint        |
| CPU usage              | <15%   | Background operation |

## Module Dependencies

```
gesture_mouse/
├── __init__.py
├── __main__.py
├── app.py              ← Entry point, coordinates all modules
├── config.py           ← Configuration management
├── hand_tracker.py     ← MediaPipe integration
├── test_mode.py        ← Safe testing environment
├── calibration.py      ← Coordinate calibration
├── gesture_mouse_core.pyd  ← C++ extension (built)
└── ui/
    ├── main_window.py
    ├── tray_icon.py
    ├── settings_dialog.py
    ├── test_mode_widget.py
    └── calibration_dialog.py
```
