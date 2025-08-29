# Chatty Friend
# Finley 2025

from chatty_async_manager import AsyncManager
from chatty_mic import mic_listener
from chatty_send_audio import stream_to_assistant
from chatty_speaker import speaker_player
from chatty_state import ChattyMasterState
from chatty_realtime_messages import *

from chatty_config import USER_SAID_WAKE_WORD, USER_STARTED_SPEAKING, ASSISTANT_STOP_SPEAKING, MASTER_EXIT_EVENT, ASSISTANT_RESUME_AFTER_AUTO_SUMMARY
from chatty_config import SPEAKER_PLAY_TONE, CHATTY_SONG_STARTUP, CHATTY_SONG_AWAKE
from chatty_config import NORMAL_EXIT, UPGRADE_EXIT

from typing import Any
import asyncio
import time

WAKE_UP_INSTRUCTIONS = "The user has just asked you to come online.  Provide a brief greeting please."
SUMMARY_INSTRUCTIONS = "You were talking to the user and then you went offline.  You are now back online.  Let them know you're back."

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
    except Exception as e:
        print(f"❌ Error in grand_central_dispatch: {e}")
        import traceback
        traceback.print_exc()

    return results


#
# kick off a listener for the mic and a player for the speaker.  then loop talking to the AI server
#
async def assistant_go_live():

    loop_forever = True
    just_rebooted = True

    master_state = ChattyMasterState()

    is_automated_restart_after_summary = False

    while loop_forever:

        # set up the managers:
        #     mic (output) -> voice detector (input)
        #     voice detector (output) -> assistant (input)
        #     assistant (output) -> speaker (input)
        managers = {"mic"     : AsyncManager("mic",       mic_listener                                       )}
        managers["assistant"] = AsyncManager("assistant", stream_to_assistant, managers["mic"].output_q,     )
        managers["speaker"]   = AsyncManager("speaker",   speaker_player,      managers["assistant"].output_q)

        # on mac, push to talk keyboard is used to start and stop the mic
        print("🎙️ Chatty Friend is ready")
        if master_state.system_type=="mac":
            from chatty_keyboard import listen_for_push_to_talk
            managers["keyboard"] = AsyncManager("keyboard", listen_for_push_to_talk)
            if not is_automated_restart_after_summary:
                print("💬 Press W to wake up")
            print("💬 hold SPACE to capture microphone")

        await master_state.start_tasks(managers)

        if is_automated_restart_after_summary:
            await setup_assistant_session(master_state, SUMMARY_INSTRUCTIONS)
            managers["mic"].command_q.put_nowait(ASSISTANT_RESUME_AFTER_AUTO_SUMMARY)
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
                            await master_state.add_to_transcript("system", await setup_assistant_session(master_state, WAKE_UP_INSTRUCTIONS))
                            await managers["speaker"].command_q.put(SPEAKER_PLAY_TONE+":"+CHATTY_SONG_AWAKE)
                        elif result == USER_STARTED_SPEAKING:
                            # within a session, user started speaking.stop audio that's already queued up

                            await assistant_session_cancel_audio(master_state)
                            # clear audio that's already downloaded but not played
                            await managers["speaker"].command_q.put(ASSISTANT_STOP_SPEAKING)

                if master_state.should_summarize:
                    break

            except KeyboardInterrupt:
                loop_forever = False

            except Exception as e:
                print(f"❌ Error in assistant_go_live: {e}")
                import traceback
                traceback.print_exc()

        # summary triggered - tell the top of the loop
        if master_state.should_summarize:
            master_state.should_summarize = False
            is_automated_restart_after_summary = True
        else:
            is_automated_restart_after_summary = False

        master_state.should_reset_session = False

        try:
            # drain any remaining audio
            deadman_audio_count = 0
            spkr = managers["speaker"]
            while any([q.qsize() > 0 for q in [spkr.command_q, spkr.input_q, spkr.output_q]]):
                await asyncio.sleep(0.1)
                deadman_audio_count += 1
                if deadman_audio_count > 100:
                    print("🔄 DEADMAN AUDIO COUNT > 100")
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
            import traceback
            traceback.print_exc()

    try:
        master_state.pa.terminate()
    except Exception as e:
        print("error in assistant_go_live outer loop cleanup")
        import traceback
        traceback.print_exc()


async def main():
    await assistant_go_live()

if __name__ == "__main__":
    asyncio.run(main())