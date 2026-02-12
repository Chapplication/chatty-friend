# Chatty Realtime Handlers
# Finley 2025

import json
import websockets
from chatty_dsp import b64
from chatty_tools import dispatch_tool_call
from chatty_config import NATIVE_OAI_SAMPLE_RATE_HZ, MAX_OUTPUT_TOKENS
from chatty_debug import trace

import time
import asyncio
import jinja2
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
    else:
        print("❌ No websocket to send message")

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
    headers = {"Authorization": f"Bearer {master_state.openai.api_key}"}

    trace("ws", f"connecting to OpenAI ({master_state.conman.get_config('REALTIME_MODEL')})")

    ws = None
    for retries in range(10):
        try:
            ws = await websockets.connect(url, 
                                          additional_headers=headers, 
                                          max_size      = 1 << 24)#,
                                          #ping_interval = 30,
                                          #ping_timeout  = 20,
                                          #close_timeout = 20)
            break
        except Exception as e:
            print(f"Error connecting to websocket: {e}")
            trace("ws", f"connection failed (attempt {retries+1}): {e}")
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
                raise Exception("❌ Timeout waiting for "+str(event_type))

    session = await wait_for_remote_ack(ws, "session.created")
    if session:
        master_state.remote_assistant_state["session_open_time"] = time.time()
        master_state.remote_assistant_state["session_id"] = session["session"]["id"]

        print("✅ session.created "+str(session["session"]["id"]))
        trace("ws", f"session created id={session['session']['id']}")

        sp = master_state.conman.get_config("VOICE_ASSISTANT_SYSTEM_PROMPT")
        if not sp:
            sp = master_state.conman.default_config["VOICE_ASSISTANT_SYSTEM_PROMPT"]

        if sp:
            sp = jinja2.Template(sp).render(**master_state.conman.config)

        user_profile = master_state.conman.get_config("USER_PROFILE")
        if user_profile:
            sp += "\n\nHere are some FACTS that the user has told you in the past.  These are not examples, they are actual useful facts about the user.  Use them to make the conversation more interesting and personal.\n"
            sp += "\n".join(user_profile)

        resume_context = master_state.conman.get_resume_context()
        if resume_context:
            sp += "\n\n--- resuming context of prior conversation ---\n"
            sp += "\n\nYou were just talking with the user and here is some context you need to use to continue the conversation.  This is just background about where you left off, don't call any tools or functions to take any actions based on this because that work was already done:\n"
            sp += resume_context
            sp += "\n--- end of resuming context of prior conversation ---\n"

        user_name_for_assistant = master_state.conman.get_config("WAKE_WORD_MODEL")
        if user_name_for_assistant:
            sp += "\n\nYou are named " + user_name_for_assistant + ".  The user will call you this name and you can tell the user that is your name too.\n"

        sp += "\n\nRespond in " + master_state.conman.get_config("LANGUAGE") + ".\n"
        if greet_user:
            greet_user = sp+"\n\n"+greet_user

        # milliseconds before remote decides to start responding... 200 is super eager, 800 is not so eager
        etr_percent = master_state.conman.get_percent_config_as_0_to_100_int("ASSISTANT_EAGERNESS_TO_REPLY")
        etr_ms = int(200 + (800 - 200) * (etr_percent / 100.0))

        session_update_message = {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "model": master_state.conman.get_config("REALTIME_MODEL"),
                "audio": {
                    "input": {
                        "format": {          
                            "type": "audio/pcm",
                            "rate": NATIVE_OAI_SAMPLE_RATE_HZ
                        },
                        "noise_reduction": {"type":"far_field"},
                        "turn_detection": {
                            "create_response": True,
                            #"eagerness": "high" if etr_ms <= 200 else "auto" if etr_ms <= 800 else "low",
                            "interrupt_response": True, # allow user to interrupt assistant's response
                            "prefix_padding_ms": 300,
                            "silence_duration_ms": etr_ms,
                            "threshold": 0.5,
                            "type": "server_vad"
                            }
                        },
                    "output": {
                        "format": {
                            "type": "audio/pcm",
                            "rate": NATIVE_OAI_SAMPLE_RATE_HZ
                        },
                        "speed":get_speed_from_percentage_int_0_to_100(master_state.conman.get_config("SPEED")),
                        "voice": master_state.conman.get_config("VOICE"),
                    }
                },
                "instructions": sp,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "output_modalities": ["audio"],
                # "temperature": 0.8,Failing as of sept 1 2025
                "tool_choice": "auto",
                "tools":[tool.get_model_function_call_metadata() for tool in master_state.tools_for_assistant],
                "tracing": None,
                "truncation":"auto"
            }
        }

        # Configure session
        if await send_to_assistant(ws, session_update_message):
            response = await wait_for_remote_ack(ws, "session.updated")

            print("✅ session.updated")
            trace("ws", "session updated - ready for audio")

            master_state.ws = ws

            if greet_user:
                await send_assistant_instructions(master_state, greet_user)

            # resturn the system prompt for the supervisor to use
            return sp

async def send_assistant_instructions(master_state, greet_user):
    await send_to_assistant(master_state.ws, {
            "type": "response.create",
            "response": {
                "conversation":"auto",
                "instructions": greet_user,
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "output_modalities": ["audio"],
                "audio": {
                    "output": {
                        "format": {
                            "type": "audio/pcm",
                            "rate": NATIVE_OAI_SAMPLE_RATE_HZ
                        },
                        "voice": master_state.conman.get_config("VOICE"),
                    }
                }
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
    """ Digest events to collect usage, estimate costs, and handle OOB transcription. """

    # --- Track usage for ALL responses (main + OOB transcription) ---
    try:
        usage = event.get("response",{}).get("usage",{})

        ONE_MILLION = 1_000_000

        cost_sheet_per_million = master_state.conman.get_config("TOKEN_COST_PER_MILLION")

        per_input_text_token = cost_sheet_per_million["per_input_text_token"] / ONE_MILLION
        per_input_text_token_cached = cost_sheet_per_million["per_input_text_token_cached"] / ONE_MILLION
        per_input_audio_token = cost_sheet_per_million["per_input_audio_token"] / ONE_MILLION
        per_input_audio_token_cached = cost_sheet_per_million["per_input_audio_token_cached"] / ONE_MILLION
        per_output_text_token = cost_sheet_per_million["per_output_text_token"] / ONE_MILLION
        per_output_audio_token = cost_sheet_per_million["per_output_audio_token"] / ONE_MILLION

        response_cost = 0

        response_cost += usage.get("input_token_details",{}).get("text_tokens",0) * per_input_text_token
        response_cost += usage.get("input_token_details",{}).get("audio_tokens",0) * per_input_audio_token
        response_cost += usage.get("input_token_details",{}).get("cached_tokens_details",{}).get("text_tokens",0) * per_input_text_token_cached
        response_cost += usage.get("input_token_details",{}).get("cached_tokens_details",{}).get("audio_tokens",0) * per_input_audio_token_cached

        response_cost += usage.get("output_token_details",{}).get("text_tokens",0) * per_output_text_token
        response_cost += usage.get("output_token_details",{}).get("audio_tokens",0) * per_output_audio_token

        master_state.accumulate_usage(response_cost)
    except Exception as e:
        print(f"❌ Error accumulating usage: {e}")

    # --- Check if this is an OOB transcription response (text-only, no audio) ---
    # OOB transcription responses are the only text-only responses in the system.
    # All other responses (main assistant, system text, function follow-ups) include audio.
    try:
        transcription_text = extract_transcription_text(event)
        if transcription_text is not None:
            if transcription_text:
                await master_state.add_to_transcript("user", transcription_text)
            else:
                await master_state.add_to_transcript("user", "[transcription unavailable]")
    except Exception as e:
        print(f"❌ Error processing OOB transcription: {e}")
        await master_state.add_to_transcript("user", "[transcription unavailable]")

async def on_assistant_transcript(event, master_state):
    """ Track the assistant's own speech as text in the transcript. """
    await master_state.add_to_transcript("AI", event['transcript'])


#
#  OUT-OF-BAND (OOB) TRANSCRIPTION
#
#  Instead of relying on the built-in input_audio_transcription (which uses a separate
#  ASR model that frequently produces truncated, foreign-language, or nonsense text),
#  we ask the same Realtime model to transcribe the user's speech via a second
#  response.create request on the same WebSocket. This gives accurate, context-aware
#  transcription because the model that understood the audio is the one producing the text.
#

def build_oob_transcription_instructions(master_state):
    """Build instructions for the out-of-band transcription request.
    
    Kept minimal because with full session context the model already knows the
    user's name, conversation topic, vocabulary, etc.  The instructions are
    emphatic about the role to prevent the model from generating a conversational
    response instead of transcribing.
    """
    instructions = (
        "You are a speech-to-text transcriber, NOT a conversational assistant. "
        "Your ONLY job is to transcribe the user's most recent speech turn into text. "
        "Output ONLY the verbatim transcription of what the user said — nothing else. "
        "Do NOT respond to the user. Do NOT continue the conversation. "
        "Do NOT add commentary, questions, or any text that the user did not speak. "
        "Do NOT wrap the output in JSON or any other format."
    )

    language = master_state.conman.get_config("LANGUAGE")
    if language:
        instructions += f" The user speaks {language}."

    return instructions


async def request_oob_transcription(master_state):
    """Fire an out-of-band text-only response to transcribe the user's last turn.
    
    The response uses conversation="none" so it does not write back to the
    conversation state.  Without an explicit "input" field the model sees the
    full session context (instructions + all prior turns) for best grounding.
    """

    # COST REDUCTION: This currently uses full session context (~16-22x the cost of
    # the old built-in transcription) because no "input" field is specified, so the
    # model sees the entire conversation history for best grounding.
    #
    # To reduce to ~3-5x cost, add an "input" field referencing only the latest
    # committed audio item (pass committed_item_id from the input_audio_buffer.committed
    # event into this function):
    #
    #   "input": [{"type": "item_reference", "id": committed_item_id}]
    #
    # This limits the model to just the latest user audio turn, losing session
    # context grounding but significantly reducing token consumption.
    #
    # A middle ground: include a text summary of recent turns in the instructions
    # field while using the item_reference input, getting partial grounding at
    # moderate cost.

    await send_to_assistant(master_state.ws, {
        "type": "response.create",
        "response": {
            "conversation": "none",
            "output_modalities": ["text"],
            "instructions": build_oob_transcription_instructions(master_state),
            "max_output_tokens": 4096,
            "tool_choice": "none"
        }
    })


async def on_audio_buffer_committed(event, master_state):
    """Handle the server committing the user's audio buffer (end of user turn).
    
    Fires an out-of-band transcription request so the Realtime model produces
    an accurate text transcript of what the user just said.
    """
    # event contains "item_id" — the conversation item for the committed audio.
    # Stored here for potential future cost reduction (see request_oob_transcription).
    # committed_item_id = event.get("item_id")

    await request_oob_transcription(master_state)


def extract_transcription_text(event):
    """Extract text from a response.done event's output items.
    
    Returns the concatenated text if the response contains only text output
    (no audio), indicating it is an OOB transcription response. Returns None
    if the response contains audio output (i.e. a normal assistant response)
    or if the output contains function calls rather than message content.
    
    The Realtime API uses content types "output_text" and "output_audio"
    (not "text" and "audio").
    """
    response = event.get("response", {})
    output_items = response.get("output", [])

    if not output_items:
        return None

    has_audio = False
    text_parts = []

    for item in output_items:
        # Skip function call outputs — only look at message items
        if item.get("type") != "message":
            return None
        for part in item.get("content", []):
            content_type = part.get("type", "")
            if content_type in ("audio", "output_audio"):
                has_audio = True
            elif content_type in ("text", "output_text"):
                text_parts.append(part.get("text", ""))

    # Only treat as transcription if there is text and no audio
    if text_parts and not has_audio:
        raw = "".join(text_parts).strip()
        return _unwrap_transcription_json(raw)

    return None


def _unwrap_transcription_json(text):
    """Unwrap transcription text if the model returned it wrapped in JSON.
    
    The OOB model sometimes returns structured output like:
      {"transcription": "actual text here"}
    This extracts the inner text. If the text is already plain, returns as-is.
    """
    if not text or not text.startswith("{"):
        return text
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            # Try common keys the model might use
            for key in ("transcription", "transcript", "text"):
                if key in parsed:
                    return str(parsed[key]).strip()
            # If it's a dict with a single string value, use that
            values = [v for v in parsed.values() if isinstance(v, str)]
            if len(values) == 1:
                return values[0].strip()
    except (json.JSONDecodeError, ValueError):
        pass
    return text

async def on_assistant_error(event, master_state):
    """ diagnostic... look at errors """
    error_code = event.get('error', {}).get('code', '')
    error_msg = event.get('error', {}).get('message', 'Unknown error')
    
    # Suppress expected/harmless errors
    if error_code in ['response_cancel_not_active', 'conversation_already_has_active_response']:
        # These happen during normal interruption flow - not a problem
        return
    
    print(f"❌ Error: {error_msg}")
    trace("ws", f"error: {error_msg}")

async def on_assistant_audio(event, master_state):
    """ stream audio to speaker and track the item id for cancellations """
    # stream to speaker and track the active item id for cancellations
    if "item_id" not in event:
        return
    if event["type"] == "response.output_audio.delta":
        if "streaming_audio_item_ids" not in master_state.remote_assistant_state:
            master_state.remote_assistant_state["streaming_audio_item_ids"] = []
        if event["item_id"] not in master_state.remote_assistant_state["streaming_audio_item_ids"]:
            master_state.remote_assistant_state["streaming_audio_item_ids"].append(event["item_id"])
            trace("ws", f"audio stream started item={event['item_id'][:8]}...")
        await master_state.task_managers["speaker"].input_q.put(event["delta"])
    elif "streaming_audio_item_ids" in master_state.remote_assistant_state:
        if event["item_id"] in master_state.remote_assistant_state["streaming_audio_item_ids"]:
            master_state.remote_assistant_state["streaming_audio_item_ids"].remove(event["item_id"])
            trace("ws", f"audio stream ended item={event['item_id'][:8]}...")

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
        func_name = event.get("name", "unknown")
        trace("tool", f"calling {func_name}")
        await send_function_call_result(await dispatch_tool_call(event, master_state), call_id)
        trace("tool", f"completed {func_name}")
            
    except Exception as e:
        print(f"❌ Error handling function call: {e}")
        trace("tool", f"error in {func_name}: {e}")
        await send_function_call_result(f"Error: {str(e)}", call_id)

async def on_speech_started(event, master_state):
    """Handle server VAD detecting user speech - stop speaker to allow interruption."""
    from chatty_config import ASSISTANT_STOP_SPEAKING
    
    # Cancel any in-progress audio on the server side
    await assistant_session_cancel_audio(master_state)
    
    # Stop the local speaker from playing buffered audio
    if "speaker" in master_state.task_managers:
        await master_state.task_managers["speaker"].command_q.put(ASSISTANT_STOP_SPEAKING)

assistant_event_handlers = {
    "response.output_audio.delta": on_assistant_audio,
    "response.output_audio.done": on_assistant_audio,
    "error": on_assistant_error,
    "response.done": on_assistant_response_done,
    "response.output_audio_transcript.done": on_assistant_transcript,
    "response.function_call_arguments.done": on_function_call_arguments_done,
    "input_audio_buffer.speech_started": on_speech_started,
    "input_audio_buffer.committed": on_audio_buffer_committed,
}

async def on_assistant_input_event(event_raw, master_state):
    """ handle events from the assistant """
    event = json.loads(event_raw)
    etype = event["type"]

    if etype in assistant_event_handlers:
        await assistant_event_handlers[etype](event, master_state)
    elif "error" in event_raw or "invalid" in event_raw:
        print(f"❌ Invalid event: {event_raw}")