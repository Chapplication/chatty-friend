# Chatty Speaker
# Finley 2025
#
#  Speaker playback handling (assistant to speaker) ---------
#

import asyncio
import numpy as np
import pyaudio
from chatty_async_manager import AsyncManager
import base64
import time
from chatty_config import ASSISTANT_STOP_SPEAKING, MASTER_EXIT_EVENT, NATIVE_OAI_SAMPLE_RATE_HZ, CHUNK_DURATION_MS, SPEAKER_PLAY_TONE
from chatty_config import chatty_songs, CHATTY_SONG_ERROR
from chatty_dsp import chatty_tone
from chatty_debug import trace

def chatty_tone_buffer(event):

    try:
        song = event.split(":",1)[1].upper()
        return chatty_tone(chatty_songs[song])
    except:
        return chatty_tone(chatty_songs[CHATTY_SONG_ERROR])

async def speaker_player(manager: AsyncManager) -> None:
    """Play audio chunks from the assistant to the speaker."""
    should_exit = False
    speaker_stream = None
    unused_buffer = None
    last_cancel_time = None

    def _speaker_callback(in_data, frame_count, time_info, status):
        """ Implement the PyAudio callback protocol."""
        # frame_count is the number of frames requested
        # We need to return audio data as bytes

        if status:
            print(f"*** Speaker callback status: {status}")

        nonlocal unused_buffer

        # peek in the output queue to see how many buffers we can use
        if unused_buffer is not None:
            buffers_to_play = [unused_buffer]
            frames_available = len(unused_buffer)
            unused_buffer = None
        else:
            buffers_to_play = []
            frames_available = 0
        
        while frames_available < frame_count and not manager.output_q.empty():
            # see if the next buffer will fit in the remaining space
            try:
                next_buffer = manager.output_q.get_nowait()
                buffers_to_play.append(next_buffer)
                frames_available += len(next_buffer)
            except:
                break
        
        if frames_available > frame_count:
            # trim excess audio and keep for next time
            trim_frames = frames_available - frame_count
            frames_available = frame_count
            unused_buffer = buffers_to_play[-1][-trim_frames:]
            buffers_to_play[-1] = buffers_to_play[-1][:-trim_frames]
        
        # prep to play the audio
        should_exit = False
        if buffers_to_play:
            audio_array = np.concatenate(buffers_to_play)
        else:
            # nothing to play? stop the stream
            audio_array = np.array([], dtype=np.int16)
            should_exit = True
        
        if frames_available < frame_count:
            # pad with silence so we get the correct number of frames
            audio_array = np.concatenate([audio_array, np.zeros(frame_count - frames_available, dtype=np.int16)])
        
        # Convert numpy array to bytes for PyAudio
        try:
            volume = manager.master_state.conman.get_percent_config_as_0_to_100_int("VOLUME")/100.0
        except:
            volume = 1.0

        out_data = (audio_array * volume).astype(np.int16).tobytes()
        
        if should_exit:
            return (out_data, pyaudio.paComplete)
        else:
            return (out_data, pyaudio.paContinue)

    def stop_speaker_stream(speaker_stream):
        if speaker_stream:
            print("🔈 Stopping speaker stream")
            trace("spkr", "stream stopped")
            speaker_stream.stop_stream()
            speaker_stream.close()
        return None

    def prepare_to_speak(speaker_stream):

        if speaker_stream and not speaker_stream.is_active():
            speaker_stream = stop_speaker_stream(speaker_stream)

        if not speaker_stream:

            speaker_stream = manager.master_state.pa.open( 
                format=pyaudio.paInt16,
                channels=1,
                rate=NATIVE_OAI_SAMPLE_RATE_HZ,
                output=True,
                frames_per_buffer=int(NATIVE_OAI_SAMPLE_RATE_HZ * CHUNK_DURATION_MS / 1000),
                stream_callback=_speaker_callback
            )

            # Start the stream
            speaker_stream.start_stream()
            trace("spkr", "stream started")

        return speaker_stream

    while not should_exit:
        try:
            events = await manager.wait_and_dispatch()
            for event_type, event in events:
                if event_type == "command":
                    if event == MASTER_EXIT_EVENT:
                        trace("spkr", "received exit command")
                        should_exit = True
                        break
                    elif event.startswith(SPEAKER_PLAY_TONE):
                        tone_name = event.split(":", 1)[1] if ":" in event else "unknown"
                        trace("spkr", f"playing tone: {tone_name}")
                        manager.output_q.put_nowait(chatty_tone_buffer(event))
                        speaker_stream = prepare_to_speak(speaker_stream)
                    elif event == ASSISTANT_STOP_SPEAKING:
                        trace("spkr", "interrupted by user - clearing queue")
                        last_cancel_time = time.time()
                        speaker_stream = stop_speaker_stream(speaker_stream)
                        # clear the output queue
                        while not manager.output_q.empty():
                            try:
                                manager.output_q.get_nowait()
                            except:
                                break
                        unused_buffer = None

                elif event_type == "input":

                    # catch buffers incoming after a user cancel but before response stops
                    if last_cancel_time and time.time() - last_cancel_time < 0.5:
                        continue
                    last_cancel_time = None

                    event_buffer = base64.b64decode(event)
                    manager.output_q.put_nowait(np.frombuffer(event_buffer, dtype=np.int16))                    
                    speaker_stream = prepare_to_speak(speaker_stream)

        except asyncio.CancelledError:
            should_exit = True
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"\nError in speaker_player: {e}")

    # drain pending audio for up to 1 second
    deadman = 10
    while speaker_stream and speaker_stream.is_active() and deadman > 0:
        await asyncio.sleep(0.1)
        deadman -= 1

    stop_speaker_stream(speaker_stream)

    print("🎤 Speaker MASTER_EXIT_EVENT.")
