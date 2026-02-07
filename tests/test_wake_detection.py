#!/usr/bin/env python3
"""
Wake Word Detection Test Framework

Regression testing for wake word detection algorithm changes.
Replays recorded frame sequences and validates detection outcomes.

Usage:
    python tests/test_wake_detection.py              # Run all tests
    python tests/test_wake_detection.py --id <id>    # Run specific test
    python tests/test_wake_detection.py --add        # Add new test case interactively
    python tests/test_wake_detection.py --verbose    # Verbose frame-by-frame output
"""

import argparse
import json
import re
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ============================================================================
# Log Parser
# ============================================================================

def parse_wake_history_line(line: str) -> list[dict]:
    """
    Parse a WAKE HISTORY frame line into frame objects.
    
    Input format:
    [60-61]  4779|0.06|0.719|  207|T   4864|0.05|0.135|  571|T
    
    Output: list of {t: int, vad: float, wake: float, rms: int, tracking: bool}
    """
    frames = []
    
    # Remove the [xx-yy] prefix
    line = re.sub(r'^\s*\[\s*\d+-\s*\d+\]\s*', '', line)
    
    # Pattern: time|vad|wake|rms|flag (with variable whitespace)
    # Example: 4779|0.06|0.719|  207|T
    pattern = r'(\d+)\|([\d.]+)\|([\d.]+)\|\s*(\d+)\|([T.])'
    
    for match in re.finditer(pattern, line):
        frames.append({
            't': int(match.group(1)),
            'vad': float(match.group(2)),
            'wake': float(match.group(3)),
            'rms': int(match.group(4)),
            'tracking': match.group(5) == 'T'
        })
    
    return frames


def parse_wake_history_block(log_text: str) -> list[dict]:
    """
    Parse the full WAKE HISTORY block from log output.
    
    Extracts all frame data from lines like:
    [wake    ]   [ 0- 9]  0|0.06|0.696|  245|. ...
    """
    frames = []
    
    for line in log_text.split('\n'):
        # Look for WAKE HISTORY frame lines (contain bracket ranges like [0-9])
        if re.search(r'\[\s*\d+-\s*\d+\]', line) and '|' in line:
            frames.extend(parse_wake_history_line(line))
    
    # Sort by timestamp
    frames.sort(key=lambda f: f['t'])
    return frames


def parse_outcome_from_log(log_text: str) -> tuple[str, Optional[str]]:
    """
    Parse the detection outcome from log text.
    
    Returns: (outcome, reason) where outcome is 'detect' or 'reject'
    """
    # Check for DETECTED
    if 'DETECTED -' in log_text or 'DETECTED:' in log_text:
        return ('detect', None)
    
    # Check for rejection reasons
    rejection_patterns = [
        (r'REJECTED - (NO_VOICE)', 'NO_VOICE'),
        (r'REJECTED - (WEAK_VOICE)', 'WEAK_VOICE'),
        (r'REJECTED - (CONTINUOUS_SPEECH)', 'CONTINUOUS_SPEECH'),
        (r'REJECTED - peak=', 'LOW_SCORE'),
    ]
    
    for pattern, reason in rejection_patterns:
        if re.search(pattern, log_text):
            return ('reject', reason)
    
    return ('unknown', None)


# ============================================================================
# Detection Algorithm Simulator
# ============================================================================

@dataclass
class SimulatorConfig:
    """Configuration for wake detection simulator."""
    vad_threshold: float = 0.3
    entry_threshold: float = 0.35
    confirm_peak: float = 0.45
    confirm_cumulative: float = 1.2
    min_frames_above_entry: int = 2
    continuous_speech_max_ms: float = 1500.0
    continuous_speech_peak: float = 0.88
    vad_lookback: int = 10
    
    @classmethod
    def from_dict(cls, d: dict) -> 'SimulatorConfig':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class DetectionResult:
    """Result of running detection on a frame sequence."""
    outcome: str  # 'detect', 'reject', or 'no_trigger'
    reason: Optional[str] = None  # Rejection reason if rejected
    peak_score: float = 0.0
    cumulative_score: float = 0.0
    frames_above_entry: int = 0
    max_vad_tracking: float = 0.0
    max_vad_history: float = 0.0
    continuous_voice_ms: float = 0.0
    tracking_frames: int = 0
    details: str = ""


class WakeDetectionSimulator:
    """
    Simulates the wake word detection algorithm for testing.
    
    Replicates the logic from chatty_mic.py's _evaluate_cluster_detection().
    """
    
    def __init__(self, config: Optional[SimulatorConfig] = None):
        self.config = config or SimulatorConfig()
        self.reset()
    
    def reset(self):
        """Reset all state for a new test."""
        self.vad_history = deque(maxlen=25)
        self.vad_score_history = deque(maxlen=25)
        self.frame_history = deque(maxlen=62)
        self.tracking = False
        self.tracking_scores = []
        self.tracking_vad_scores = []
        self.result: Optional[DetectionResult] = None
    
    def process_frames(self, frames: list[dict], verbose: bool = False) -> DetectionResult:
        """
        Process a sequence of frames and return the detection result.
        
        Args:
            frames: List of frame dicts with 't', 'vad', 'wake', 'rms' keys
            verbose: If True, print frame-by-frame details
        
        Returns:
            DetectionResult with outcome and details
        """
        self.reset()
        last_result = None
        
        for i, frame in enumerate(frames):
            vad_score = frame['vad']
            wake_score = frame['wake']
            
            # Update history buffers (like real detector does)
            is_voice = vad_score > self.config.vad_threshold
            self.vad_history.append(is_voice)
            self.vad_score_history.append(vad_score)
            self.frame_history.append({
                'vad': vad_score,
                'wake': wake_score,
                'rms': frame.get('rms', 0),
            })
            
            # Run detection logic
            result = self._evaluate_frame(wake_score, vad_score, verbose, i)
            
            if result is not None:
                # If detected, return immediately (like real detector)
                if result.outcome == 'detect':
                    return result
                # If rejected, save result but continue processing
                # (there may be another tracking cluster later)
                last_result = result
        
        # Return the last result if any clusters were evaluated
        if last_result is not None:
            return last_result
        
        # No trigger occurred
        return DetectionResult(outcome='no_trigger', details='Score never exceeded entry threshold')
    
    def _evaluate_frame(self, wake_score: float, vad_score: float, 
                        verbose: bool, frame_idx: int) -> Optional[DetectionResult]:
        """Evaluate a single frame. Returns result if detection/rejection occurs."""
        
        cfg = self.config
        above_entry = wake_score >= cfg.entry_threshold
        
        if self.tracking:
            # We're tracking a potential wake word
            self.tracking_scores.append(wake_score)
            self.tracking_vad_scores.append(vad_score)
            
            if verbose:
                print(f"  Frame {frame_idx}: tracking frame {len(self.tracking_scores)}, "
                      f"score={wake_score:.3f}, vad={vad_score:.2f}, above_entry={above_entry}")
            
            if not above_entry:
                # Score dropped below entry - evaluate the cluster
                return self._evaluate_cluster(verbose)
        else:
            # Not currently tracking
            if above_entry:
                # Start tracking
                self.tracking = True
                self.tracking_scores = [wake_score]
                self.tracking_vad_scores = [vad_score]
                
                if verbose:
                    print(f"  Frame {frame_idx}: TRACKING START, score={wake_score:.3f}, vad={vad_score:.2f}")
        
        return None
    
    def _evaluate_cluster(self, verbose: bool) -> DetectionResult:
        """Evaluate a completed tracking cluster."""
        
        cfg = self.config
        vad_threshold = cfg.vad_threshold
        
        peak_score = max(self.tracking_scores)
        cumulative_score = sum(self.tracking_scores)
        frames_above = sum(1 for s in self.tracking_scores if s >= cfg.entry_threshold)
        
        # VAD gating: check for voice DURING tracking OR in recent history
        voice_frames_tracking = sum(1 for v in self.tracking_vad_scores if v > vad_threshold)
        
        # Check VAD history (lookback before tracking)
        recent_vad = list(self.vad_history)[-cfg.vad_lookback:]
        voice_frames_history = sum(1 for v in recent_vad if v)
        
        has_voice = voice_frames_tracking > 0 or voice_frames_history > 0
        max_vad_tracking = max(self.tracking_vad_scores) if self.tracking_vad_scores else 0
        
        # Get max VAD from history window (BEFORE tracking started)
        recent_vad_scores = list(self.vad_score_history)[-cfg.vad_lookback:]
        max_vad_history = max(recent_vad_scores) if recent_vad_scores else 0
        
        # Use the MAXIMUM of tracking VAD and recent history VAD
        max_vad_combined = max(max_vad_tracking, max_vad_history)
        
        # Require VAD to peak significantly above threshold
        vad_peak_required = min(vad_threshold + 0.3, 1.0)
        has_strong_voice = max_vad_combined >= vad_peak_required
        
        # Calculate continuous voice duration before tracking started
        history = list(self.frame_history)
        num_tracking_frames = len(self.tracking_scores)
        continuous_voice_before_ms = 0
        if len(history) > num_tracking_frames:
            pre_tracking_history = history[:-num_tracking_frames] if num_tracking_frames > 0 else history
            continuous_voice_frames = 0
            for f in reversed(pre_tracking_history):
                if f['vad'] >= vad_threshold:
                    continuous_voice_frames += 1
                else:
                    break
            continuous_voice_before_ms = continuous_voice_frames * 80
        
        # Determine required peak based on speech context
        in_continuous_speech = continuous_voice_before_ms > cfg.continuous_speech_max_ms
        required_peak = cfg.continuous_speech_peak if in_continuous_speech else cfg.confirm_peak
        
        # Build result
        result = DetectionResult(
            outcome='reject',
            peak_score=peak_score,
            cumulative_score=cumulative_score,
            frames_above_entry=frames_above,
            max_vad_tracking=max_vad_tracking,
            max_vad_history=max_vad_history,
            continuous_voice_ms=continuous_voice_before_ms,
            tracking_frames=len(self.tracking_scores),
        )
        
        # Apply detection logic
        if not has_voice:
            result.reason = 'NO_VOICE'
            result.details = f"peak={peak_score:.3f}, max_vad={max_vad_tracking:.2f}<{vad_threshold}"
        elif not has_strong_voice:
            result.reason = 'WEAK_VOICE'
            result.details = f"peak={peak_score:.3f}, max_vad_combined={max_vad_combined:.2f}<{vad_peak_required:.2f}"
        elif in_continuous_speech and peak_score < cfg.continuous_speech_peak:
            result.reason = 'CONTINUOUS_SPEECH'
            result.details = f"peak={peak_score:.3f}<{cfg.continuous_speech_peak:.2f}, continuous={continuous_voice_before_ms:.0f}ms"
        elif peak_score >= required_peak and frames_above > 1:
            result.outcome = 'detect'
            result.reason = None
            result.details = f"peak={peak_score:.3f}, frames_above={frames_above}"
        elif cumulative_score >= cfg.confirm_cumulative and frames_above >= cfg.min_frames_above_entry:
            if in_continuous_speech:
                result.reason = 'CONTINUOUS_SPEECH'
                result.details = f"cumul={cumulative_score:.2f}, peak={peak_score:.3f}<{cfg.continuous_speech_peak:.2f}"
            else:
                result.outcome = 'detect'
                result.reason = None
                result.details = f"cumul={cumulative_score:.2f}, frames_above={frames_above}"
        else:
            result.reason = 'LOW_SCORE'
            result.details = f"peak={peak_score:.3f}<{required_peak}, cumul={cumulative_score:.2f}<{cfg.confirm_cumulative}"
        
        if verbose:
            print(f"  CLUSTER EVALUATED: {result.outcome} ({result.reason or 'detected'})")
            print(f"    peak={peak_score:.3f}, cumul={cumulative_score:.2f}, frames_above={frames_above}")
            print(f"    max_vad_tracking={max_vad_tracking:.2f}, max_vad_history={max_vad_history:.2f}")
            print(f"    continuous_voice={continuous_voice_before_ms:.0f}ms, in_continuous={in_continuous_speech}")
        
        return result


# ============================================================================
# Test Runner
# ============================================================================

def load_test_cases(test_file: Path) -> tuple[dict, list[dict]]:
    """Load test cases from JSON file."""
    with open(test_file) as f:
        data = json.load(f)
    return data.get('default_config', {}), data.get('test_cases', [])


def save_test_cases(test_file: Path, default_config: dict, test_cases: list[dict]):
    """Save test cases to JSON file."""
    data = {
        'schema_version': '1.0',
        'description': 'Wake word detection test cases for regression testing algorithm changes',
        'default_config': default_config,
        'test_cases': test_cases,
    }
    with open(test_file, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Saved {len(test_cases)} test cases to {test_file}")


def run_test(test_case: dict, config: SimulatorConfig, verbose: bool = False) -> tuple[bool, str]:
    """
    Run a single test case.
    
    Returns: (passed, message)
    """
    simulator = WakeDetectionSimulator(config)
    
    if verbose:
        print(f"\n--- {test_case['id']}: {test_case.get('description', '')} ---")
    
    frames = test_case.get('frames', [])
    if not frames:
        return False, "No frames in test case"
    
    result = simulator.process_frames(frames, verbose=verbose)
    
    expected_outcome = test_case.get('expected_outcome', 'unknown')
    expected_reason = test_case.get('expected_reason')
    
    # Check outcome
    if result.outcome != expected_outcome:
        return False, f"got {result.outcome} ({result.reason}), expected {expected_outcome}"
    
    # If rejection, optionally check reason
    if expected_outcome == 'reject' and expected_reason:
        if result.reason != expected_reason:
            return False, f"got reason {result.reason}, expected {expected_reason}"
    
    return True, f"{result.outcome}" + (f" ({result.reason})" if result.reason else "")


def run_all_tests(test_file: Path, test_id: Optional[str] = None, verbose: bool = False):
    """Run all tests (or a specific test) and report results."""
    
    default_config, test_cases = load_test_cases(test_file)
    config = SimulatorConfig.from_dict(default_config)
    
    if not test_cases:
        print("No test cases found.")
        return
    
    # Filter to specific test if requested
    if test_id:
        test_cases = [tc for tc in test_cases if tc['id'] == test_id]
        if not test_cases:
            print(f"Test case '{test_id}' not found.")
            return
    
    print("Wake Word Detection Test Suite")
    print("=" * 40)
    
    passed = 0
    failed = 0
    
    for tc in test_cases:
        success, message = run_test(tc, config, verbose=verbose)
        
        status = "[PASS]" if success else "[FAIL]"
        expected = tc.get('expected_outcome', 'unknown')
        expected_reason = tc.get('expected_reason', '')
        expected_str = f"{expected}" + (f" ({expected_reason})" if expected_reason else "")
        
        print(f"{status} {tc['id']}: {message} - expected {expected_str}")
        
        if success:
            passed += 1
        else:
            failed += 1
    
    print()
    print(f"Results: {passed}/{passed + failed} passed ({100 * passed / (passed + failed):.1f}%)")
    
    return failed == 0


def add_test_interactive(test_file: Path):
    """Interactively add a new test case."""
    
    print("Paste the log output (including WAKE HISTORY), then press Ctrl+D (or Ctrl+Z on Windows):")
    print("-" * 40)
    
    try:
        log_text = sys.stdin.read()
    except KeyboardInterrupt:
        print("\nCancelled.")
        return
    
    print("-" * 40)
    
    # Parse the log
    frames = parse_wake_history_block(log_text)
    if not frames:
        print("Error: Could not parse any frames from the log.")
        print("Make sure the log contains WAKE HISTORY lines like:")
        print("  [ 0- 9]  0|0.06|0.696|  245|. ...")
        return
    
    print(f"Parsed {len(frames)} frames.")
    
    # Parse outcome
    actual_outcome, actual_reason = parse_outcome_from_log(log_text)
    print(f"Detected actual outcome: {actual_outcome}" + (f" ({actual_reason})" if actual_reason else ""))
    
    # Ask for expected outcome
    print("\nWhat SHOULD have happened?")
    print("  1. detect (wake word should have been detected)")
    print("  2. reject (wake word should have been rejected)")
    choice = input("Enter 1 or 2: ").strip()
    
    if choice == '1':
        expected_outcome = 'detect'
        expected_reason = None
    elif choice == '2':
        expected_outcome = 'reject'
        print("\nExpected rejection reason?")
        print("  1. WEAK_VOICE")
        print("  2. NO_VOICE")
        print("  3. CONTINUOUS_SPEECH")
        print("  4. LOW_SCORE")
        print("  5. (none/any)")
        reason_choice = input("Enter 1-5: ").strip()
        reasons = {
            '1': 'WEAK_VOICE',
            '2': 'NO_VOICE', 
            '3': 'CONTINUOUS_SPEECH',
            '4': 'LOW_SCORE',
            '5': None,
        }
        expected_reason = reasons.get(reason_choice)
    else:
        print("Invalid choice.")
        return
    
    # Get description
    description = input("\nDescription (e.g., 'False negative - quiet room, normal distance'): ").strip()
    
    # Get notes
    notes = input("Notes (optional): ").strip() or None
    
    # Generate ID
    import datetime
    date_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "tp" if expected_outcome == 'detect' else "fn" if actual_outcome == 'reject' else "fp"
    test_id = f"{prefix}_{date_str}"
    
    # Create test case
    test_case = {
        'id': test_id,
        'description': description,
        'expected_outcome': expected_outcome,
        'expected_reason': expected_reason,
        'notes': notes,
        'actual_outcome': actual_outcome,
        'actual_reason': actual_reason,
        'frames': frames,
        'raw_log': log_text[:2000],  # Truncate if very long
    }
    
    # Load existing and append
    default_config, test_cases = load_test_cases(test_file)
    test_cases.append(test_case)
    save_test_cases(test_file, default_config, test_cases)
    
    print(f"\nAdded test case '{test_id}'")
    
    # Optionally run the test
    run_now = input("Run test now? (y/n): ").strip().lower()
    if run_now == 'y':
        config = SimulatorConfig.from_dict(default_config)
        success, message = run_test(test_case, config, verbose=True)
        print(f"\nResult: {'PASS' if success else 'FAIL'} - {message}")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Wake Word Detection Test Framework',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/test_wake_detection.py              # Run all tests
  python tests/test_wake_detection.py --id tp_1   # Run specific test
  python tests/test_wake_detection.py --add        # Add new test interactively
  python tests/test_wake_detection.py --verbose    # Verbose output
        """
    )
    parser.add_argument('--id', help='Run specific test case by ID')
    parser.add_argument('--add', action='store_true', help='Add new test case interactively')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose frame-by-frame output')
    parser.add_argument('--test-file', default=None, help='Path to test cases JSON file')
    
    args = parser.parse_args()
    
    # Find test file
    if args.test_file:
        test_file = Path(args.test_file)
    else:
        # Look relative to this script
        script_dir = Path(__file__).parent
        test_file = script_dir / 'wake_word_test_cases.json'
    
    if not test_file.exists():
        print(f"Test file not found: {test_file}")
        sys.exit(1)
    
    if args.add:
        add_test_interactive(test_file)
    else:
        success = run_all_tests(test_file, test_id=args.id, verbose=args.verbose)
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
