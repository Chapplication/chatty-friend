# Chatty Mic
# Finley 2025

import asyncio
import sys
import time
import numpy as np
from chatty_async_manager import AsyncManager
import pyaudio
from chatty_config import USER_SAID_WAKE_WORD, USER_STARTED_SPEAKING, ASSISTANT_GO_TO_SLEEP, MASTER_EXIT_EVENT, SAMPLE_RATE_HZ, AUDIO_BLOCKSIZE, ASSISTANT_RESUME_AFTER_AUTO_SUMMARY
from chatty_config import SPEAKER_PLAY_TONE, CHATTY_SONG_NEAR_MISS
from chatty_debug import trace

try:
    from openwakeword.model import Model as OpenWakewordModel
except ImportError:
    OpenWakewordModel = None


#
#  MIC input handling ---------
#

import time
from collections import deque
import numpy as np


class AutoNoiseManager:
    """
    Adaptive noise injection optimized for wake word detection.
    
    Key insight from testing: Real acoustic noise performs better than synthetic
    digital noise for model recognition, likely because training data contains
    natural acoustic noise. Best results at ~30-40 RMS ambient with ~85 injection.
    
    Philosophy:
    - Target a total noise floor of ~120 RMS
    - BUT cap synthetic injection at ~85-90 to avoid over-injecting digital noise
    - In quiet rooms: accept slightly lower floor rather than excessive synthetic noise
    - In rooms with natural ambient noise: inject less (natural noise helps!)
    """
    
    def __init__(self, target_floor=120.0, max_injection=85.0):
        """
        Args:
            target_floor: Desired minimum total noise floor RMS.
            max_injection: Maximum synthetic noise to inject. Capped because
                          synthetic noise doesn't match training data as well
                          as real acoustic noise. Default 85 based on testing
                          showing optimal performance at this injection level.
        """
        self.target_floor = target_floor
        self.max_injection = max_injection
        
        # Transient rejection: ignore "quiet" frames with RMS above this
        # (catches door slams, music bursts with low VAD)
        self.max_ambient_rms = target_floor * 2  # 240 by default
        
        # State - exponential moving average for smooth ambient tracking
        self.ambient_ema = None
        self.alpha = 0.08  # Smoothing factor (slightly faster adaptation)
        self.frame_count = 0
        self.warmup_frames = 25  # ~2 seconds
        self.is_warmed_up = False
        self.current_noise_level = 0
    
    def update(self, rms, vad_score):
        """
        Update with new frame, return noise level to inject.
        
        Key insight: Only track ambient during quiet periods (low VAD).
        This prevents speech from corrupting our ambient estimate.
        """
        self.frame_count += 1
        
        # Only update ambient estimate during quiet periods
        # AND reject transient loud sounds (low VAD but high RMS = door slam, etc.)
        if vad_score < 0.15 and rms < self.max_ambient_rms:
            if self.ambient_ema is None:
                self.ambient_ema = rms
            else:
                self.ambient_ema = self.alpha * rms + (1 - self.alpha) * self.ambient_ema
        
        # Warmup period - gather initial ambient estimate
        if not self.is_warmed_up:
            if self.frame_count >= self.warmup_frames and self.ambient_ema is not None:
                self.is_warmed_up = True
            return 0  # No injection during warmup
        
        # Calculate injection: bring floor UP to target, but cap synthetic noise
        # Key: don't over-inject synthetic noise in quiet rooms - it hurts performance
        if self.ambient_ema is not None:
            gap = self.target_floor - self.ambient_ema
            # Cap at max_injection to avoid excessive synthetic noise
            self.current_noise_level = min(max(0, gap), self.max_injection)
        
        return self.current_noise_level
    
    def get_stats(self):
        """Return current statistics for display."""
        return {
            'noise_level': self.current_noise_level,
            'ambient_rms': self.ambient_ema or 0,
            'target_floor': self.target_floor,
            'max_injection': self.max_injection,
            'warmed_up': self.is_warmed_up,
        }


class WakeWordDetector:
    """Wraps openwakeword model for wake word detection with cluster-based detection and auto-noise."""
    def __init__(self, master_state):
        self.model = None
        self.master_state = master_state
        cfg = master_state.conman

        # Audio characteristics: 80ms frames at 16kHz -> 1280 samples per call
        self.sample_rate = 16000
        self.frame_duration_sec = 0.08
        self.frame_samples = int(self.sample_rate * self.frame_duration_sec)  # 1280

        # --- VAD history for is_voice detection
        # Store actual VAD scores (not just booleans) for max_vad lookback
        self.vad_history = deque(maxlen=25)
        self.vad_score_history = deque(maxlen=25)  # Track actual scores for peak detection

        # --- Activity logging state (rate-limited to once per second)
        self.activity_log_interval = 1.0  # seconds between activity logs
        self.last_vad_log_time = 0

        # --- Cluster-based detection state
        self.tracking = False
        self.tracking_scores = []
        self.tracking_vad_scores = []  # Track VAD during detection for gating
        self.tracking_start_time = 0.0
        self.cooldown_remaining = 0

        # --- Detection thresholds from config
        self.entry_threshold = cfg.get_config("WAKE_ENTRY_THRESHOLD") or 0.35
        self.confirm_peak = cfg.get_config("WAKE_CONFIRM_PEAK") or 0.45
        self.confirm_cumulative = cfg.get_config("WAKE_CONFIRM_CUMULATIVE") or 1.2
        self.min_frames_above_entry = int(cfg.get_config("WAKE_MIN_FRAMES_ABOVE_ENTRY") or 2)
        self.cooldown_frames = int(cfg.get_config("WAKE_COOLDOWN_FRAMES") or 5)
        
        # --- Near-miss chirp feedback
        self.near_miss_peak_ratio = float(cfg.get_config("NEAR_MISS_PEAK_RATIO") or 0.80)
        self.near_miss_cooldown_seconds = float(cfg.get_config("NEAR_MISS_COOLDOWN_SECONDS") or 5.0)
        self.last_near_miss_time = 0
        self.near_miss_chirp = False  # Flag consumed by mic_listener to emit tone
        
        # --- Continuous speech rejection thresholds
        # When wake word is detected in the middle of ongoing speech (not isolated utterance),
        # it's contextually unlikely to be intentional - real wake words are typically spoken
        # after a pause, not mid-conversation. Require very high confidence to override context.
        self.continuous_speech_max_ms = float(cfg.get_config("WAKE_CONTINUOUS_SPEECH_MAX_MS") or 1500.0)
        self.continuous_speech_peak = float(cfg.get_config("WAKE_CONTINUOUS_SPEECH_PEAK") or 0.88)
        
        # --- Stale voice rejection: sub-threshold overlap check
        # When voice is only detected in lookback history (not during tracking),
        # check for temporal co-occurrence of VAD and wake signals. In a real wake word,
        # the decaying voice tail overlaps with the rising wake score. No overlap = stale voice.
        self.overlap_vad_min = float(cfg.get_config("WAKE_OVERLAP_VAD_MIN") or 0.18)
        self.overlap_wake_min = float(cfg.get_config("WAKE_OVERLAP_WAKE_MIN") or 0.05)
        self.overlap_lookback_frames = int(cfg.get_config("WAKE_OVERLAP_LOOKBACK_FRAMES") or 8)

        # --- Platform-specific detection mode
        # On macOS, VAD and wake word model have timing desync (~300-500ms latency difference)
        # that causes STALE_VOICE and WEAK_VOICE checks to fail on legitimate wake words.
        # Use simplified detection on Mac: trust high peak scores with voice-in-history only.
        self.is_macos = sys.platform == 'darwin'

        # --- Auto-noise manager
        noise_target = cfg.get_config("NOISE_TARGET_FLOOR") or 120.0
        noise_max = cfg.get_config("NOISE_MAX_INJECTION") or 85.0
        self.noise_manager = AutoNoiseManager(
            target_floor=noise_target,
            max_injection=noise_max
        )

        # --- Load wake word model
        base_assistant_name = master_state.conman.get_wake_word_model()
        if OpenWakewordModel and base_assistant_name:
            oww = None
            for extension in ["tflite", "onnx"]:
                try:
                    wake_word_file = "./" + base_assistant_name + "." + extension
                    print("Trying to load OpenWakeWord model: " + wake_word_file)
                    oww = OpenWakewordModel(
                        wakeword_models=[wake_word_file],
                        vad_threshold=cfg.get_config("VAD_THRESHOLD"),
                        inference_framework=extension,
                    )
                    break
                except Exception as e:
                    print(f"OpenWakeWord exception: {e}")
                    self.master_state.add_log_for_next_summary(f"OpenWakeWord exception loading {wake_word_file}: {e}")
                    pass
            if oww:
                detection_mode = "macOS (simplified)" if self.is_macos else "Linux/Pi (full VAD gating)"
                print(f"OpenWakeWord model loaded - detection mode: {detection_mode}")
                self.master_state.add_log_for_next_summary(f"Wake word model loaded: {wake_word_file} ({detection_mode})")
                trace("wake", f"model loaded: {wake_word_file}, mode: {detection_mode}")
                self.model = oww
            else:
                print("Failed to load OpenWakeWord model")
                self.master_state.add_log_for_next_summary("Wake word model failed to load; mic will fall back to always-on")
                trace("wake", "model failed to load - falling back to always-on")
                self.model = None
        else:
            self.master_state.add_log_for_next_summary("OpenWakeWord not available; mic will fall back to always-on")
            trace("wake", "OpenWakeWord not available")

        self.last_wake_word_detected = None
        # Use monotonic time for better reliability in debounce checks
        self._monotonic_time = time.monotonic if hasattr(time, 'monotonic') else time.time

        # Periodic heartbeat logging for debugging (every 5 seconds)
        self.heartbeat_interval = 5.0
        self.last_heartbeat_time = 0
        self.frames_since_heartbeat = 0
        self.max_score_since_heartbeat = 0.0
        self.max_vad_since_heartbeat = 0.0
        self.max_rms_since_heartbeat = 0.0
        self.max_noise_since_heartbeat = 0.0

        # --- Instrumentation ring buffer for wake word analysis
        # Captures ~5 seconds of history (62 frames at 80ms each)
        # Dumped to log on wake word detection to help diagnose false positives
        self.history_buffer_size = 62  # ~5 seconds
        self.frame_history = deque(maxlen=self.history_buffer_size)

        # Log config values at startup
        self._log_startup_config()

    def _log_startup_config(self):
        """Log all wake word detection config values at startup."""
        cfg = self.master_state.conman
        noise_stats = self.noise_manager.get_stats()
        config_info = (
            f"Wake detector config: "
            f"vad_thresh={cfg.get_config('VAD_THRESHOLD')}, "
            f"entry={self.entry_threshold}, "
            f"confirm_peak={self.confirm_peak}, "
            f"confirm_cumul={self.confirm_cumulative}, "
            f"min_frames={self.min_frames_above_entry}, "
            f"cooldown={self.cooldown_frames}, "
            f"noise_floor={noise_stats['target_floor']}, "
            f"noise_max={noise_stats['max_injection']}, "
            f"cont_speech_max={self.continuous_speech_max_ms}ms, "
            f"cont_speech_peak={self.continuous_speech_peak}, "
            f"near_miss_ratio={self.near_miss_peak_ratio}, "
            f"near_miss_cooldown={self.near_miss_cooldown_seconds}s"
        )
        print(config_info)
        trace("wake", config_info)
        self.master_state.add_log_for_next_summary(f"Wake detector: {config_info}")

    def _record_frame(self, vad_score: float, wake_score: float, rms: float, 
                      noise_level: float, is_tracking: bool):
        """Record a frame's data to the history buffer for later analysis."""
        self.frame_history.append({
            't': time.time(),
            'vad': vad_score,
            'wake': wake_score,
            'rms': rms,
            'noise': noise_level,
            'tracking': is_tracking,
        })

    def _dump_detection_history(self, detection_reason: str, num_frames: int, 
                                 duration_ms: float, scores: list):
        """
        Dump the frame history to logs when wake word is detected.
        This helps analyze false positives by showing context before detection.
        """
        if not self.frame_history:
            return
        
        history = list(self.frame_history)
        
        # Calculate derived metrics for analysis
        vad_scores = [f['vad'] for f in history]
        wake_scores = [f['wake'] for f in history]
        rms_values = [f['rms'] for f in history]
        
        # Find silence gaps (low VAD periods) in the history
        vad_threshold = self.master_state.conman.get_config("VAD_THRESHOLD") or 0.3
        silence_frames = sum(1 for v in vad_scores if v < vad_threshold)
        voice_frames = len(vad_scores) - silence_frames
        
        # Check for pre-detection silence (was there quiet before tracking started?)
        # Look at the last 20 frames (~1.6s) before detection
        recent_frames = history[-20:] if len(history) >= 20 else history
        pre_silence_count = 0
        for i, f in enumerate(recent_frames):
            if f['tracking']:
                # Count silence frames before tracking started
                pre_silence_count = sum(1 for ff in recent_frames[:i] if ff['vad'] < vad_threshold)
                break
        
        # Find continuous speech duration before detection
        continuous_voice_before = 0
        for f in reversed(history[:-num_frames] if num_frames < len(history) else []):
            if f['vad'] >= vad_threshold:
                continuous_voice_before += 1
            else:
                break
        continuous_voice_ms = continuous_voice_before * 80  # 80ms per frame
        
        # Build summary line
        summary = (
            f"WAKE HISTORY: {detection_reason} | "
            f"duration={duration_ms:.0f}ms | "
            f"history={len(history)} frames (~{len(history)*80/1000:.1f}s) | "
            f"voice={voice_frames}/{len(history)} frames | "
            f"pre_silence={pre_silence_count} frames | "
            f"continuous_voice_before={continuous_voice_ms}ms"
        )
        trace("wake", summary)
        
        # Dump detailed per-frame data (compact format)
        # Format: relative_time, vad, wake, rms, tracking_flag
        # Group into lines of ~10 frames for readability
        base_time = history[0]['t']
        frame_data = []
        for f in history:
            rel_t = (f['t'] - base_time) * 1000  # ms since start
            tracking_flag = "T" if f['tracking'] else "."
            # Compact format: time|vad|wake|rms|flag
            frame_data.append(f"{rel_t:5.0f}|{f['vad']:.2f}|{f['wake']:.3f}|{f['rms']:5.0f}|{tracking_flag}")
        
        # Log in chunks of 10 frames per line
        chunk_size = 10
        for i in range(0, len(frame_data), chunk_size):
            chunk = frame_data[i:i+chunk_size]
            frame_nums = f"[{i:2d}-{min(i+chunk_size-1, len(frame_data)-1):2d}]"
            trace("wake", f"  {frame_nums} " + "  ".join(chunk))
        
        # Log the actual detection scores
        trace("wake", f"  DETECTION SCORES: [{','.join(f'{s:.3f}' for s in scores)}]")

    def calculate_signal_strength(self, audio_samples: np.ndarray) -> float:
        """Calculate RMS (Root Mean Square) amplitude of audio signal."""
        return np.sqrt(np.mean(audio_samples.astype(np.float64) ** 2))
    
    def detect_audio_quality_issues(self, audio_samples: np.ndarray) -> tuple[bool, str]:
        """
        Lightweight audio quality detection optimized for Raspberry Pi.
        Runs infrequently (every 5 seconds) to minimize CPU impact.
        Returns: (has_issues, issue_description)
        """
        issues = []
        
        # Fast checks first (avoid expensive operations if possible)
        max_val = np.max(np.abs(audio_samples))
        
        # Check for clipping (samples at max/min values) - fast check
        clipping_threshold = 32000  # Close to int16 max (32767)
        if max_val > clipping_threshold:
            # Only count clipped samples if we detected high values
            clipped_count = np.sum(np.abs(audio_samples) > clipping_threshold)
            clipping_percent = clipped_count / len(audio_samples) * 100
            if clipping_percent > 1.0:  # More than 1% clipped
                issues.append(f"clipping ({clipping_percent:.1f}%)")
        
        # Use fast energy estimate (mean abs) instead of full RMS for initial check
        energy = np.mean(np.abs(audio_samples.astype(np.int32)))
        
        # Check for very low signal or silence
        if energy < 10.0:
            issues.append("silence")
        elif energy < 100.0:
            issues.append("very low signal")
        
        # Only do expensive distortion check if we have significant signal
        if energy > 1000.0 and len(audio_samples) > 100:
            # Simplified distortion check: high max relative to mean
            # Avoids expensive variance calculation
            if max_val > energy * 20:  # Very high peaks relative to average
                issues.append("potential distortion")
        
        if issues:
            return True, ", ".join(issues)
        return False, ""

    def _evaluate_cluster_detection(self, max_score: float, vad_score: float, vad_threshold: float) -> bool:
        """
        Cluster-based wake word detection with cumulative scoring and VAD gating.
        
        Returns True if wake word is detected, False otherwise.
        """
        # Handle cooldown
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
            return False
        
        above_entry = max_score >= self.entry_threshold
        is_voice = vad_score > vad_threshold
        
        if self.tracking:
            # We're tracking a potential wake word
            self.tracking_scores.append(max_score)
            self.tracking_vad_scores.append(vad_score)
            
            # Log each frame while tracking for debugging
            trace("wake", f"tracking: frame={len(self.tracking_scores)}, score={max_score:.3f}, vad={vad_score:.2f}, above_entry={above_entry}")
            
            if not above_entry:
                # Score dropped below entry - evaluate the cluster
                peak_score = max(self.tracking_scores)
                cumulative_score = sum(self.tracking_scores)
                frames_above = sum(1 for s in self.tracking_scores if s >= self.entry_threshold)
                
                # VAD gating: check for voice DURING tracking OR in recent history
                # Wake word model has ~200-300ms latency, so voice may have been
                # detected before the wake score spiked
                voice_frames_tracking = sum(1 for v in self.tracking_vad_scores if v > vad_threshold)
                
                # Check VAD history (lookback ~10 frames = 800ms before tracking)
                vad_lookback = 10
                recent_vad = list(self.vad_history)[-vad_lookback:] if self.vad_history else []
                voice_frames_history = sum(1 for v in recent_vad if v)  # vad_history stores booleans
                
                has_voice = voice_frames_tracking > 0 or voice_frames_history > 0
                max_vad_tracking = max(self.tracking_vad_scores) if self.tracking_vad_scores else 0
                
                # Get max VAD from history window (BEFORE tracking started)
                # This is critical: wake word model has ~200-400ms latency, so by the time
                # the wake score spikes, the actual voice has often already passed
                recent_vad_scores = list(self.vad_score_history)[-vad_lookback:] if self.vad_score_history else []
                max_vad_history = max(recent_vad_scores) if recent_vad_scores else 0
                
                # Use the MAXIMUM of tracking VAD and recent history VAD
                # This accounts for wake word model latency where voice precedes wake score
                max_vad_combined = max(max_vad_tracking, max_vad_history)
                
                # Require VAD to peak significantly above threshold (in tracking OR recent history)
                # This filters out background speech that happens to coincide with a wake score spike
                vad_peak_required = min(vad_threshold + 0.3, 1.0)
                has_strong_voice = max_vad_combined >= vad_peak_required
                
                wake_detected = False
                detection_reason = ""
                rejection_reason = ""
                
                # Build voice source info for logging
                voice_source = []
                if voice_frames_tracking > 0:
                    voice_source.append(f"tracking:{voice_frames_tracking}")
                if voice_frames_history > 0:
                    voice_source.append(f"history:{voice_frames_history}/{vad_lookback}")
                voice_info = "+".join(voice_source) if voice_source else "none"
                
                # Calculate continuous voice duration before tracking started
                # This detects if wake word appeared in middle of ongoing conversation
                history = list(self.frame_history)
                num_tracking_frames = len(self.tracking_scores)
                continuous_voice_before_ms = 0
                if len(history) > num_tracking_frames:
                    # Count consecutive voice frames before tracking started
                    pre_tracking_history = history[:-num_tracking_frames] if num_tracking_frames > 0 else history
                    continuous_voice_frames = 0
                    for f in reversed(pre_tracking_history):
                        if f['vad'] >= vad_threshold:
                            continuous_voice_frames += 1
                        else:
                            break
                    continuous_voice_before_ms = continuous_voice_frames * 80  # 80ms per frame
                
                # Determine required peak based on speech context
                # If wake word appears mid-conversation, require higher confidence
                in_continuous_speech = continuous_voice_before_ms > self.continuous_speech_max_ms
                required_peak = self.continuous_speech_peak if in_continuous_speech else self.confirm_peak
                
                # Check for sub-threshold overlap between VAD and wake signals.
                # In a real wake word, the decaying voice tail overlaps with the rising
                # wake score (due to ~200-400ms model latency). If there's zero overlap,
                # voice and wake are temporally disjoint = stale/unrelated voice.
                has_overlap = False
                if voice_frames_tracking == 0:
                    overlap_start = max(0, len(history) - num_tracking_frames - self.overlap_lookback_frames)
                    overlap_window = history[overlap_start:]
                    for f in overlap_window:
                        if f['vad'] >= self.overlap_vad_min and f['wake'] >= self.overlap_wake_min:
                            has_overlap = True
                            break
                else:
                    # Voice during tracking = direct temporal overlap
                    has_overlap = True
                
                if not has_voice:
                    # No voice activity in tracking or recent history - reject as noise spike
                    rejection_reason = f"NO_VOICE (peak={peak_score:.3f}, max_vad={max_vad_tracking:.2f}<{vad_threshold}, history_voice={voice_frames_history}/{vad_lookback})"
                elif not self.is_macos and not has_strong_voice:
                    # Voice present but never peaked high enough - likely background speech not directed at device
                    # Skip on macOS: VAD timing desync causes false rejections with legitimate wake words
                    rejection_reason = f"WEAK_VOICE (peak={peak_score:.3f}, max_vad_tracking={max_vad_tracking:.2f}, max_vad_history={max_vad_history:.2f}, combined={max_vad_combined:.2f}<{vad_peak_required:.2f})"
                elif not self.is_macos and voice_frames_tracking == 0 and not has_overlap:
                    # Voice only in history with no sub-threshold overlap between VAD and wake signals.
                    # The voice and wake events are temporally disjoint - the voice was unrelated.
                    # Skip on macOS: VAD and wake model have ~300-500ms timing offset causing false rejections
                    rejection_reason = f"STALE_VOICE (peak={peak_score:.3f}, no overlap vad>={self.overlap_vad_min}&wake>={self.overlap_wake_min}, voice only in history={voice_info})"
                elif in_continuous_speech and peak_score < self.continuous_speech_peak:
                    # Wake word detected in middle of ongoing speech - require higher peak to confirm
                    # This reduces false positives from conversational speech
                    rejection_reason = f"CONTINUOUS_SPEECH (peak={peak_score:.3f}<{self.continuous_speech_peak:.2f}, continuous_voice={continuous_voice_before_ms:.0f}ms>{self.continuous_speech_max_ms:.0f}ms)"
                elif peak_score >= required_peak and frames_above > 1:
                    # Traditional peak-based detection (with voice present)
                    wake_detected = True
                    detection_reason = f"peak={peak_score:.3f}, voice={voice_info}"
                    if in_continuous_speech:
                        detection_reason += f", continuous={continuous_voice_before_ms:.0f}ms"
                elif cumulative_score >= self.confirm_cumulative and frames_above >= self.min_frames_above_entry:
                    # Cumulative score detection (catches sustained moderate scores)
                    # Also apply continuous speech check for cumulative detection
                    if in_continuous_speech:
                        rejection_reason = f"CONTINUOUS_SPEECH (cumul={cumulative_score:.2f}, peak={peak_score:.3f}<{self.continuous_speech_peak:.2f}, continuous_voice={continuous_voice_before_ms:.0f}ms)"
                    else:
                        wake_detected = True
                        detection_reason = f"cumul={cumulative_score:.2f}, frames={frames_above}, voice={voice_info}"
                else:
                    # Cluster rejected - build rejection reason for debugging
                    rejection_reason = f"peak={peak_score:.3f}<{required_peak}, cumul={cumulative_score:.2f}<{self.confirm_cumulative}, frames={frames_above}, voice={voice_info}"
                    
                    # Near-miss chirp: cluster passed all voice quality gates but
                    # missed on score. If scores were close, chirp to let the user
                    # know they almost triggered the wake word.
                    near_miss_peak_thr = self.confirm_peak * self.near_miss_peak_ratio
                    near_miss_cumul_thr = self.confirm_cumulative * self.near_miss_peak_ratio
                    now_mono = self._monotonic_time()
                    if (frames_above >= 2
                            and (peak_score >= near_miss_peak_thr or cumulative_score >= near_miss_cumul_thr)
                            and (now_mono - self.last_near_miss_time) >= self.near_miss_cooldown_seconds):
                        self.near_miss_chirp = True
                        self.last_near_miss_time = now_mono
                        trace("wake", f"NEAR_MISS chirp - peak={peak_score:.3f}(thr={near_miss_peak_thr:.3f}), cumul={cumulative_score:.2f}(thr={near_miss_cumul_thr:.2f}), frames={frames_above}, voice={voice_info}")
                
                # Reset tracking state (save scores before clearing)
                tracking_duration_ms = (time.time() - self.tracking_start_time) * 1000
                num_frames = len(self.tracking_scores)
                detection_scores = list(self.tracking_scores)  # Copy for history dump
                scores_str = ",".join(f"{s:.2f}" for s in self.tracking_scores[-10:])  # Last 10 scores
                vad_str = ",".join(f"{v:.2f}" for v in self.tracking_vad_scores[-10:])  # Last 10 VAD scores
                self.tracking = False
                self.tracking_scores = []
                self.tracking_vad_scores = []
                
                if wake_detected:
                    self.cooldown_remaining = self.cooldown_frames
                    self.last_wake_word_detected = self._monotonic_time()
                    self.model.reset()
                    
                    print(f"Wake word DETECTED: {detection_reason} ({num_frames} frames, {tracking_duration_ms:.0f}ms)")
                    self.master_state.add_log_for_next_summary(
                        f"Wake word detected: {detection_reason} ({num_frames} frames)"
                    )
                    trace("wake", f"DETECTED - {detection_reason} ({num_frames} frames, {tracking_duration_ms:.0f}ms, scores=[{scores_str}], vad=[{vad_str}])")
                    
                    # Dump full history buffer to help analyze false positives
                    self._dump_detection_history(detection_reason, num_frames, tracking_duration_ms, detection_scores)
                    
                    return True
                else:
                    # Log rejected clusters to help debug false positives and missed detections
                    trace("wake", f"REJECTED - {rejection_reason} ({num_frames} frames, {tracking_duration_ms:.0f}ms, scores=[{scores_str}], vad=[{vad_str}])")
        else:
            # Not currently tracking
            if above_entry:
                # Start tracking - log this event
                self.tracking = True
                self.tracking_scores = [max_score]
                self.tracking_vad_scores = [vad_score]
                self.tracking_start_time = time.time()
                trace("wake", f"TRACKING START - initial_score={max_score:.3f}, vad={vad_score:.2f}, entry_threshold={self.entry_threshold}")
        
        return False

    def on_audio_buffer_in(
        self,
        audio_16ints: np.ndarray,
        vad_only: bool = False
    ) -> tuple[bool, bool]:
        """
        Process audio and return (is_voice, is_wake_word).

        Uses cluster-based detection with auto-noise injection for improved
        wake word recognition in quiet environments.
        """

        # If we have no model, just estimate voice and never fire wake word
        if self.model is None:
            rms = self.calculate_signal_strength(audio_16ints)
            is_voice = rms > 500.0  # simple fallback heuristic
            return (is_voice, False)

        # --- 1. Get VAD score on raw audio first (before noise injection)
        vad_score = self.model.vad.predict(audio_16ints)
        vad_threshold = self.master_state.conman.get_config("VAD_THRESHOLD")
        is_voice = vad_score > vad_threshold
        self.vad_history.append(is_voice)
        self.vad_score_history.append(vad_score)  # Track actual score for peak detection

        # --- 2. Calculate raw RMS (for auto-noise tracking)
        raw_rms = self.calculate_signal_strength(audio_16ints)

        # --- 3. Update noise manager, get injection level
        noise_level = self.noise_manager.update(raw_rms, vad_score)

        # --- 4. Inject noise if needed
        if noise_level > 0:
            noise = np.random.randn(len(audio_16ints)) * noise_level
            audio_16ints = np.clip(
                audio_16ints.astype(np.float64) + noise,
                -32768, 32767
            ).astype(np.int16)

        now = time.time()

        # Track stats for heartbeat
        self.frames_since_heartbeat += 1
        if vad_score > self.max_vad_since_heartbeat:
            self.max_vad_since_heartbeat = vad_score
        if raw_rms > self.max_rms_since_heartbeat:
            self.max_rms_since_heartbeat = raw_rms
        if noise_level > self.max_noise_since_heartbeat:
            self.max_noise_since_heartbeat = noise_level

        # Return now if we're just filtering for voice (vs. listening for wakeword)
        if vad_only:
            return (is_voice, False)

        # --- 5. Run wake word prediction on noise-augmented audio
        scores_dict = self.model.predict(audio_16ints)
        max_score = max(scores_dict.values()) if scores_dict else 0.0

        # Track max wake score for heartbeat
        if max_score > self.max_score_since_heartbeat:
            self.max_score_since_heartbeat = max_score

        # --- 6. Record frame to history buffer for detection analysis
        self._record_frame(vad_score, max_score, raw_rms, noise_level, self.tracking)

        # Periodic heartbeat logging - shows we're alive even when nothing is happening
        if (now - self.last_heartbeat_time) >= self.heartbeat_interval:
            noise_stats = self.noise_manager.get_stats()
            trace("wake", 
                f"heartbeat: frames={self.frames_since_heartbeat}, "
                f"max_score={self.max_score_since_heartbeat:.3f}, "
                f"max_vad={self.max_vad_since_heartbeat:.3f}, "
                f"max_rms={self.max_rms_since_heartbeat:.0f}, "
                f"noise={self.max_noise_since_heartbeat:.0f}, "
                f"ambient={noise_stats['ambient_rms']:.0f}, "
                f"entry={self.entry_threshold}"
            )
            # Reset heartbeat stats
            self.last_heartbeat_time = now
            self.frames_since_heartbeat = 0
            self.max_score_since_heartbeat = 0.0
            self.max_vad_since_heartbeat = 0.0
            self.max_rms_since_heartbeat = 0.0
            self.max_noise_since_heartbeat = 0.0

        # Log activity when audio detected (rate-limited to 1/sec)
        # Note: VAD detects ANY audio activity (music, noise), not just speech
        # Wake score detects the specific wake word pattern
        near_threshold = self.entry_threshold * 0.7  # 70% of entry = "near" activation
        if (now - self.last_vad_log_time) >= self.activity_log_interval:
            if max_score >= near_threshold or is_voice:
                self.last_vad_log_time = now
                tracking_info = f", TRACKING({len(self.tracking_scores)})" if self.tracking else ""
                # Explain: vad=audio_activity, wake=wake_word_score
                trace("wake", 
                    f"audio: vad={vad_score:.3f}(thr={vad_threshold}), "
                    f"wake={max_score:.3f}(thr={self.entry_threshold}), "
                    f"rms={raw_rms:.0f}, noise_inj={noise_level:.0f}{tracking_info}"
                )

        # --- 7. Cluster-based detection with VAD gating
        self.near_miss_chirp = False  # Reset before evaluation; set by _evaluate if near miss
        is_wake_word = self._evaluate_cluster_detection(max_score, vad_score, vad_threshold)

        return (is_voice, is_wake_word)


async def mic_listener(manager: AsyncManager) -> None:
    """
    Capture raw mic.  when listening, send to assistant.  when not listening, send to wake word detector.
    """

    loop = asyncio.get_running_loop()
    def _mic_input_callback(in_data, frame_count, time_info, status):
        # PyAudio calling back with audio. Just add to the mic listener queue
        try:
            loop.call_soon_threadsafe(manager.input_q.put_nowait, in_data)
        except Exception as e:
            print(f"Mic callback error: {e}")
        
        # Return None to continue streaming
        return (None, pyaudio.paContinue)

    wake_detector = None
    if manager.master_state.conman.get_config("WAKE_WORD_MODEL"):
        wake_detector = WakeWordDetector(manager.master_state)
        if not wake_detector.model:
            wake_detector = None

    if wake_detector is None:
        # No wake detector available - go to always-on mode
        mic_is_live_to_assistant = True
        user_is_speaking = True
        await manager.event_q.put(USER_SAID_WAKE_WORD)
        manager.master_state.add_log_for_next_summary("⚠️ Wake detection unavailable; mic started in always-on mode")
    else:
        # Wake detector ready - wait for wake word
        mic_is_live_to_assistant = False
        user_is_speaking = False
        print("💤 Say '"+manager.master_state.conman.get_wake_word_model()+"' to start")

    last_voice_activity_time = None
    should_exit = False
    
    # Local VAD gating - only stream when voice detected (saves bandwidth/API costs)
    local_vad_gate_enabled = manager.master_state.conman.get_config("LOCAL_VAD_GATE")
    preroll_frame_count = int(manager.master_state.conman.get_config("LOCAL_VAD_PREROLL_FRAMES") or 5)
    preroll_buffer = deque(maxlen=preroll_frame_count)  # Circular buffer for speech onset capture
    was_voice_active = False  # Track voice state transitions for pre-roll flush
    
    if local_vad_gate_enabled:
        trace("mic", f"Local VAD gating enabled with {preroll_frame_count} frame pre-roll buffer")
    
    # Open the stream
    stream = manager.master_state.pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=SAMPLE_RATE_HZ,
        input=True,
        frames_per_buffer=AUDIO_BLOCKSIZE,
        stream_callback=_mic_input_callback
    )

    # Start the stream
    stream.start_stream()

    # On macOS, print the active mic device for local dev visibility
    import platform
    if platform.system().lower() == 'darwin':
        try:
            dev_info = manager.master_state.pa.get_default_input_device_info()
            dev_name = dev_info.get('name', 'unknown')
            dev_rate = int(dev_info.get('defaultSampleRate', 0))
            dev_channels = dev_info.get('maxInputChannels', 0)
            print(f"🎤 Mic: {dev_name} ({dev_rate}Hz, {dev_channels}ch)")
        except Exception:
            pass

    trace("mic", "stream opened")

    try:
        while not should_exit:

            # see if there is any mic input or a command to exit
            events = await manager.wait_and_dispatch()

            if not events:
                # timed out...
                continue

            for event_type, event in events:

                if event_type == "command":
                    if event == MASTER_EXIT_EVENT:
                        trace("mic", "received exit command")
                        should_exit = True
                        break
                    if event == ASSISTANT_GO_TO_SLEEP:
                        # go to sleep
                        trace("mic", "going to sleep - listening for wake word")
                        mic_is_live_to_assistant = False
                        preroll_buffer.clear()  # Clear pre-roll to avoid stale audio
                        was_voice_active = False
                    elif event == ASSISTANT_RESUME_AFTER_AUTO_SUMMARY:
                        trace("mic", "resuming after auto-summary")
                        mic_is_live_to_assistant = True
                        preroll_buffer.clear()  # Fresh start after summary
                        was_voice_active = False

                elif event_type == "input":

                    # Convert bytes to numpy array
                    event = np.frombuffer(event, dtype=np.int16)

                    # feed the new audio to the local model.  detect voice always so we can stop sending to the assistant if its just noise.
                    # if we are currently not sending to the assistant, also check for wake word.
                    if wake_detector:
                        is_voice, is_wake_word = wake_detector.on_audio_buffer_in(event, vad_only=mic_is_live_to_assistant)
                    else:
                        # No wake detector - always-on mode, always consider voice active
                        is_voice = True
                        is_wake_word = False

                    if not mic_is_live_to_assistant:
                        if is_wake_word:
                            mic_is_live_to_assistant = True
                            await manager.event_q.put(USER_SAID_WAKE_WORD)

                            # wait past the wake word and flush partial audio from input AND output queues
                            await asyncio.sleep(1.0)
                            try:
                                deadman = 100
                                while not manager.input_q.empty() and deadman > 0:
                                    manager.input_q.get_nowait()
                                    deadman -= 1
                                # Also flush output queue to prevent stale audio reaching assistant
                                deadman = 100
                                while not manager.output_q.empty() and deadman > 0:
                                    manager.output_q.get_nowait()
                                    deadman -= 1
                            except:
                                print("❌ Error flushing partial audio")
                                pass
                        elif wake_detector and wake_detector.near_miss_chirp:
                            # Near miss - play a subtle chirp so user knows they're close
                            wake_detector.near_miss_chirp = False
                            try:
                                manager.master_state.task_managers["speaker"].command_q.put_nowait(
                                    SPEAKER_PLAY_TONE + ":" + CHATTY_SONG_NEAR_MISS
                                )
                            except Exception:
                                pass
                        # we are asleep
                        continue

                    # we are live... debounce voice activity for UI events only
                    if is_voice:
                        last_voice_activity_time = time.time()
                    elif last_voice_activity_time is not None:
                        if (time.time() - last_voice_activity_time < manager.master_state.conman.get_config("SECONDS_TO_WAIT_FOR_MORE_VOICE")):
                            is_voice = True
                        else:
                            last_voice_activity_time = None

                    # Local VAD gating: only send audio when voice is detected
                    # This saves bandwidth and API costs by not streaming silence/noise
                    if local_vad_gate_enabled:
                        if is_voice:
                            # Voice detected - check if this is a new voice onset
                            if not was_voice_active:
                                # Flush pre-roll buffer to capture speech onset
                                for preroll_frame in preroll_buffer:
                                    await manager.output_q.put(preroll_frame)
                                preroll_buffer.clear()
                                was_voice_active = True
                                trace("mic", f"Voice onset - flushed {preroll_frame_count} pre-roll frames")
                            # Send current frame
                            await manager.output_q.put(event)
                        else:
                            # No voice - just buffer for potential pre-roll
                            preroll_buffer.append(event)
                            was_voice_active = False
                    else:
                        # VAD gating disabled - always send audio (original behavior)
                        await manager.output_q.put(event)

                    # Track speaking state for UI/interruption events
                    # When using wake word detection (server VAD mode), disable local interruption
                    # because server VAD handles turn detection and local VAD causes false interrupts
                    if is_voice:
                        if not user_is_speaking:
                            user_is_speaking = True
                            # Only send USER_STARTED_SPEAKING if NOT using wake word detection
                            # With wake word, server VAD handles turns; local VAD causes false interrupts
                            if wake_detector is None:
                                print("🔄 USER_STARTED_SPEAKING")
                                await manager.event_q.put(USER_STARTED_SPEAKING)
                    else:
                        user_is_speaking = False

                    
    except asyncio.CancelledError:
        print("\n⏹️  Mic stream closed.")
        should_exit = True

    except Exception as e:
        print(f"\nError in mic_listener: {e}")

    stream.stop_stream()
    stream.close()
    trace("mic", "stream closed")

    print("🎤 Microphone MASTER_EXIT_EVENT.")
