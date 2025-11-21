# Chatty Mic
# Finley 2025

import asyncio
import time
import numpy as np
from chatty_async_manager import AsyncManager
import pyaudio
from chatty_config import USER_SAID_WAKE_WORD, USER_STARTED_SPEAKING, ASSISTANT_GO_TO_SLEEP, MASTER_EXIT_EVENT, SAMPLE_RATE_HZ, AUDIO_BLOCKSIZE, PUSH_TO_TALK_START, PUSH_TO_TALK_STOP, ASSISTANT_RESUME_AFTER_AUTO_SUMMARY

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

class WakeWordDetector:
    """Wraps openwakeword model for wake word detection."""
    def __init__(self, master_state):
        self.model = None
        self.wake_to_wake_min_time = 5.0
        self.master_state = master_state

        # Audio characteristics: 80ms frames at 16kHz → 1280 samples per call
        self.sample_rate = 16000
        self.frame_duration_sec = 0.08
        self.frame_samples = int(self.sample_rate * self.frame_duration_sec)  # 1280

        # --- Temporal smoothing / history state
        # 25 frames ≈ 25 * 80ms ≈ 2.0s of score history
        self.score_history = deque(maxlen=25)
        self.vad_history = deque(maxlen=25)

        # trigger_level=4 → ≈ 320ms of sustained high scores
        cfg_trigger_level = master_state.conman.get_config("WAKE_TRIGGER_LEVEL")
        self.trigger_level = cfg_trigger_level if cfg_trigger_level is not None else 4

        # vad_trigger_lookback=10 → ≈ 800ms of "recent voice" required
        cfg_vad_lookback = master_state.conman.get_config("VAD_TRIGGER_LOOKBACK")
        self.vad_trigger_lookback = cfg_vad_lookback if cfg_vad_lookback is not None else 10

        # RMS window: ~0.75s of audio for energy check
        self.rms_window_samples = int(0.75 * self.sample_rate)  # 12000

        base_assistant_name = master_state.conman.get_wake_word_model()
        if OpenWakewordModel and base_assistant_name:
            oww = None
            for extension in ["tflite", "onnx"]:
                try:
                    wake_word_file = "./" + base_assistant_name + "." + extension
                    print("Trying to load OpenWakeWord model: " + wake_word_file)
                    oww = OpenWakewordModel(
                        wakeword_models=[wake_word_file],
                        vad_threshold=master_state.conman.get_config("VAD_THRESHOLD"),
                        inference_framework=extension,
                    )
                    break
                except Exception as e:
                    print(f"OpenWakeWord exception: {e}")
                    pass
            if oww:
                print("✅ OpenWakeWord model loaded")
                self.model = oww
            else:
                print("❌ Failed to load OpenWakeWord model")
                self.model = None

        self.last_wake_word_detected = None

    def calculate_signal_strength(self, audio_samples: np.ndarray) -> float:
        """Calculate RMS (Root Mean Square) amplitude of audio signal."""
        return np.sqrt(np.mean(audio_samples.astype(np.float64) ** 2))

    def on_audio_buffer_in(
        self,
        audio_16ints: np.ndarray,
        vad_only: bool = False
    ) -> tuple[bool, bool]:
        """
        Process audio and return (is_voice, is_wake_word).

        - Always feeds the model (stateful streaming).
        - Uses VAD gating + temporal smoothing to reduce false positives.
        """

        # If we have no model, just estimate voice and never fire wake word
        if self.model is None:
            rms = self.calculate_signal_strength(audio_16ints)
            is_voice = rms > 500.0  # simple fallback heuristic
            return (is_voice, False)

        # --- VAD first (we keep history to use for gating)
        vad_score = self.model.vad.predict(audio_16ints)
        vad_threshold = self.master_state.conman.get_config("VAD_THRESHOLD")
        is_voice = vad_score > vad_threshold

        self.vad_history.append(is_voice)

        # Always feed the wake word model to maintain its internal state
        scores_dict = self.model.predict(audio_16ints)

        if vad_only:
            return (is_voice, False)

        # --- Temporal smoothing of wake-word scores

        # For multiple wakewords, you can swap this to something else (e.g., per-key)
        max_score = max(scores_dict.values()) if scores_dict else 0.0
        self.score_history.append(max_score)

        wake_threshold = self.master_state.conman.get_config("WAKE_WORD_THRESHOLD")

        # Require `trigger_level` consecutive frames above threshold
        recent_scores = list(self.score_history)[-self.trigger_level:]
        has_sustained_high_scores = (
            len(recent_scores) == self.trigger_level
            and all(s >= wake_threshold for s in recent_scores)
        )

        # --- VAD gating for acceptance

        if self.vad_trigger_lookback > 0:
            recent_vad = list(self.vad_history)[-self.vad_trigger_lookback:]
            has_recent_voice = any(recent_vad) if recent_vad else is_voice
        else:
            has_recent_voice = is_voice

        wake_candidate = has_sustained_high_scores and has_recent_voice

        is_wake_word = False

        if wake_candidate:
            # RMS-energy filter + debounce + safe error handling
            try:
                raw_audio_history = np.array(
                    list(self.model.preprocessor.raw_data_buffer)
                ).astype(np.int16)

                if raw_audio_history.size == 0:
                    raise ValueError("raw_data_buffer is empty")

                # Use last ~0.75s of audio or the full buffer if smaller
                if raw_audio_history.shape[0] > self.rms_window_samples:
                    wake_word_audio = raw_audio_history[-self.rms_window_samples:]
                else:
                    wake_word_audio = raw_audio_history

                rms_strength = self.calculate_signal_strength(wake_word_audio)

                min_strength = 1100.0  # still your heuristic; we can tune later

                now = time.time()
                debounce_ok = (
                    self.last_wake_word_detected is None
                    or (now - self.last_wake_word_detected) > self.wake_to_wake_min_time
                )

                if rms_strength >= min_strength and debounce_ok:
                    print(
                        f"🎯 Wake word detected (smoothed): "
                        f"score={max_score:.2f}, RMS={rms_strength:.0f}"
                    )
                    self.master_state.add_log_for_next_summary(
                        f"🎯 Wake word detected (smoothed): "
                        f"score={max_score:.2f}, RMS={rms_strength:.0f}"
                    )
                    print("✅ Wake word accepted")
                    self.last_wake_word_detected = now
                    is_wake_word = True
                    self.model.reset()
                else:
                    if not debounce_ok:
                        print("⏱️ Wake word candidate rejected: within debounce window")
                    else:
                        print(
                            f"🔇 Wake word rejected: insufficient signal strength "
                            f"{rms_strength:.0f} < {min_strength}"
                        )

            except Exception as e:
                msg = (
                    f"⚠️ Error checking signal strength for wake word candidate: {e}. "
                    "Wake word NOT accepted."
                )
                print(msg)
                self.master_state.add_log_for_next_summary(msg)
                # is_wake_word remains False

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

    push_to_talk_active = True

    if wake_detector is None:
        if not manager.master_state.system_type == "mac":
            # if there's no wake detector and we're not testing, fire up
            mic_is_live_to_assistant = True
            user_is_speaking = True
            await manager.event_q.put(USER_SAID_WAKE_WORD)
        else:
            # we are in QA mode on mac, require push to talk start event
            push_to_talk_active = False
            mic_is_live_to_assistant = False
    else:
        #  not testing - we're live... require wake word
        mic_is_live_to_assistant = False
        user_is_speaking = False
        print("💤 Say '"+manager.master_state.conman.get_wake_word_model()+"' to start")

    last_voice_activity_time = None
    should_exit = False
    
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
                        should_exit = True
                        break
                    if event == ASSISTANT_GO_TO_SLEEP:
                        # go to sleep
                        mic_is_live_to_assistant = False
                    elif event == ASSISTANT_RESUME_AFTER_AUTO_SUMMARY:
                        mic_is_live_to_assistant = True

                elif event_type == "input":

                    # handle QA mode keyboard push to talk events
                    if isinstance(event, str):
                        if event==USER_SAID_WAKE_WORD:
                            mic_is_live_to_assistant = True
                            await manager.event_q.put(USER_SAID_WAKE_WORD)
                        else:
                            push_to_talk_active = event == PUSH_TO_TALK_START
                        continue

                    # Convert bytes to numpy array
                    event = np.frombuffer(event, dtype=np.int16)

                    # feed the new audio to the local model.  detect voice always so we can stop sending to the assistant if its just noise.
                    # if we are currently not sending to tjhe assistant, also check for wake word.
                    if wake_detector:
                        is_voice, is_wake_word = wake_detector.on_audio_buffer_in(event, vad_only=mic_is_live_to_assistant)
                    else:
                        is_voice = push_to_talk_active
                        is_wake_word = False

                    if not mic_is_live_to_assistant:
                        if is_wake_word:
                            mic_is_live_to_assistant = True
                            await manager.event_q.put(USER_SAID_WAKE_WORD)

                            # wait past the wake word and flush partial audio
                            await asyncio.sleep(1.0)
                            try:
                                deadman = 100
                                while not manager.input_q.empty() and deadman > 0:
                                    manager.input_q.get_nowait()
                                    deadman -= 1
                            except:
                                print("❌ Error flushing partial audio")
                                pass
                        # we are asleep
                        continue

                    # we are live... debounce voice activity
                    if is_voice:
                        last_voice_activity_time = time.time()
                    elif last_voice_activity_time is not None:
                        if (time.time() - last_voice_activity_time < manager.master_state.conman.get_config("SECONDS_TO_WAIT_FOR_MORE_VOICE")):
                            is_voice = True
                        else:
                            last_voice_activity_time = None

                    if is_voice:
                        await manager.output_q.put(event)
                        if not user_is_speaking:
                            user_is_speaking = True
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


    print("🎤 Microphone MASTER_EXIT_EVENT.")