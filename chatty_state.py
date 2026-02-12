from re import L
import threading
from typing import Any, Optional
from openai import AsyncOpenAI, OpenAI
import pyaudio
from chatty_tools import load_tool_config
from chatty_secrets import SecretsManager
from chatty_config import ConfigManager, ASSISTANT_GO_TO_SLEEP, SPEAKER_PLAY_TONE, CHATTY_SONG_SLEEP, OPENAI_SESSION_HARD_LIMIT_SECONDS, EMBEDDED_PHRASES
import asyncio
import platform
import time
from chatty_supervisor import report_conversation_to_supervisor
from chatty_realtime_messages import send_assistant_text_from_system
from chatty_embed import ChattyEmbed
from chatty_communications import chatty_send_email
from chatty_communications import chatty_send_email

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
        self.auto_summary_count = 0
        self.auto_summary_auto_resume_limit = 3
        
        # Cost tracking
        self.daily_cost_history = {}  # date_string -> total_cost
        self.monthly_cost_history = {}  # year-month -> total_cost
        self.last_cost_alert_date = None
        self.cost_alert_sent_today = False

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
            session_cost = sum([u['cost'] for u in self.usage_history])
            message_count = len(self.transcript_history)
            print(f"**** Total cost : ${session_cost:.2f} ***** ")
            
            # Reset cost alert flag for new day
            from chatty_config import get_current_date_string
            today = get_current_date_string()
            if self.last_cost_alert_date != today:
                self.cost_alert_sent_today = False
            
            # Supabase sync: try once, don't block on failure
            await self._sync_to_supabase(session_cost, message_count)

        self.transcript_history = []
        self.usage_history = []
        self.logs_for_next_summary = []
        self.remote_assistant_state = {}
        self.ws = None
        self.last_activity_time = None
    
    async def _sync_to_supabase(self, session_cost: float, message_count: int):
        """
        Sync usage stats and check for updates from Supabase.
        Try once at conversation end, fail silently if unsuccessful.
        """
        try:
            from chatty_supabase import get_supabase_manager
            
            supabase = get_supabase_manager(self.conman, self.secrets_manager)
            
            if not supabase.is_device_linked():
                return  # Not linked to Supabase, skip sync
            
            usage_stats = {
                "cost": session_cost,
                "message_count": message_count
            }
            
            # Try to sync - this pushes usage and checks for config/upgrade flags
            success, new_config, new_secrets = supabase.sync_at_conversation_end(
                usage_stats,
                self.conman.config if self.conman else None
            )
            
            if success:
                # Apply new config if received (cloud wins, volume stays local)
                if new_config:
                    print("☁️ Applying updated configuration from cloud")
                    self.conman.save_config(new_config)
                
                # Check for upgrade flag
                if supabase.check_upgrade_pending():
                    print("☁️ Upgrade pending - will trigger upgrade on next cycle")
                    self.should_upgrade = True
            
        except ImportError:
            # Supabase module not available, skip silently
            pass
        except Exception as e:
            # Log but don't fail - device operation is more important than sync
            print(f"☁️ Supabase sync skipped: {e}")

    def flow_control_event(self):
        return any([self.should_quit, self.should_upgrade, self.should_reset_session, self.should_summarize])

    def check_assistant_timeout(self):
        time_out = self.conman.get_config("AUTO_GO_TO_SLEEP_TIME_SECONDS") or self.conman.default_config.get("AUTO_GO_TO_SLEEP_TIME_SECONDS") or 3000
        if time_out>0 and self.last_activity_time is not None and time.time() - self.last_activity_time > time_out:
            self.dismiss_assistant("sleep")

    async def check_auto_summarize_n_messages(self):
        """Check if we should auto-summarize based on token usage or message count"""
        # Check token-based summarization first (more accurate)
        if hasattr(self, 'usage_history') and self.usage_history:
            # Estimate total tokens used so far
            # Rough estimate: 1 audio token ≈ 0.6 seconds of audio, 1 text token ≈ 4 characters
            # We track costs, so we can estimate tokens from costs
            try:
                total_cost = sum([u.get("cost", 0) for u in self.usage_history])
                cost_sheet = self.conman.get_config("TOKEN_COST_PER_MILLION")
                if cost_sheet:
                    # Estimate tokens: cost / (cost_per_million / 1_000_000)
                    # Use average of input and output token costs
                    avg_input_cost = (cost_sheet.get("per_input_text_token", 0) + 
                                     cost_sheet.get("per_input_audio_token", 0)) / 2_000_000
                    avg_output_cost = (cost_sheet.get("per_output_text_token", 0) + 
                                      cost_sheet.get("per_output_audio_token", 0)) / 2_000_000
                    # Rough split: 60% input, 40% output
                    estimated_tokens = int((total_cost * 0.6 / avg_input_cost) + (total_cost * 0.4 / avg_output_cost))
                    
                    # Auto-summarize if we've used more than ~50k tokens (roughly $0.50-1.00 depending on model)
                    max_tokens_before_summary = self.conman.get_config("AUTO_SUMMARIZE_MAX_TOKENS")
                    if max_tokens_before_summary is None:
                        max_tokens_before_summary = 50000  # default
                    
                    if estimated_tokens > max_tokens_before_summary:
                        print(f"🔄 Auto-summarizing due to token usage: ~{estimated_tokens} tokens")
                        await self.do_auto_summarize()
                        return
            except Exception as e:
                print(f"⚠️ Error in token-based summarization check: {e}")
        
        # Fallback to message-based summarization
        try:
            n = self.conman.get_config("AUTO_SUMMARIZE_EVERY_N_MESSAGES")
            n = max(int(n), 4)
        except:
            n = 30

        if self.transcript_history and self.transcript_history[-1]["role"] == "AI":
            ai_message_count = sum(1 for item in self.transcript_history if item["role"] == "AI")
            if ai_message_count % n == 0:
                await self.do_auto_summarize()

    async def check_auto_summarize_time(self):
        if self.remote_assistant_state:
            if "session_open_time" in self.remote_assistant_state:
                if time.time() - self.remote_assistant_state["session_open_time"] > OPENAI_SESSION_HARD_LIMIT_SECONDS-60:
                    self.do_auto_summarize()

    async def do_auto_summarize(self):
        self.auto_summary_count += 1
        self.should_summarize = True
        await send_assistant_text_from_system(self, PAUSING_FOR_SUMMARY_INSTRUCTIONS)
        print("🔄 Automatic conversation summary")

    async def add_to_transcript(self, role, content):
        self.transcript_history.append({"role": role, "content": content})
        print(f"🔄 {role}: {content}")
        await self.check_auto_summarize_n_messages()

        # assistant is reluctant to react to "go to sleep" etc. so force embedding check
        # as a FALLBACK.  We delay the check to give the assistant time to handle the
        # command via tool call first (e.g. GoToSleepTool with action="upgrade").
        # If the assistant already dismissed by the time we check, we skip.
        if role == "user":
            asyncio.get_event_loop().call_later(
                5.0, self._deferred_embedding_check, content
            )

    def _deferred_embedding_check(self, content):
        """Run embedding match after a delay, but only if the assistant hasn't already
        handled the command via a tool call (e.g. GoToSleepTool).  This makes the
        embedding check a true fallback rather than a race with the tool path."""
        if self.should_quit or self.should_upgrade or self.should_reset_session:
            return  # assistant already handled it
        embedding_match = self.semantic_matcher.match(content, thresh=0.5)
        if embedding_match:
            if embedding_match[0] in EMBEDDED_PHRASES:
                self.dismiss_assistant()

    def accumulate_usage(self, cost):
        self.usage_history.append({"cost":cost})
        #print(f"Just spent ${cost:0.4f} on this response")
        #print(f"Total cost so far: ${sum([u['cost'] for u in self.usage_history]):0.2f}")
        
        # Update daily and monthly cost tracking
        from chatty_config import get_current_date_string
        today = get_current_date_string()
        month_key = today[:7]  # YYYY-MM
        
        if today not in self.daily_cost_history:
            self.daily_cost_history[today] = 0.0
        self.daily_cost_history[today] += cost
        
        if month_key not in self.monthly_cost_history:
            self.monthly_cost_history[month_key] = 0.0
        self.monthly_cost_history[month_key] += cost
        
        # Check cost limits and alerts
        self.check_cost_limits()

    def check_cost_limits(self):
        """Check daily/monthly cost limits and send alerts if needed"""
        from chatty_config import get_current_date_string
        import asyncio
        
        today = get_current_date_string()
        daily_cost = self.daily_cost_history.get(today, 0.0)
        month_key = today[:7]
        monthly_cost = self.monthly_cost_history.get(month_key, 0.0)
        
        daily_limit = self.conman.get_config("DAILY_COST_LIMIT")
        monthly_limit = self.conman.get_config("MONTHLY_COST_LIMIT")
        alert_threshold = self.conman.get_config("COST_ALERT_THRESHOLD")
        
        # Check daily limit
        if daily_limit is not None and daily_cost >= daily_limit:
            print(f"⚠️ Daily cost limit reached: ${daily_cost:.2f} >= ${daily_limit:.2f}")
            self.add_log_for_next_summary(f"⚠️ Daily cost limit reached: ${daily_cost:.2f}")
            # Don't auto-pause, but log it - user can configure behavior if needed
        
        # Check monthly limit
        if monthly_limit is not None and monthly_cost >= monthly_limit:
            print(f"⚠️ Monthly cost limit reached: ${monthly_cost:.2f} >= ${monthly_limit:.2f}")
            self.add_log_for_next_summary(f"⚠️ Monthly cost limit reached: ${monthly_cost:.2f}")
        
        # Check alert threshold (only alert once per day)
        if alert_threshold is not None and daily_cost >= alert_threshold:
            if not self.cost_alert_sent_today or self.last_cost_alert_date != today:
                print(f"💰 Cost alert: Daily cost ${daily_cost:.2f} exceeds threshold ${alert_threshold:.2f}")
                self.add_log_for_next_summary(f"💰 Cost alert: Daily cost ${daily_cost:.2f}")
                self.cost_alert_sent_today = True
                self.last_cost_alert_date = today
                
                # Send email alert to primary contact if configured
                supervisor_contact = self.conman.get_contact_by_type("primary")
                if supervisor_contact and hasattr(self, 'secrets_manager') and self.secrets_manager.has_email_configured():
                    try:
                        # Use asyncio to send email (if we're in an async context)
                        loop = None
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        
                        if loop and not loop.is_closed():
                            for supervisor in supervisor_contact:
                                if supervisor and supervisor.get("email"):
                                    subject = f"Chatty Friend Cost Alert - ${daily_cost:.2f} today"
                                    message = f"Daily cost has reached ${daily_cost:.2f}, exceeding the alert threshold of ${alert_threshold:.2f}.\n\n"
                                    message += f"Monthly cost so far: ${monthly_cost:.2f}\n"
                                    if daily_limit:
                                        message += f"Daily limit: ${daily_limit:.2f}\n"
                                    if monthly_limit:
                                        message += f"Monthly limit: ${monthly_limit:.2f}\n"
                                    
                                    # Schedule email send
                                    asyncio.create_task(chatty_send_email(self, supervisor["email"], subject, message))
                    except Exception as e:
                        print(f"⚠️ Error sending cost alert email: {e}")

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
