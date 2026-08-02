# Chatty Send Audio
# Finley 2025

import asyncio
import time
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
    last_audio_send_time = None
    burst_count = 0
    active_burst = None

    def finish_burst(reason):
        nonlocal active_burst
        if not active_burst:
            return
        wall_ms = (active_burst["last_sent"] - active_burst["started"]) * 1000
        audio_ms = active_burst["bytes"] / (24_000 * 2) * 1000
        trace(
            "audio_out",
            f"B{active_burst['id']:04d} END local={active_burst['local_turn']} "
            f"reason={reason} wall_ms={wall_ms:.0f} audio_ms={audio_ms:.0f} "
            f"send_calls={active_burst['send_calls']} bytes={active_burst['bytes']} "
            f"send_failures={active_burst['send_failures']} max_input_q={active_burst['max_input_q']} "
            f"max_input_rms={active_burst['max_input_rms']:.0f} "
            f"max_sent_rms={active_burst['max_sent_rms']:.0f}",
        )
        active_burst = None

    initial_buffers = []
    while not should_exit:
        try:
            events = await manager.wait_and_dispatch()
            if not events and active_burst and time.monotonic() - last_audio_send_time > 0.5:
                finish_burst("idle")

            for event_type, event in events:
                if event_type == "input":
                    if not manager.master_state.ws:
                        # WebSocket not connected yet, skip this audio chunk
                        continue
                    
                    # Apply noise gate if configured (disabled by default for RPi performance)
                    # Only enable if experiencing significant background noise issues
                    input_rms = float(np.sqrt(np.mean(event.astype(np.float64) ** 2)))
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
                        sent_audio = np.frombuffer(upsampled_buffer, dtype=np.int16)
                        sent_rms = float(np.sqrt(np.mean(sent_audio.astype(np.float64) ** 2)))
                        # Check WebSocket health before sending
                        ws = manager.master_state.ws
                        if ws is None:
                            chunk_count += 1
                            continue
                        
                        now = time.monotonic()
                        is_new_burst = last_audio_send_time is None or now - last_audio_send_time > 0.5
                        if is_new_burst:
                            finish_burst("next_burst")
                            burst_count += 1
                            diagnostics = getattr(manager.master_state, "audio_diagnostics", {})
                            local_turn_id = diagnostics.get("latest_local_turn_id") or "none"
                            local_turn_started = diagnostics.get("local_turn_started_monotonic")
                            local_age_ms = (
                                (now - local_turn_started) * 1000
                                if local_turn_started is not None
                                else -1
                            )
                            active_burst = {
                                "id": burst_count,
                                "local_turn": local_turn_id,
                                "started": now,
                                "last_sent": now,
                                "send_calls": 0,
                                "bytes": 0,
                                "send_failures": 0,
                                "max_input_q": manager.input_q.qsize(),
                                "max_input_rms": input_rms,
                                "max_sent_rms": sent_rms,
                            }
                            trace(
                                "audio_out",
                                f"B{burst_count:04d} START local={local_turn_id} "
                                f"local_age_ms={local_age_ms:.0f} first_bytes={len(upsampled_buffer)} "
                                f"ws_state={getattr(ws, 'state', 'unknown')} "
                                f"input_q={manager.input_q.qsize()} input_rms={input_rms:.0f} "
                                f"sent_rms={sent_rms:.0f}",
                            )

                        sent = await send_audio_to_assistant(ws, upsampled_buffer)
                        last_audio_send_time = now
                        if active_burst:
                            active_burst["last_sent"] = now
                            active_burst["send_calls"] += 1
                            active_burst["bytes"] += len(upsampled_buffer)
                            active_burst["max_input_q"] = max(
                                active_burst["max_input_q"], manager.input_q.qsize()
                            )
                            active_burst["max_input_rms"] = max(
                                active_burst["max_input_rms"], input_rms
                            )
                            active_burst["max_sent_rms"] = max(
                                active_burst["max_sent_rms"], sent_rms
                            )
                        if not sent:
                            if active_burst:
                                active_burst["send_failures"] += 1
                            trace("audio_out", f"B{burst_count:04d} send failed")
                        chunk_count += 1
                        
                        # Rate-limited logging: log first chunk only
                        if chunk_count == 1:
                            print(f"🎙️ Streaming audio to OpenAI")
                            trace("audio_out", f"first audio buffer sent ({len(upsampled_buffer)}B)")

                elif event_type == "command":
                    if event == MASTER_EXIT_EVENT:
                        finish_burst("shutdown")
                        should_exit = True
                        break
        except asyncio.CancelledError:
            should_exit = True
        except Exception as e:
            print(f"\nError in stream_to_assistant: {e}")

    print("🎤 Assistant MASTER_EXIT_EVENT.")
            
