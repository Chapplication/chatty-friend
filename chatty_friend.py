# Chatty Friend
# Finley 2025

from chatty_async_manager import AsyncManager
from chatty_mic import mic_listener
from chatty_send_audio import stream_to_assistant
from chatty_speaker import speaker_player
from chatty_state import ChattyMasterState
from chatty_realtime_messages import *
from chatty_wifi import is_online, what_is_my_ip
from chatty_debug import start_debug_server, stop_debug_server, trace

from chatty_config import USER_SAID_WAKE_WORD, USER_STARTED_SPEAKING, ASSISTANT_STOP_SPEAKING, MASTER_EXIT_EVENT, ASSISTANT_RESUME_AFTER_AUTO_SUMMARY
from chatty_config import SPEAKER_PLAY_TONE, CHATTY_SONG_STARTUP, CHATTY_SONG_AWAKE
from chatty_config import NORMAL_EXIT, UPGRADE_EXIT
import websockets

from typing import Any
import asyncio
import time
import os
WAKE_UP_INSTRUCTIONS = "You are starting a new conversation."
SUMMARY_INSTRUCTIONS = "You were talking to the user a few minutes ago."

async def grand_central_dispatch(master_state) -> list[tuple[str, Any]]:
    """ main loop for the assistant.  listen for events from the remote AI and the mic/speaker/assistant managers
    parameters:
        master state
    returns:
        list of tuples of (source, result) where source is the name of the manager that completed the task
    """

    # create a task to monitor the websocket
    websocket_task = asyncio.create_task(master_state.ws.recv()) if master_state.ws else None

    # Create tasks to listen for events from each of the managers
    manager_tasks = {}
    for name, manager in master_state.task_managers.items():
        manager_tasks[name] = asyncio.create_task(manager.event_q.get())

    task_list = ([websocket_task] if websocket_task else [])+list(manager_tasks.values())
    results = []

    try:

        while True:
            # Wait for the first task to complete (i.e., get an item from either queue)
            done, pending = await asyncio.wait(
                task_list,
                timeout=10,
                return_when=asyncio.FIRST_COMPLETED
            )

            if done:
                # got some activity.  reset the sleep timer and see what we got
                master_state.last_activity_time = time.time()
                for task in done:
                    task_exception = task.exception()
                    if task_exception:
                        print(f"❌ Error in {task.get_name()} queue: {task_exception}")

                    if task is websocket_task:
                        results.append(("assistant", task.result()))
                    else:
                        for name, manager_task in manager_tasks.items():
                            if task is manager_task:
                                results.append((name, task.result()))

                # break out to process events
                break

            # auto-expire if the socket has been open for too long
            await master_state.check_auto_summarize_time()
            master_state.check_assistant_timeout()
            
            if master_state.flow_control_event():
                break

        for task in pending:
            task.cancel()

    except websockets.ConnectionClosed:
        print("🔄 Remote closed connection - summarizing")
        master_state.should_summarize = True
        # Attempt to reconnect on next iteration
        master_state.ws = None
    except Exception as e:
        print(f"❌ Error in grand_central_dispatch: {e}")
        import traceback
        traceback.print_exc()
        # Mark websocket as invalid to trigger reconnection
        master_state.ws = None

    return results


#
# kick off a listener for the mic and a player for the speaker.  then loop talking to the AI server
#
async def assistant_go_live():

    loop_forever = True
    just_rebooted = True

    async def do_early_exit(message):
        print(message)
        try:
            os.system("espeak -v en-us -a 20 '"+message+"'")
        except Exception as e:
            print(f"❌ Error in do_early_exit: {e}")
        await asyncio.sleep(60)  # Wait 60 seconds before retry
        exit(1)  # Exit with code 1 to trigger restart loop

    if not is_online():
       await do_early_exit("Cannot find Wifi.  please connect to the device hotspot and browse to 10 dot 42 dot 0 dot 1 to configure.")

    where_to_connect = what_is_my_ip() or "Not Known"
    where_to_connect = " dot ".join(where_to_connect.split("."))

    try:
        master_state = ChattyMasterState()
    except Exception as e:
        print(f"❌ Error in assistant_go_live: {e}")
        import traceback
        traceback.print_exc()
        await do_early_exit("No OpenAI API key found.  Connect to " + where_to_connect + " and enter your API key.")

    # Start debug log server for troubleshooting (if enabled)
    if master_state.conman.get_config("DEBUG_SERVER_ENABLED"):
        debug_port = master_state.conman.get_config("DEBUG_SERVER_PORT") or 9999
        await start_debug_server(port=debug_port)
        trace("main", "chatty_friend starting")

    welcome_message = "Chatty Friend is named " + master_state.conman.get_config("WAKE_WORD_MODEL")
    welcome_message += ".  Connect to the wifi network " + master_state.conman.get_config("WIFI_SSID") + " and browse to " + where_to_connect + " to configure."

    os.system("espeak -v en-us -a 20 '"+welcome_message+"'")

    is_automated_restart_after_summary = False

    # main audio server loop
    while loop_forever:

        # set up the managers:
        #     mic (output) -> voice detector (input)
        #     voice detector (output) -> assistant (input)
        #     assistant (output) -> speaker (input)
        managers = {"mic"     : AsyncManager("mic",       mic_listener                                       )}
        managers["assistant"] = AsyncManager("assistant", stream_to_assistant, managers["mic"].output_q,     )
        managers["speaker"]   = AsyncManager("speaker",   speaker_player,      managers["assistant"].output_q)

        print("🎙️ Chatty Friend is ready")
        trace("main", "ready - waiting for wake word")

        await master_state.start_tasks(managers)

        if is_automated_restart_after_summary:
            if master_state.auto_summary_count < master_state.auto_summary_auto_resume_limit:
                trace("main", "resuming after auto-summary")
                await master_state.add_to_transcript("system", await setup_assistant_session(master_state, SUMMARY_INSTRUCTIONS))
                managers["mic"].command_q.put_nowait(ASSISTANT_RESUME_AFTER_AUTO_SUMMARY)
            else:
                trace("main", "auto-summary limit reached - waiting for wake word")
                print("⏸️ Auto-summary limit reached; waiting for wake word to resume")
        elif just_rebooted:
            await managers["speaker"].command_q.put(SPEAKER_PLAY_TONE+":"+CHATTY_SONG_STARTUP)
            just_rebooted = False

        while not master_state.flow_control_event():
            try:

                results = await grand_central_dispatch(master_state)

                for source, result in results:
                    if source == "assistant":
                        await on_assistant_input_event(result, master_state)
                    elif source in ["mic","keyboard"]:
                        if result == USER_SAID_WAKE_WORD:
                            print("🔄 USER_SAID_WAKE_WORD received from MIC")
                            trace("main", "wake word received - starting session")
                            master_state.auto_summary_count = 0  # reset auto-resume budget on explicit wake
                            await master_state.add_to_transcript("system", await setup_assistant_session(master_state, WAKE_UP_INSTRUCTIONS))
                            await managers["speaker"].command_q.put(SPEAKER_PLAY_TONE+":"+CHATTY_SONG_AWAKE)
                        elif result == USER_STARTED_SPEAKING:
                            # within a session, user started speaking.stop audio that's already queued up
                            trace("main", "user started speaking")
                            await assistant_session_cancel_audio(master_state)
                            # clear audio that's already downloaded but not played
                            await managers["speaker"].command_q.put(ASSISTANT_STOP_SPEAKING)

                if master_state.should_summarize:
                    break

            except KeyboardInterrupt:
                loop_forever = False

            except Exception as e:
                print(f"❌ Error in assistant_go_live: {e}")
                master_state.add_log_for_next_summary("X non-keyboard exception assistant go live "+str(e))
                import traceback
                traceback.print_exc()

        # summary triggered - tell the top of the loop
        if master_state.should_summarize:
            trace("main", "auto-summarize triggered")
            master_state.should_summarize = False
            is_automated_restart_after_summary = True
        else:
            trace("main", "going to sleep")
            is_automated_restart_after_summary = False

        master_state.should_reset_session = False

        try:
            # drain any remaining audio
            deadman_audio_count = 0
            spkr = managers["speaker"]
            max_wait_iterations = 200  # Increased from 100 to 200 (20 seconds total)
            while any([q.qsize() > 0 for q in [spkr.command_q, spkr.input_q, spkr.output_q]]):
                await asyncio.sleep(0.1)
                deadman_audio_count += 1
                if deadman_audio_count > max_wait_iterations:
                    print(f"🔄 DEADMAN AUDIO COUNT > {max_wait_iterations}")
                    break

            # clean up 
            for manager in managers.values():
                try:
                    manager.command_q.put_nowait(MASTER_EXIT_EVENT)
                except:
                    pass
            for manager in managers.values():
                await manager.wait_for_done()

            if master_state.ws:
                await master_state.ws.close()

            if master_state.should_upgrade:
                print("🔄 UPGRADE REQUIRED")
                exit(UPGRADE_EXIT)

            if master_state.should_quit:
                print("🔄 NORMAL EXIT")
                exit(NORMAL_EXIT)

        except Exception as e:
            print("error in assistant_go_live inner loop cleanup")
            master_state.add_log_for_next_summary("X exception inner loop "+str(e))

            import traceback
            traceback.print_exc()

    try:
        master_state.pa.terminate()
    except Exception as e:
        print("error in assistant_go_live outer loop cleanup")
        master_state.add_log_for_next_summary("X exception outer loop "+str(e))
        import traceback
        traceback.print_exc()

    # Stop debug server on exit
    trace("main", "shutting down")
    await stop_debug_server()


async def main():
    await assistant_go_live()

if __name__ == "__main__":
    asyncio.run(main())
