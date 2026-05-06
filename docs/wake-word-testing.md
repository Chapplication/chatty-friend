# Wake Word Detection Testing

This document describes how to use the wake word detection test framework to validate algorithm changes and prevent regressions.

## Overview

The test framework in `tests/` allows you to:
- Store recorded wake word detection examples (true positives, false positives, false negatives)
- Replay them against the detection algorithm
- Validate that algorithm changes don't break existing behavior

## Quick Start

### Run All Tests

```bash
python tests/test_wake_detection.py
```

Output:
```
Wake Word Detection Test Suite
========================================
[PASS] tp_loud_close_20260201_1: detect - expected detect
[FAIL] fn_quiet_room_20260201_1: got reject (LOW_SCORE), expected detect
[PASS] fp_conversation_20260201_1: reject (CONTINUOUS_SPEECH) - expected reject

Results: 2/3 passed (66.7%)
```

### Run with Verbose Output

See frame-by-frame decision making:

```bash
python tests/test_wake_detection.py --verbose
```

### Run a Specific Test

```bash
python tests/test_wake_detection.py --id fp_conversation_20260201_1
```

## Adding New Test Cases

When you encounter a false positive or false negative, capture the log output and add it as a test case.

### Method 1: Interactive Mode

```bash
python tests/test_wake_detection.py --add
```

1. Paste the log output (must include WAKE HISTORY lines)
2. Answer prompts for expected outcome and description
3. Test case is automatically added to `tests/wake_word_test_cases.json`

### Method 2: Manual Addition

1. Copy the WAKE HISTORY block from the log
2. Edit `tests/wake_word_test_cases.json`
3. Add a new entry to the `test_cases` array

#### Required Log Format

The parser needs the WAKE HISTORY frame dump. Look for lines like:

```
[wake] WAKE HISTORY: peak=0.697, voice=tracking:3+history:10/10 | duration=171ms | ...
[wake]   [ 0- 9]  0|0.06|0.696|  245|. ...
[wake]   [10-19]  ...
```

Each frame entry is: `timestamp|vad|wake_score|rms|tracking_flag`

#### Test Case Structure

```json
{
  "id": "fp_conversation_20260201_1",
  "description": "False positive - wake word detected during conversation",
  "expected_outcome": "reject",
  "expected_reason": "CONTINUOUS_SPEECH",
  "notes": "Optional notes about the scenario",
  "actual_outcome": "detect",
  "actual_reason": null,
  "frames": [
    {"t": 0, "vad": 0.69, "wake": 0.001, "rms": 53},
    {"t": 85, "vad": 0.65, "wake": 0.002, "rms": 48},
    ...
  ],
  "raw_log": "Original log text for reference"
}
```

#### Field Descriptions

| Field | Description |
|-------|-------------|
| `id` | Unique identifier (e.g., `fp_` for false positive, `fn_` for false negative, `tp_` for true positive) |
| `expected_outcome` | What SHOULD happen: `"detect"` or `"reject"` |
| `expected_reason` | If reject, which reason: `"WEAK_VOICE"`, `"NO_VOICE"`, `"CONTINUOUS_SPEECH"`, `"LOW_SCORE"`, or `null` |
| `actual_outcome` | What actually happened when the bug was observed |
| `frames` | Array of frame data with `t` (time ms), `vad`, `wake`, `rms` |

### Naming Conventions

- `fp_*` - False positive (detected when it shouldn't have)
- `fn_*` - False negative (rejected when it should have detected)
- `tp_*` - True positive (correctly detected)
- `tn_*` - True negative (correctly rejected)

## Understanding Test Results

### PASS vs FAIL

- **PASS**: Algorithm produces the expected outcome
- **FAIL**: Algorithm produces a different outcome than expected

A failing test can mean:
1. **Regression**: A code change broke previously working behavior
2. **Known issue**: The test documents desired behavior not yet implemented (e.g., `fn_quiet_room` tests)

### Rejection Reasons

| Reason | Description |
|--------|-------------|
| `NO_VOICE` | No voice activity detected in tracking or history |
| `WEAK_VOICE` | Voice present but VAD never peaked >= 0.6 |
| `CONTINUOUS_SPEECH` | Wake word in middle of ongoing conversation (>1.5s continuous speech) |
| `LOW_SCORE` | Peak and cumulative scores below thresholds |

## Configuration

Default thresholds are stored in `tests/wake_word_test_cases.json`:

```json
{
  "default_config": {
    "vad_threshold": 0.3,
    "entry_threshold": 0.35,
    "confirm_peak": 0.45,
    "confirm_cumulative": 1.2,
    "min_frames_above_entry": 2,
    "continuous_speech_max_ms": 1500.0,
    "continuous_speech_peak": 0.88,
    "vad_lookback": 10
  }
}
```

These match the defaults in `chatty_mic.py`. Individual test cases can override these with a `config` field if needed.

## Workflow for Algorithm Changes

1. **Before changing `chatty_mic.py`**: Run the test suite to establish baseline
   ```bash
   python tests/test_wake_detection.py
   ```

2. **Make your changes** to the detection algorithm

3. **Run tests again** to check for regressions
   ```bash
   python tests/test_wake_detection.py --verbose
   ```

4. **If tests fail**: Either fix the regression or update the test if the new behavior is intentional

5. **Add new test cases** for any bugs you fix to prevent future regressions

## Troubleshooting

### "No frames in test case"

The test case is missing frame data. Re-capture the log with WAKE HISTORY output.

### Parser not finding frames

Ensure the log includes the full WAKE HISTORY block with frame lines like:
```
[ 0- 9]  0|0.06|0.696|  245|. ...
```

### Test passes but real system fails

The simulator may not perfectly match the real system. Check:
- Are the config values in sync?
- Is the test case frame data complete (all 62 frames)?
- Was the log captured with the current logging format?
