# Chatty quick and dirty mac "push to talk" for QA
# Finley 2025

import time
import asyncio
from chatty_async_manager import AsyncManager
from chatty_config import USER_SAID_WAKE_WORD, PUSH_TO_TALK_START, PUSH_TO_TALK_STOP
import sys
import termios
import tty
import select

def inkey():
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())

        if select.select([sys.stdin], [], [], 0.05) == ([sys.stdin], [], []):
            return sys.stdin.read(1)

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

async def listen_for_push_to_talk(manager: AsyncManager):
    last_space_time = None
    mic_queue = manager.master_state.task_managers["mic"].input_q

    print("🎤 Keyboard listening for 'W' (wake word) or SPACE (HOLD space to talk).")
    
    # Set terminal to cbreak mode once at the start
    old_settings = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())
    
    try:
        while manager.command_q.empty():
            try:
                # Check for input without blocking
                if select.select([sys.stdin], [], [], 0.05) == ([sys.stdin], [], []):
                    key = sys.stdin.read(1)
                else:
                    key = None
                
                if key is None:            
                    if last_space_time is not None and time.time() - last_space_time > 0.5:
                        await mic_queue.put(PUSH_TO_TALK_STOP)
                        last_space_time = None
                else:
                    if key == ' ':
                        if last_space_time is None:
                            await mic_queue.put(PUSH_TO_TALK_START)
                        last_space_time = time.time()

                    if key == 'w':
                        await mic_queue.put(USER_SAID_WAKE_WORD)
                        
            except Exception as e:
                print(f"\nError in listen_for_push_to_talk: {e}")
            
            # Small delay to prevent tight loop
            await asyncio.sleep(0.05)
    except Exception as e:
        print(f"\nError in listen_for_push_to_talk: {e}")
    
    finally:
        # Restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

    print("🎤 listen_for_push_to_talk MASTER_EXIT_EVENT.")