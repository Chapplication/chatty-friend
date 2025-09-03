# Chatty Send Audio
# Finley 2025

import asyncio
from chatty_async_manager import AsyncManager
from chatty_dsp import upsample_audio_efficient
from chatty_config import MASTER_EXIT_EVENT, CHUNK_DURATION_MS

from chatty_realtime_messages import send_audio_to_assistant
#
#  Audio OUT handling (mic voice, when active, to assistant) ---------
#

async def stream_to_assistant(manager: AsyncManager):
    """Read audio chunks from mic event queue and send as JSON events to the assistant."""
    should_exit = False

    have_not_sent_audio = True

    initial_buffers = []
    while not should_exit:
        try:
            events = await manager.wait_and_dispatch()
            for event_type, event in events:
                if event_type == "input":
                    if manager.master_state.ws:
                        # event is audio_16ints (np.ndarray) at 16000hz so we need to up-sample to 24000hz
                        upsampled_buffer = upsample_audio_efficient(event)

                        # when socket first connects, hold on to a few frames so the assistant gets enough to infer language
                        if have_not_sent_audio:
                            initial_buffers.append(upsampled_buffer)
                            if len(initial_buffers) < int(1000/CHUNK_DURATION_MS):
                                upsampled_buffer = None
                            else:
                                upsampled_buffer = b''.join(initial_buffers)
                                have_not_sent_audio = False

                        if upsampled_buffer:
                            await send_audio_to_assistant(manager.master_state.ws, upsampled_buffer)

                elif event_type == "command":
                    if event == MASTER_EXIT_EVENT:
                        should_exit = True
                        break
        except asyncio.CancelledError:
            should_exit = True
        except Exception as e:
            print(f"\nError in stream_to_assistant: {e}")

    print("🎤 Assistant MASTER_EXIT_EVENT.")
            
