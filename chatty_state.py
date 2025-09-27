from re import L
import threading
from typing import Any, Optional
from openai import AsyncOpenAI, OpenAI
import pyaudio
from chatty_tools import load_tool_config
from chatty_secrets import SecretsManager
from chatty_config import ConfigManager, ASSISTANT_GO_TO_SLEEP, SPEAKER_PLAY_TONE, CHATTY_SONG_SLEEP, OPENAI_SESSION_HARD_LIMIT_SECONDS, EMBEDDED_PHRASES
import platform
import time
from chatty_supervisor import report_conversation_to_supervisor
from chatty_realtime_messages import send_assistant_text_from_system
from chatty_embed import ChattyEmbed

DEBUGGING = True
PAUSING_FOR_SUMMARY_INSTRUCTIONS = "You're going offline for a moment.  let the user know you need a moment and will be back soon."

# singleton global state holder
class ChattyMasterState:
    
    _instance: Optional['ChattyMasterState'] = None
    _lock: threading.Lock = threading.Lock()
    
    def __new__(cls) -> 'ChattyMasterState':
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):

        # singleton
        if self._initialized:
            return
            
        # unprotected thread-safe state - only one thread should set!
        self.tool_dispatch_map = {}
        self.tools_for_assistant = []

        self.logs_for_next_summary = []

        self.should_quit = False
        self.should_upgrade = False
        self.should_reset_session = False
        self.should_summarize = False

        self.system_type = self.get_system_type()
        self.conman = ConfigManager()
        self.secrets_manager = SecretsManager()

        openai_api_key = self.secrets_manager.get_secret("chat_api_key")
        if not openai_api_key:

            raise Exception("No OpenAI API key found")

        self.openai = OpenAI(api_key=openai_api_key)
        self.async_openai = AsyncOpenAI(api_key=openai_api_key)
        self.pa = pyaudio.PyAudio()

        self._data_lock = threading.RLock()

        self.tool_dispatch_map, self.tools_for_assistant = load_tool_config(self)

        self._initialized = True

        self.semantic_matcher = ChattyEmbed(self, EMBEDDED_PHRASES)

    def add_log_for_next_summary(self, log):
        self.logs_for_next_summary.append(log)
        if len(self.logs_for_next_summary) > 100:
            self.logs_for_next_summary = self.logs_for_next_summary[-100:]
    def get_logs_for_next_summary(self):
        logs = self.logs_for_next_summary
        self.logs_for_next_summary = []
        return logs

    async def start_tasks(self, task_managers):
        await self.reset_session_state_variables()
        self.task_managers = task_managers
        for manager in self.task_managers.values():
            manager.start(self)

    def get_system_type(self):
        system = platform.system().lower()
        
        if system == 'darwin':
            return 'mac'
        elif system == 'linux':
            # Check if it's a Raspberry Pi
            try:
                with open('/proc/device-tree/model', 'r') as f:
                    if 'raspberry pi' in f.read().lower():
                        return 'raspberry_pi'
            except:
                pass
            
            # Alternative: Check CPU info
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    cpuinfo = f.read().lower()
                    if 'raspberry' in cpuinfo or 'bcm2' in cpuinfo:
                        return 'raspberry_pi'
            except:
                pass
                
            # Could be generic Linux
            return 'linux'
        else:
            return 'unknown'
        

    def debug(self, message):
        if DEBUGGING:
            # use single character messages to debug streams
            if len(message)==1:
                print(message,flush=True, end="")
            else:
                print(message)

    async def reset_session_state_variables(self):

        if hasattr(self, "transcript_history") and self.transcript_history:
            await report_conversation_to_supervisor(self)
            print(f"**** Total cost : ${sum([u['cost'] for u in self.usage_history]):0.2f} ***** ")   

        self.transcript_history = []
        self.usage_history = []
        self.logs_for_next_summary = []
        self.remote_assistant_state = {}
        self.ws = None
        self.last_activity_time = None

    def flow_control_event(self):
        return any([self.should_quit, self.should_upgrade, self.should_reset_session, self.should_summarize])

    def check_assistant_timeout(self):
        time_out = self.conman.get_config("AUTO_GO_TO_SLEEP_TIME_SECONDS") or self.conman.default_config.get("AUTO_GO_TO_SLEEP_TIME_SECONDS") or 3000
        if time_out>0 and self.last_activity_time is not None and time.time() - self.last_activity_time > time_out:
            self.dismiss_assistant("sleep")

    async def check_auto_summarize_n_messages(self):

        # auto summarize if transcript is too long; TODO should prob base on audio duration for token budget
        try:
            n = self.conman.get_config("AUTO_SUMMARIZE_EVERY_N_MESSAGES")
            n = max(int(n), 4)
        except:
            n = 30

        if self.transcript_history and self.transcript_history[-1]["role"] == "AI":
            ai_message_count = sum(1 for item in self.transcript_history if item["role"] == "AI")
            if ai_message_count % n == 0:
                self.do_auto_summarize()

    async def check_auto_summarize_time(self):
        if self.remote_assistant_state:
            if "socket_open_time" in self.remote_assistant_state:
                if time.time() - self.remote_assistant_state["socket_open_time"] > OPENAI_SESSION_HARD_LIMIT_SECONDS-60:
                    self.do_auto_summarize()

    async def do_auto_summarize(self):
        self.should_summarize = True
        await send_assistant_text_from_system(self, PAUSING_FOR_SUMMARY_INSTRUCTIONS)
        print("🔄 Automatic conversation summary")

    async def add_to_transcript(self, role, content):
        self.transcript_history.append({"role": role, "content": content})
        print(f"🔄 {role}: {content}")
        await self.check_auto_summarize_n_messages()

        # assistant is reluctant to react to "go to sleep" etc. so force embeddinging check
        if role == "user":
            embedding_match = self.semantic_matcher.match(content, thresh=0.5)
            if embedding_match:
                # only one embedding match action for now... expand as needed
                if embedding_match[0] in EMBEDDED_PHRASES:
                    self.dismiss_assistant()

    def accumulate_usage(self, cost):
        self.usage_history.append({"cost":cost})
        #print(f"Just spent ${cost:0.4f} on this response")
        #print(f"Total cost so far: ${sum([u['cost'] for u in self.usage_history]):0.2f}")

    def dismiss_assistant(self, action=None):
        if not action:
            action = "sleep"

        if action == "exit":
            print("❌ USER_REQUESTED_EXIT")
            self.should_quit = True
        elif action == "sleep" or action == "bye":
            print("💤 USER_REQUESTED_SLEEP")
            self.should_reset_session = True
        elif action == "upgrade":
            print("🔄 USER_REQUESTED_UPGRADE")
            self.should_upgrade = True

        self.task_managers["mic"].command_q.put_nowait(ASSISTANT_GO_TO_SLEEP)
        self.task_managers["speaker"].command_q.put_nowait(SPEAKER_PLAY_TONE+":"+CHATTY_SONG_SLEEP)

    # these are thread-safe setters and getters for shared global state that needs to be edited by multiple threads.  
    # not used as of 8/11/2025
    def safe_set(self, key: str, value: Any) -> None:
        with self._data_lock:
            setattr(self, key, value)
    
    def safe_get(self, key: str, default: Any = None) -> Any:
        with self._data_lock:
            return getattr(self, key, default)