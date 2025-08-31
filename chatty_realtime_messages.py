# Chatty Realtime Handlers
# Finley 2025

import json
import websockets
from chatty_dsp import b64
from chatty_tools import dispatch_tool_call
import time
import asyncio

#
#  OUTGOING MESSAGES TO ASSISTANT
#
async def send_to_assistant(ws, message):

    if ws:

        try:
            await ws.send(json.dumps(message))
            return True
        except Exception as e:
            print(f"Error sending websocket message: {e}")
            print(f"Message: {str(message)[:100]}...")

    return False

async def send_audio_to_assistant(ws, buffer):
    await send_to_assistant(ws,{
        "type": "input_audio_buffer.append",
        "audio": b64(buffer),
    })

def get_speed_from_percentage_int_0_to_100(speed):
    # map [0-100] -> [0.25-1.5] (per spec); otherwise 1.0
    try:
        return max(0.25, min(1.5, 0.25+(float(speed) * 1.25) / 100.0))
    except:
        return 1.0

#
#   SETUP realtime connection
#
async def setup_assistant_session(master_state, greet_user: str = None):

    url = master_state.conman.get_config("WS_URL") + master_state.conman.get_config("REALTIME_MODEL")
    headers = {"Authorization": f"Bearer {master_state.openai.api_key}", "OpenAI-Beta": "realtime=v1"}

    ws = None
    for retries in range(10):
        try:
            ws = await websockets.connect(url, additional_headers=headers, max_size=1 << 24)
            break
        except Exception as e:
            print(f"Error connecting to websocket: {e}")
            await asyncio.sleep(1)

    if not ws:
        raise Exception("❌ Failed to connect to websocket")

    # Wait until server sends session.created
    async def wait_for_remote_ack(ws, event_type):
        deadman = 100
        while True:
            msg = await ws.recv()
            event = json.loads(msg)
            if event["type"] == event_type:
                return event
            await asyncio.sleep(0.1)
            deadman -= 1
            if deadman < 0:
                raise Exception("❌ Timeout waiting for session.created")

    session = await wait_for_remote_ack(ws, "session.created")
    if session:
        master_state.remote_assistant_state["session_open_time"] = time.time()
        master_state.remote_assistant_state["session_id"] = session["session"]["id"]

        print("✅ session.created")

        sp = master_state.conman.get_config("VOICE_ASSISTANT_SYSTEM_PROMPT")
        if not sp:
            sp = master_state.conman.default_config["VOICE_ASSISTANT_SYSTEM_PROMPT"]

        user_profile = master_state.conman.get_config("USER_PROFILE")
        if user_profile:
            sp += "\n\nHere are some things that they user has told you in the past.  Use them to make the conversation more interesting and personal.\n"
            sp += "\n".join(user_profile)

        resume_context = master_state.conman.get_resume_context()
        if resume_context:
            sp += "\n\nYou were just talking with the user and here is some context you need to use to continue the conversation:\n"
            sp += resume_context

        # milliseconds before remote decides to start responding... 200 is super eager, 800 is not so eager
        etr_percent = master_state.conman.get_percent_config_as_0_to_100_int("ASSISTANT_EAGERNESS_TO_REPLY")
        etr_ms = int(200 + (800 - 200) * (etr_percent / 100.0))

        # Configure session
        if await send_to_assistant(ws, {
            "type": "session.update",
            "session": {
                "voice": master_state.conman.get_config("VOICE"),
                "instructions": sp,
                "max_response_output_tokens": 1024,
                "speed": get_speed_from_percentage_int_0_to_100(master_state.conman.get_config("SPEED")),
                "modalities": ["audio", "text"],
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_noise_reduction": {"type":"far_field"},
                "tools":[tool.get_model_function_call_metadata() for tool in master_state.tools_for_assistant],
                "input_audio_transcription": {"model": master_state.conman.get_config("AUDIO_TRANSCRIPTION_MODEL")},
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": etr_ms, 
                    "create_response": True, 
                    "interrupt_response": False, # assume we are doing VAD locally on the pi; mac is push to talk
                }
            },
        }):
            await wait_for_remote_ack(ws, "session.updated")

            print("✅ session.updated")

            master_state.ws = ws

            if greet_user:
                await send_assistant_instructions(master_state, greet_user)

            # resturn the system prompt for the supervisor to use
            return sp

async def send_assistant_instructions(master_state, greet_user):
    await send_to_assistant(master_state.ws, {
            "type": "response.create",
            "response": {
                "modalities": ["audio","text"],
                "instructions": greet_user,
                "voice": master_state.conman.get_config("VOICE"),
                "output_audio_format": "pcm16",
                "max_output_tokens": 64
            }
        })

async def send_assistant_text_from_system(master_state, message):
    await send_to_assistant(master_state.ws, {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": message
                    }
                ]
            }
        })
    await send_to_assistant(master_state.ws, {
            "type": "response.create",
            "response": {
                "modalities": ["text", "audio"],
                "instructions": "brief response",
                "voice": master_state.conman.get_config("VOICE"),
                "output_audio_format": "pcm16",
                "max_output_tokens": 64
            }
        })

async def assistant_session_cancel_audio(master_state):
    """ cancels audio that is streaming in if the user interrupts """

    if not master_state.remote_assistant_state:
        return
    item_ids = master_state.remote_assistant_state.get("streaming_audio_item_ids")
    if not master_state.ws or not item_ids:
        return

    # tell the assistant to stop speaking; pending audio will be discarded
    for item_id in item_ids:
        await send_to_assistant(master_state.ws, {
                "type": "conversation.item.truncate",
                "audio_end_ms": 0,
                "content_index": 0,
                "item_id": item_id,
            })
    await send_to_assistant(master_state.ws, {
            "type": "response.cancel",
        })


#
#  HANLDERS for incoming assistant realtime events
#

async def on_assistant_response_done(event, master_state):
    """ Digest events to collect usage and estimate costs. """
    usage = event.get("response",{}).get("usage",{})

    # https://platform.openai.com/docs/pricing#audio-tokens Aug 28 2025
    ONE_MILLION = 1_000_000
    cost_sheet_per_million = {
        "gpt-realtime": {
            "per_input_text_token": 4.0,
            "per_input_text_token_cached": 0.4,
            "per_input_audio_token": 32.0,
            "per_input_audio_token_cached": 32.0,
            "per_output_text_token": 16,
            "per_output_audio_token": 64,
        },
        "gpt-4o-mini-realtime-preview": {
            "per_input_text_token": 0.6,
            "per_input_text_token_cached": 0.3,
            "per_input_audio_token": 10,
            "per_input_audio_token_cached": 0.3,
            "per_output_text_token": 2.4,
            "per_output_audio_token": 20,
        }
    }

    active_model = master_state.conman.get_config("REALTIME_MODEL")

    # if the model is not in the cost sheet, use the first model in the sheet... UGH estimate
    if active_model not in cost_sheet_per_million:
        active_model = cost_sheet_per_million.keys()[0]

    per_input_text_token = cost_sheet_per_million[active_model]["per_input_text_token"] / ONE_MILLION
    per_input_text_token_cached = cost_sheet_per_million[active_model]["per_input_text_token_cached"] / ONE_MILLION
    per_input_audio_token = cost_sheet_per_million[active_model]["per_input_audio_token"] / ONE_MILLION
    per_input_audio_token_cached = cost_sheet_per_million[active_model]["per_input_audio_token_cached"] / ONE_MILLION
    per_output_text_token = cost_sheet_per_million[active_model]["per_output_text_token"] / ONE_MILLION
    per_output_audio_token = cost_sheet_per_million[active_model]["per_output_audio_token"] / ONE_MILLION

    response_cost = 0

    response_cost += usage.get("input_token_details",{}).get("text_tokens",0) * per_input_text_token
    response_cost += usage.get("input_token_details",{}).get("audio_tokens",0) * per_input_audio_token
    response_cost += usage.get("input_token_details",{}).get("cached_tokens_details",{}).get("text_tokens",0) * per_input_text_token_cached
    response_cost += usage.get("input_token_details",{}).get("cached_tokens_details",{}).get("audio_tokens",0) * per_input_audio_token_cached

    response_cost += usage.get("output_token_details",{}).get("text_tokens",0) * per_output_text_token
    response_cost += usage.get("output_token_details",{}).get("audio_tokens",0) * per_output_audio_token

    master_state.accumulate_usage(response_cost)

async def on_transcript_event(event, master_state):
    """ Track the transcript of the conversation. """
    event_type = event["type"]
    if event_type == 'response.audio_transcript.done':
        await master_state.add_to_transcript("AI", event['transcript'])

    elif event_type == 'conversation.item.input_audio_transcription.completed':
        await master_state.add_to_transcript("user", event['transcript'])

async def on_assistant_error(event, master_state):
    """ diagnostic... look at errors """
    print(f"❌ Error: {event.get('error', {}).get('message', 'Unknown error')}")

async def on_assistant_audio(event, master_state):
    """ stream audio to speaker and track the item id for cancellations """
    # stream to speaker and track the active item id for cancellations
    if "item_id" not in event:
        return
    if event["type"] == "response.audio.delta":
        if "streaming_audio_item_ids" not in master_state.remote_assistant_state:
            master_state.remote_assistant_state["streaming_audio_item_ids"] = []
        if event["item_id"] not in master_state.remote_assistant_state["streaming_audio_item_ids"]:
            master_state.remote_assistant_state["streaming_audio_item_ids"].append(event["item_id"])
        await master_state.task_managers["speaker"].input_q.put(event["delta"])
    elif "streaming_audio_item_ids" in master_state.remote_assistant_state:
        if event["item_id"] in master_state.remote_assistant_state["streaming_audio_item_ids"]:
            master_state.remote_assistant_state["streaming_audio_item_ids"].remove(event["item_id"])

async def on_function_call_arguments_done(event, master_state):
    """ receive and dispatch tool calls """
    async def send_function_call_result(result, call_id):
        result_message = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "output": result,
                "call_id": call_id
            }
        }
        
        try:
            if await send_to_assistant(master_state.ws, result_message):
                await send_to_assistant(master_state.ws, {"type": "response.create"})
            
        except Exception as e:
            print(f"❌ Failed to send tool call result: {e}")

    try:
        call_id = event.get("call_id", "")
        await send_function_call_result(await dispatch_tool_call(event, master_state), call_id)
            
    except Exception as e:
        print(f"❌ Error handling function call: {e}")
        await send_function_call_result(f"Error: {str(e)}", call_id)

assistant_event_handlers = {
    "response.audio.delta": on_assistant_audio,
    "response.audio.done": on_assistant_audio,
    "error": on_assistant_error,
    "response.done": on_assistant_response_done,
    "conversation.item.input_audio_transcription.completed": on_transcript_event,
    "response.audio_transcript.done": on_transcript_event,
    "response.function_call_arguments.done": on_function_call_arguments_done,
}

async def on_assistant_input_event(event_raw, master_state):
    """ handle events from the assistant """
    event = json.loads(event_raw)
    etype = event["type"]

    if etype in assistant_event_handlers:
        await assistant_event_handlers[etype](event, master_state)
