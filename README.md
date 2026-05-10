# WavePoint

A **production-grade** Windows application for controlling your laptop using hand gestures detected through a webcam.

## Overview

WavePoint is a hybrid Python/C++ application that provides real-time, low-latency cursor control using hand gesture recognition. It is designed for **accessibility**, **stability**, and **safety**.

**Key Principles:**

- Safety-first: Fails safely, never misclicks
- Accessibility-grade: Designed for users who need alternative input
- Works offline: No cloud, no telemetry, complete privacy
- Low-latency: <50ms end-to-end response time

## Features

| Gesture                   | Action          |
| ------------------------- | --------------- |
| **Index finger pointing** | Cursor movement |
| **Thumb + index pinch**   | Left click      |
| **Thumb + middle pinch**  | Right click     |
| **Two fingers vertical**  | Scroll up/down  |
| **Closed fist**           | Drag (hold)     |
| **Open palm**             | Neutral / pause |
| **Hand removed**          | Auto pause      |

## System Requirements

### Minimum Requirements

- **OS**: Windows 10/11 (64-bit)
- **CPU**: Any modern dual-core processor
- **RAM**: 4GB (200MB used by application)
- **Camera**: 720p webcam @ 30 FPS
- **Python**: 3.9 or higher

### Build Requirements (for C++ core)

- Visual Studio 2019 or 2022 with C++ workload
- CMake 3.20+
- pybind11

## Quick Start

### Option 1: Easy Setup (Recommended)

```batch
# Run the setup script
scripts\setup.bat

# Run the application
scripts\run.bat
```

### Option 2: Manual Setup

```batch
# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run application (Python-only mode)
python -m gesture_mouse
```

### Option 3: Full Build (with C++ core for best performance)

```batch
# Setup Python environment first
scripts\setup.bat

# Build C++ core (requires Visual Studio)
scripts\build.bat

# Run application
scripts\run.bat
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Python Layer                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │  Tray    │  │ Settings │  │   Test   │  │   Calibration    │ │
│  │   UI     │  │  Panel   │  │   Mode   │  │     Workflow     │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘ │
│       └─────────────┴─────────────┴──────────────────┘           │
│                              │                                    │
│  ┌───────────────────────────┴────────────────────────────────┐  │
│  │                 Hand Tracking Module                        │  │
│  │            (MediaPipe + OpenCV Preprocessing)               │  │
│  └───────────────────────────┬────────────────────────────────┘  │
└──────────────────────────────┼───────────────────────────────────┘
                               │ pybind11
┌──────────────────────────────┼───────────────────────────────────┐
│                          C++ Core                                 │
│  ┌───────────────────────────┴────────────────────────────────┐  │
│  │                     GestureEngine                           │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐            │  │
│  │  │  Gesture   │  │   Cursor   │  │    OS      │            │  │
│  │  │   State    │  │  Smoother  │  │   Input    │            │  │
│  │  │  Machine   │  │            │  │  Injector  │            │  │
│  │  └────────────┘  └────────────┘  └────────────┘            │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Threading Model

| Thread   | Responsibility         | Latency Budget |
| -------- | ---------------------- | -------------- |
| Thread 1 | Camera capture         | ~10ms          |
| Thread 2 | MediaPipe inference    | ~15ms          |
| Thread 3 | Gesture classification | ~5ms           |
| Thread 4 | OS input injection     | ~1ms           |

**Total target latency: <50ms**

## Usage Guide

### First Time Setup

1. **Launch Application**

   ```batch
   scripts\run.bat
   ```

2. **Test Mode (Required First Step)**

   - Application starts in Test Mode by default
   - Verify your hand is detected (green landmarks)
   - Check confidence score is >70%
   - Ensure FPS is >20
   - Practice all gestures

3. **Calibrate**

   - Click "Calibrate" button
   - Point at 5 screen markers
   - Hold steady for 1.5 seconds each
   - Verify cursor follows hand correctly

4. **Enable Control**
   - Only after successful testing
   - Click "Enable Mouse Control"
   - Your hand now controls the cursor!

### Gesture Guide

**Pointing (Cursor Movement)**

- Extend index finger, curl others
- Cursor follows fingertip

**Left Click**

- Touch thumb tip to index fingertip
- Hold for ~100ms to confirm

**Right Click**

- Touch thumb tip to middle fingertip
- Hold for ~100ms to confirm

**Scroll**

- Extend index and middle fingers together
- Move hand up/down to scroll

**Drag**

- Make a fist
- Move to drag
- Open hand to release

**Pause/Neutral**

- Open palm with all fingers extended
- Cursor moves but no actions triggered

## Safety Features

WavePoint is designed to **fail safely**:

| Feature                   | Description                                   |
| ------------------------- | --------------------------------------------- |
| **Confidence thresholds** | No action on uncertain detection              |
| **Dwell time**            | Actions require sustained gesture (100-300ms) |
| **Hysteresis**            | Prevents rapid state flickering               |
| **Auto-pause**            | Pauses when hand is lost for 500ms            |
| **Dead zones**            | Prevents accidental edge movements            |
| **Debouncing**            | 200ms minimum between clicks                  |
| **Test Mode**             | Verify setup before enabling control          |

## Configuration

Settings are stored in:

```
%APPDATA%\WavePoint\
├── config.json           # Application settings
└── profiles\
    ├── Default.json      # Default profile
    └── [Custom].json     # User profiles
```

### Adjustable Settings

- **Cursor smoothing**: Lower = smoother, higher = more responsive
- **Cursor speed**: Movement multiplier
- **Dwell time**: How long to hold gesture before action
- **Confidence thresholds**: Detection sensitivity
- **Dead zone**: Center area with no cursor movement

## Troubleshooting

### Hand Not Detected

- Ensure good, even lighting
- Avoid backlight (window behind you)
- Keep hand within camera frame
- Try plain background

### Low FPS

- Close other applications
- Reduce camera resolution in settings
- Ensure no other app is using camera

### Cursor Jumpy

- Increase smoothing in settings
- Calibrate for your setup
- Check lighting conditions

### Gestures Not Recognized

- Practice in Test Mode first
- Adjust confidence thresholds
- Ensure clear gesture formation

## Privacy & Security

**WavePoint respects your privacy:**

- ✅ **No cloud connectivity** - Works completely offline
- ✅ **No video storage** - Frames processed and discarded
- ✅ **No telemetry** - No usage data collected
- ✅ **No network access** - No internet required
- ✅ **Local processing only** - All computation on your machine

## Project Structure

```
WavePoint/
├── src/
│   ├── cpp/                    # C++ core
│   │   ├── include/            # Header files
│   │   ├── bindings/           # pybind11 bindings
│   │   └── *.cpp               # Implementation
│   └── gesture_mouse/          # Python package
│       ├── ui/                 # PyQt6 UI components
│       ├── app.py              # Main application
│       ├── config.py           # Configuration
│       ├── hand_tracker.py     # MediaPipe integration
│       ├── calibration.py      # Calibration workflow
│       └── test_mode.py        # Test mode
├── scripts/                    # Build/run scripts
├── docs/                       # Documentation
├── CMakeLists.txt              # C++ build config
├── requirements.txt            # Python dependencies
└── pyproject.toml              # Python package config
```

## Documentation

- [Architecture Details](docs/ARCHITECTURE.md)
- [Safety Documentation](docs/SAFETY.md)

## License

MIT License

## Acknowledgments

- [MediaPipe](https://mediapipe.dev/) - Hand landmark detection
- [OpenCV](https://opencv.org/) - Computer vision
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - User interface
- [pybind11](https://pybind11.readthedocs.io/) - Python/C++ binding
