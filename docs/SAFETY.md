# WavePoint Safety Documentation

WavePoint is designed with **safety-first** principles. The system is built to **fail safely** - when in doubt, it pauses rather than performing unintended actions.

## Design Philosophy

## Safety Mechanisms

### 1. Test Mode Requirement

Users **must** verify their setup in Test Mode before enabling mouse control:

- Camera preview shows what the system sees
- Gesture detection is displayed without any mouse control
- Confidence scores help identify lighting/positioning issues
- Recommendations guide users to optimal setup

### 2. Confidence-Based Filtering

The system uses multiple confidence thresholds:

| Threshold            | Default | Purpose                           |
| -------------------- | ------- | --------------------------------- |
| Detection Confidence | 0.7     | Hand must be clearly visible      |
| Tracking Confidence  | 0.5     | Hand must be consistently tracked |
| Gesture Confidence   | 0.6     | Gesture must be unambiguous       |

**If any threshold is not met, no action is taken.**

### 3. Temporal Filtering (Dwell Time)

Actions require sustained gestures to prevent accidental triggers:

- **Click**: 100ms sustained pinch
- **Drag**: 300ms sustained fist
- **Minimum consecutive frames**: 3

### 4. Debouncing

Prevents rapid repeated actions:

- **Click debounce**: 200ms between clicks
- **Scroll debounce**: 50ms between scroll events

### 5. Hysteresis

Prevents gesture state flickering:

- **Pinch threshold**: 0.05 (to activate)
- **Release threshold**: 0.08 (to deactivate)

This gap prevents rapid on/off switching at the boundary.

### 6. Tracking Loss Handling

When hand tracking is lost:

1. **Grace period**: 5 frames before action
2. **Timeout**: 500ms before auto-pause
3. **Button release**: Any held buttons are released
4. **State reset**: System returns to neutral

### 7. Dead Zones

Configurable dead zones prevent:

- Accidental cursor movement in center position
- Edge-of-screen issues
- Jitter in stable hand positions

### 8. Maximum Cursor Jump

Single-frame cursor movements are limited to prevent:

- Cursor teleporting across screen
- Unintended large movements from tracking glitches

## Failure Modes

### Safe Failures

| Condition         | System Response              |
| ----------------- | ---------------------------- |
| Hand not detected | Pause all input              |
| Low confidence    | Ignore gesture               |
| Tracking lost     | Release buttons, pause       |
| Ambiguous gesture | Default to neutral           |
| System overload   | Drop frames, maintain safety |

### Recovery

The system automatically recovers when:

- Hand becomes visible again
- Confidence improves
- Tracking stabilizes

No user intervention required for recovery.

## Privacy & Security

### No Data Collection

- **No cloud connectivity**: All processing is local
- **No video storage**: Frames are processed and discarded
- **No telemetry**: No usage data is collected
- **No network access**: Application works offline

### Camera Access

- Camera is only accessed when tracking is active
- Camera is released when application exits
- No background camera access

### Input Injection

- Uses standard Windows SendInput API
- No kernel-level drivers
- No system modifications
- Can be disabled instantly

## User Controls

### Quick Disable

Multiple ways to disable mouse control:

1. **Tray icon**: Right-click → Disable
2. **Main window**: Toggle button
3. **Keyboard**: Close application
4. **Physical mouse**: Always works, overrides gesture input

### Emergency Stop

If gesture control becomes problematic:

1. Move physical mouse - it always works
2. Click tray icon to disable
3. Close application from Task Manager if needed

## Accessibility Considerations

### Target Users

WavePoint is designed for users who:

- Have difficulty using traditional mouse
- Need hands-free computer control
- Want alternative input methods

### Limitations

Users should be aware:

- Requires visible hand in camera frame
- Affected by lighting conditions
- May have learning curve
- Not suitable for precision tasks initially

### Recommendations

1. Start with Test Mode
2. Calibrate for your setup
3. Practice gestures before enabling control
4. Adjust sensitivity settings as needed
5. Use in well-lit environment

## Testing Checklist

Before enabling mouse control, verify:

- [ ] Hand is clearly visible in camera preview
- [ ] Detection rate > 80%
- [ ] Confidence scores > 70%
- [ ] FPS > 20
- [ ] All intended gestures are recognized
- [ ] No false positives in neutral position
- [ ] Lighting is adequate and stable

## Reporting Issues

If you experience safety issues:

1. Disable mouse control immediately
2. Note the conditions (lighting, gestures, etc.)
3. Check Test Mode to diagnose
4. Adjust settings or recalibrate
5. Report persistent issues with details
