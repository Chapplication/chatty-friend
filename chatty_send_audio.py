# Chatty Send Audio
# Finley 2025

import asyncio
from chatty_async_manager import AsyncManager
from chatty_dsp import upsample_audio_efficient, apply_simple_noise_gate
import numpy as np
from chatty_config import MASTER_EXIT_EVENT, CHUNK_DURATION_MS
from chatty_debug import trace

from chatty_realtime_messages import send_audio_to_assistant
#
#  Audio OUT handling (mic voice, when active, to assistant) ---------
#

async def stream_to_assistant(manager: AsyncManager):
    """Read audio chunks from mic event queue and send as JSON events to the assistant."""
    should_exit = False

    have_not_sent_audio = True
    chunk_count = 0  # For rate-limited tracing

    initial_buffers = []
    while not should_exit:
        try:
            events = await manager.wait_and_dispatch()
            for event_type, event in events:
                if event_type == "input":
                    if manager.master_state.ws:
                        # Apply noise gate if configured (disabled by default for RPi performance)
                        # Only enable if experiencing significant background noise issues
                        noise_gate_threshold = manager.master_state.conman.get_config("NOISE_GATE_THRESHOLD")
                        if noise_gate_threshold is not None and noise_gate_threshold > 0:
                            event = apply_simple_noise_gate(event, threshold=float(noise_gate_threshold))
                        
                        # event is audio_16ints (np.ndarray) at 16000hz so we need to up-sample to 24000hz
                        # This upsampling is optimized for RPi: simple linear interpolation, minimal CPU
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
                            chunk_count += 1
                            # Rate-limited tracing: log first chunk and every 50th chunk
                            if chunk_count == 1:
                                trace("audio_out", f"first audio buffer sent ({len(upsampled_buffer)}B)")
                            elif chunk_count % 50 == 0:
                                trace("audio_out", f"streaming chunk #{chunk_count} ({len(upsampled_buffer)}B)")

                elif event_type == "command":
                    if event == MASTER_EXIT_EVENT:
                        should_exit = True
                        break
        except asyncio.CancelledError:
            should_exit = True
        except Exception as e:
            print(f"\nError in stream_to_assistant: {e}")

    print("🎤 Assistant MASTER_EXIT_EVENT.")
            
