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

class WakeWordDetector:
    """  Wraps openwakeword model for wake word detection.  """
    def __init__(self, master_state):
        self.model = None
        self.wake_to_wake_min_time = 5.0
        self.master_state = master_state

        wake_word_model = master_state.conman.get_wake_word_model()
        if OpenWakewordModel and wake_word_model:
            oww = None
            base_assistant_name = master_state.conman.get_config("WAKE_WORD_MODEL").rsplit(".",1)[0]
            for extension in [".tflite", ".onnx"]:
                try:
                    wake_word_file = "./"+base_assistant_name + extension
                    print("Trying to load OpenWakeWord model: "+wake_word_file)
                    oww = OpenWakewordModel(wakeword_models=[wake_word_file], vad_threshold=master_state.conman.get_config("VAD_THRESHOLD"))
                    break
                except Exception as e:
                    print(f"OpenWakeWord exception: {e}")
                    pass
            if oww:
                print("✅ OpenWakeWord model loaded")
                self.model = oww
            else:
                print(f"❌ Failed to load OpenWakeWord model")
                self.model = None

        # default to active if no model
        self.last_wake_word_detected = None

    def on_audio_buffer_in(self, audio_16ints: np.ndarray, vad_only: bool = False) -> tuple[bool, bool]:
        """
        Process audio and return (is_voice, is_wake_word).  
        don't optimize out the call to model.predict if not voice... 
        it appears to be a stateful call that accumulates audio.
        """

        # feed the VAD model first....
        vad_score = self.model.vad.predict(audio_16ints)
        is_voice = vad_score > self.master_state.conman.get_config("VAD_THRESHOLD")

        is_wake_word = False

        if not vad_only:

            # now feed the wake word model
            for _, score in self.model.predict(audio_16ints).items():
                if score > self.master_state.conman.get_config("WAKE_WORD_THRESHOLD"):
                    print(f"🎯 Wake word detected: {score:.2f}")
                    if self.last_wake_word_detected is None or (time.time() - self.last_wake_word_detected) > self.wake_to_wake_min_time:
                        self.last_wake_word_detected = time.time()
                        is_wake_word = True
                        self.model.reset()
        
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