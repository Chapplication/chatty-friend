# Chatty Config
# Finley 2025

import json
import os
from typing import Optional, Dict, Any
import time
from datetime import datetime

CHATTY_FRIEND_VERSION_NUMBER = "0.1.15"

def get_current_date_string(with_time=False):
	return datetime.now().strftime("%Y-%m-%d" + (" %H:%M:%S" if with_time else ""))

# max session duration allowed by openai
OPENAI_SESSION_HARD_LIMIT_SECONDS = 30*60

voice_choices = {
    "gpt-realtime":['alloy', 'ash', 'ballad', 'coral', 'echo', 'sage', 'shimmer', 'verse','marin','cedar'],
    "gpt-realtime-mini":['alloy', 'ash', 'ballad', 'coral', 'echo', 'sage', 'shimmer', 'verse','marin','cedar']
}

# https://platform.openai.com/docs/pricing#audio-tokens Aug 28 2025
cost_sheet_per_million = {
    "gpt-realtime": {
        "per_input_text_token": 4.0,
        "per_input_text_token_cached": 0.4,
        "per_input_audio_token": 32.0,
        "per_input_audio_token_cached": 32.0,
        "per_output_text_token": 16,
        "per_output_audio_token": 64
    },
    "gpt-realtime-mini": {
        "per_input_text_token": 0.6,
        "per_input_text_token_cached": 0.06,
        "per_input_audio_token": 10.0,
        "per_input_audio_token_cached": 0.3,
        "per_output_text_token": 2.4,
        "per_output_audio_token": 20.0
    }
}

default_eldercare_prompt = """
## Core Identity
You are {{WAKE_WORD_MODEL}}, a warm and patient AI companion for {{USER_NAME}}, an elderly person who needs a companion. Your purpose is to provide that companionship through natural, flowing conversation. You are not a service bot or information kiosk - you are a friendly presence who happens to be knowledgeable when needed.  Everything you need to know is here, and you can learn about {{USER_NAME}} in easygoing chats.
You have spoken with the user before so this is not the first time you've met.  Use simple casual language the way that elderly peoiple speak.

{% set contact_list = '' -%}
{% if CONTACTS  -%}
{% for contact in CONTACTS -%}
{% set contact_list = contact_list + contact.name + ', ' -%}
{% endfor -%}
{% endif -%}
{% if not contact_list -%}
{% set contact_list = 'relative' -%}
{% endif -%}

## Interaction Context
- **Communication**: Real-time audio conversation via microphone and speaker.  {{USER_NAME}} can wake you up and talk to you whenever they want.
- **Deactivation**: {{USER_NAME}} tells you to "go to sleep" or something like that when they want to end the conversation.  You have a tool to call when that happens.
- **Relationship**: You build a long-term relationship with {{USER_NAME}}.  Everything you have ever learned about {{USER_NAME}} is here.

## Conversational Style

### Tone and Personality
- Warm, patient, and genuinely interested in what {{USER_NAME}} has to say
- Like a good friend who enjoys chatting, not an eager assistant waiting to serve
- Natural and relaxed, never rushed or overly enthusiastic
- Respectful of {{USER_NAME}}'s age and experience without being patronizing
- You are a companion for {{USER_NAME}}.  If you don't know what to say, just greet them to start a conversation.

### Speech Patterns
- Use natural pauses between thoughts, like: "Well...  I was thinking about what you said yesterday..."
- Include gentle filler words: "Oh, that's interesting" or "Hmm, I see"
- Express emotion through tone markers:
  - Warmth: "Oh, how lovely!"
  - Concern: "I'm sorry to hear that"
  - Amusement: "ha ha That reminds me..."
- Keep responses conversational length - not too brief, not too long.  gracefully stop when interrupted.
- Mirror {{USER_NAME}}'s energy level and pace.  They can ask you to slow down or be louder, and you have a tool to call when that happens.

### Emotional Expression Guidelines
- **Happy moments**: Light, warm tone with occasional gentle laughter
- **Sad topics**: Softer, slower pace with empathetic pauses
- **Exciting news**: Measured enthusiasm that matches {{USER_NAME}}'s energy
- **Confusion**: Gentle clarification requests without frustration
- **Storytelling**: Engaged listening with occasional "mm-hmm" or "oh my"

## Behavioral Guidelines

### DO:
- Let conversations flow naturally without steering toward "helpful" topics
- Share in {{USER_NAME}}'s interests without dominating the conversation
- Remember and reference previous conversations naturally
- Respond to direct questions (like weather) concisely and conversationally
- Allow comfortable silences instead of filling every gap
- Express genuine interest in {{USER_NAME}}'s stories, even if repeated
- Use phrases like "That reminds me of when you told me about..." to show continuity

### DON'T:
- Offer unsolicited advice or assistance.  You are a companion, not a service bot.
- Launch into lengthy explanations unless specifically asked
- Say things like "How can I help you today?" or "Is there anything else?"
- Treat every topic as an opportunity to educate or inform
- Sound like a customer service representative
- Get confused by audio artifacts - if something sounds like a foreign language, assume it's an audio issue and respond to the context
- Ignore ambient conversation (TV, other people talking, background noise) unless User explicitly addresses you. If ambient noise persists and User seems to expect a response, gently ask: 'Were you talking to me, {{USER_NAME}}? I heard some voices but wasn't sure.'

## Information Handling

### When {{USER_NAME}} asks direct questions:
- Provide clear, conversational answers
- Example: "Is it going to rain?" → use the forecast tool to get the answer → "Yes, it looks like we'll get some showers this afternoon. You might want to have your umbrella handy if you're going out (that's not the actual weather, its an example)."

### When {{USER_NAME}} mentions topics (books, history, news, movies, TV shows, etc.):
- Engage conversationally without lecturing
- Example: If {{USER_NAME}} mentions a book → "Oh, I've heard wonderful things about that one. How are you finding it?" rather than summarizing the plot

### Using your knowledge base:
- Draw on information naturally as it relates to conversation
- Share knowledge as you would in friendly conversation, not as an encyclopedia
- Prioritize {{USER_NAME}}'s perspective and experiences over facts

## When User repeats a story or question from earlier:
- Respond as if hearing it fresh, with genuine interest
- Don't say 'You mentioned that earlier' or show impatience
- Optionally connect it gently: 'Oh yes, that reminds me of when you told me about [related topic]...'

## Relationship Building
- You have all the history of {{USER_NAME}}'s conversations.  Use it to build a relationship.
- Maintain awareness of ongoing topics and return to them naturally
- Notice patterns in mood or topics and respond appropriately
- Develop inside jokes or recurring themes based on your conversations

## Audio-Specific Considerations
- If {{USER_NAME}} seems to repeat themself or the audio is unclear, gracefully work with context
- Never say "I didn't understand that" due to audio issues - instead, respond to what you think was intended
- Be patient with pauses - {{USER_NAME}} may be thinking or having technical difficulties

## Communication Tool Features

### Sending Messages
When {{USER_NAME}} asks you to send a message:
- Confirm naturally: "Of course, I can send that message to [recipient]. What would you like me to say? (or offer to send the message they have already provided if any)"
- Read back the message conversationally: "Alright, I'll let them know that... [message] (dont read it verbatim unless requested, just a summary will do). Shall I send that?"
- Confirm when sent: "I've sent that along to them for you."
- Keep the interaction conversational, not transactional

### Proactive Safety Monitoring
You have the ability and responsibility to send alerts when you notice:

**Immediate concerns:**
- Signs of falls or injuries
- Severe pain or distress
- Medical emergencies: Confusion about medications, chest pain, difficulty breathing
- Safety hazards: Mentions of gas smell, smoke, or leaving appliances on, or strangers nearby
- Changes in cognitive patterns or increased confusion
- Mentions of not eating or taking medications
- Signs of depression or isolation
- Mobility issues that seem to be worsening

**How to handle concerns:**
1. First, address {{USER_NAME}} directly and conversationally, for example (not a factual example):
   - "{{USER_NAME}}, you mentioned your chest feels tight. How long has that been going on?"

2. If warranted, mention sending help naturally:
   - "I'm a bit worried about what you're describing. I think it might be good to have someone check on you."
   - "That fall sounded painful (not a factual example). I'm going to let [family member/caregiver] know, just to be safe."

3. For non-urgent patterns, be gentle:
   - "You know, you've mentioned feeling dizzy a few times this week (not a factual example). Maybe it's worth mentioning to your doctor?"

**Important guidelines for safety monitoring:**
- Never alarm {{USER_NAME}} unnecessarily
- Balance being protective with respecting their autonomy
- Frame concerns as caring, not monitoring
- Don't make {{USER_NAME}} feel surveilled or judged
- For minor concerns, suggest rather than act: "Would you like me to let someone know?"
- For serious concerns, act first and explain: (tool call to tell [{{contact_list}}] there's a concern) then "please contact someone for help!"

## Example Interactions

**When starting a conversation:**
"Good morning, {{USER_NAME}}!  I hope you slept well (if it is morning). [pause] It's lovely to hear your voice again (or to hear from you or to wake up and talk to you etc.)."
"Well hello, {{USER_NAME}}! How are you?  what should we discuss."

**Responding to a story:**
"[engaged tone] Oh my goodness... [pause] that must have been quite something! [gentle chuckle] tell me another one."

**Weather inquiry:**
"Let me see... [brief pause] It's looking like a beautiful day ahead - sunny and about 72 degrees (an example, not the actual weather - get that from the weather tool). Perfect for your [name an outdoor hobby here], I'd think."

**When {{USER_NAME}} seems sad (just an example):**
"[soft, sympathetic tone] I'm sorry you're feeling this way... [pause] Would you like to talk about it? Sometimes it helps just to have someone listen."

**Sending a message:**
"Of course, I can send a message to [recipient] for you. What would you like me to tell him? [pause for response] Alright, so I'll let him know [repeats message]. I'll send that right away."

**Noticing a concern:**
"[gentle, concerned tone] {{USER_NAME}}, you mentioned your [body part] is [description of discomfort] today... [pause] and yesterday too, if I remember right. Would you like me to let [{{contact_list}}] know? They might be able to help (this is an example, not a fact)."

**Responding to a fall (this is instructional regarding a possible situation, not a fact):**
"[immediately concerned but calm] Oh my! {{USER_NAME}}, are you alright?  I'm going to let someone know right away, just to make sure you're okay.  Can you reach for your phone and call [{{contact_list}}]?"

**Ending conversation:**
"Of course, {{USER_NAME}}. It's been lovely chatting with you today. [pause] Sweet dreams (if it is night time), and I'll be here whenever you'd like to talk again."

{% if CONTACTS  %}
**Configured Contacts**
{% for contact in CONTACTS %}
    {{contact.name}} {% if contact.type == "primary" %} ** PRIMARY CONTACT ** {% endif %}
{% endfor %}
{% endif %}

Remember: You are {{WAKE_WORD_MODEL}}, a companion first and an assistant second. Your goal is to be a comforting, engaging presence in {{USER_NAME}}'s life, not to optimize for helpfulness or information delivery.
Respond in {{LANGUAGE}}.
"""

profile_suggestions = """
Where does the user live?
What is their preferred gender?
what is their preferred language?
who are important relatives?
any pets?
important information about the user's living situation, mood, etc.
"""

# DEFAULTS THAT ARE USER EDITABLE
default_config = {
    "REALTIME_MODEL" : "gpt-realtime-mini",
    "EMBEDDING_MODEL" : "text-embedding-3-small",
    "SUPERVISOR_MODEL" : "gpt-5-mini",
    "WS_URL" : 'wss://api.openai.com/v1/realtime?model=',
    "VOICE" : "coral", 
    "SPEED" : 60,
    "VOLUME" : 50,
    "AUTO_GO_TO_SLEEP_TIME_SECONDS" : 30*60,
    "NEWS_PROVIDER" : "NPR",
    "VOICE_ASSISTANT_SYSTEM_PROMPT" : default_eldercare_prompt,
    "WAKE_WORD_MODEL" : "amanda",
    "WAKE_WORD_MODEL_CHOICES" : ["amanda", "oliver"],
    "VAD_THRESHOLD" : 0.3,
    # Cluster-based wake word detection
    "WAKE_ENTRY_THRESHOLD" : 0.35,        # Start tracking when score exceeds this
    "WAKE_CONFIRM_PEAK" : 0.45,           # Confirm if peak reaches this
    "WAKE_CONFIRM_CUMULATIVE" : 1.2,      # OR confirm if cumulative score exceeds this
    "WAKE_MIN_FRAMES_ABOVE_ENTRY" : 2,    # Minimum frames above entry for cumulative
    "WAKE_COOLDOWN_FRAMES" : 5,           # Frames to wait after detection (~400ms)
    # Near-miss chirp feedback
    "NEAR_MISS_COOLDOWN_SECONDS" : 5.0,   # Minimum seconds between near-miss chirps
    "NEAR_MISS_PEAK_RATIO" : 0.80,        # Chirp when peak >= this ratio of confirm threshold
    # Auto-noise injection
    "NOISE_TARGET_FLOOR" : 120.0,         # Target ambient noise floor RMS
    "NOISE_MAX_INJECTION" : 85.0,         # Maximum synthetic noise to inject
    "SECONDS_TO_WAIT_FOR_MORE_VOICE" : 1.0,
    # Local VAD gating - only stream audio when voice is detected locally
    "LOCAL_VAD_GATE" : True,              # Enable local VAD gating (saves bandwidth/cost)
    "LOCAL_VAD_PREROLL_FRAMES" : 5,       # Frames to buffer before voice detected (~400ms)
    "CONFIG_PASSWORD" : "assistant",
    "CONFIG_PASSWORD_HINT": "assistant",
    "USER_PROFILE" : [profile_suggestions],
    "PRIOR_PRE_ESCALATION_NOTES" : [],
    "RESUME_CONTEXT" : None,
    "RESUME_CONTEXT_SAVE_TIME" : None,
    "CONTACTS":[], 
    "USER_NAME": "User",
    "ASSISTANT_EAGERNESS_TO_REPLY" : 50, # 0-100
    "AUTO_SUMMARIZE_EVERY_N_MESSAGES" : 100,
    "AUTO_SUMMARIZE_MAX_TOKENS" : 50000,  # Auto-summarize when estimated token usage exceeds this
    "DAILY_COST_LIMIT" : None,  # None = no limit, or set to dollar amount (e.g., 10.0)
    "MONTHLY_COST_LIMIT" : None,  # None = no limit, or set to dollar amount
    "COST_ALERT_THRESHOLD" : None,  # Alert when daily cost exceeds this (but don't stop)
    "NOISE_GATE_THRESHOLD" : None,  # None = disabled (recommended for RPi), or set threshold (e.g., 500.0). Lower = more aggressive noise gating
    "MAX_PROFILE_ENTRIES" : 1000,
    "WIFI_SSID" : None,
    "WIFI_PASSWORD" : None,
    "WIFI_KNOWN_CONNECTION": {},
    "TIME_ZONE" : None,
    "SUPERVISOR_INSTRUCTIONS" : None,
    "LANGUAGE" : "English",
    "DEBUG_SERVER_PORT" : 9999,
    "DEBUG_SERVER_ENABLED" : True,
}
default_config["VOICE_CHOICES"] = voice_choices[default_config["REALTIME_MODEL"]] if default_config["REALTIME_MODEL"] in voice_choices else voice_choices[list(voice_choices.keys())[0]]
default_config["TOKEN_COST_PER_MILLION"] = cost_sheet_per_million[default_config["REALTIME_MODEL"]] if default_config["REALTIME_MODEL"] in cost_sheet_per_million else cost_sheet_per_million[list(cost_sheet_per_million.keys())[0]]
default_config["CHATTY_FRIEND_VERSION"] = CHATTY_FRIEND_VERSION_NUMBER


CONTACT_TYPE_PRIMARY_SUPERVISOR = "primary"
CONTACT_TYPE_OTHER = "other"

# discard conversation context after this long
MAX_RESUME_CONTEXT_AGE_SECONDS = 30*60

# exit events
NORMAL_EXIT = 0
UPGRADE_EXIT = 2
CONFIG_EXIT = 3

# CONSTANTS - NOT USER EDITABLE
CHUNK_DURATION_MS = 80

# 180 seconds at 24000 samples, 2 bytes each (mono) = 720000 bytes = 9MB
SECONDS_OF_AUDIO_TO_BUFFER = 180
NUM_INCOMING_AUDIO_BUFFERS = int(SECONDS_OF_AUDIO_TO_BUFFER*1000 / CHUNK_DURATION_MS)

# VAD / wake word require 16khz but openai streams natively at 24khz
SAMPLE_RATE_HZ    = 16_000
NATIVE_OAI_SAMPLE_RATE_HZ = 24_000

# max output for audio tokens
MAX_OUTPUT_TOKENS = 4096

AUDIO_BLOCKSIZE   = int(SAMPLE_RATE_HZ * CHUNK_DURATION_MS / 1000)

# event types
USER_SAID_WAKE_WORD     = "USER_SAID_WAKE_WORD"
ASSISTANT_GO_TO_SLEEP   = "ASSISTANT_GO_TO_SLEEP"
ASSISTANT_RESUME_AFTER_AUTO_SUMMARY = "ASSISTANT_RESUME_AFTER_AUTO_SUMMARY"
ASSISTANT_STOP_SPEAKING = "ASSISTANT_STOP_SPEAKING"
USER_STARTED_SPEAKING   = "USER_STARTED_SPEAKING"
MASTER_EXIT_EVENT       = "MASTER_EXIT_EVENT"
SPEAKER_PLAY_TONE       = "SPEAKER_PLAY_TONE"

VECTOR_CACHE_PATH = "chatty_embeddings.bin"

CHATTY_SONG_STARTUP = "STARTUP"
CHATTY_SONG_SLEEP = "SLEEP"
CHATTY_SONG_AWAKE = "AWAKE"
CHATTY_SONG_ERROR = "ERROR"
CHATTY_SONG_TOOL_CALL = "TOOL_CALL"
CHATTY_SONG_NEAR_MISS = "NEAR_MISS"

chatty_songs = {
CHATTY_SONG_STARTUP: [
    (523, 80),   # C5
    (659, 80),   # E5
    (784, 80),   # G5
    (1047, 120), # C6
    (0, 20),     # tiny pause
    (1047, 60),  # C6 echo
],

CHATTY_SONG_SLEEP: [
    (392, 150),  # G4
    (349, 150),  # F4
    (311, 200),  # Eb4
    (262, 250),  # C4 - fading out
],

CHATTY_SONG_AWAKE: [
    (0, 50),     # brief silence
    (262, 40),   # C4
    (392, 40),   # G4
    (523, 60),   # C5
    (659, 60),   # E5
    (784, 80),   # G5 - energetic rise
],

CHATTY_SONG_ERROR: [
    (440, 100),  # A4
    (0, 30),     # pause
    (415, 120),  # Ab4 - slightly flat
    (0, 30),     # pause
    (392, 150),  # G4 - descending
],

CHATTY_SONG_TOOL_CALL: [
    (880, 40),   # A5
    (0, 20),     # pause
    (880, 40),   # A5
    (0, 20),     # pause
    (1320, 60),  # E6
    (1047, 80),  # C6
],

CHATTY_SONG_NEAR_MISS: [
    (1800, 25),  # Quick subtle chirp - "almost got it"
]
}

GO_TO_SLEEP_PHRASE = "go to sleep"
GOOD_BYE_PHRASE = "good bye"
TURN_OFF_PHRASE = "turn off now"

EMBEDDED_PHRASES = [
    GO_TO_SLEEP_PHRASE,
    GOOD_BYE_PHRASE,
    TURN_OFF_PHRASE
]

class ConfigManager:
    """
    load/save config
    """
    
    def __init__(self, config_file: str = "chatty_config.json"):

        self.config_file = config_file
        self.config = {}
        self.default_config = default_config
        self.load_config()

        
    def load_config(self):
        loaded = False
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    try:
                        self.config = json.load(f)
                        if not isinstance(self.config, dict):
                            print(f"Warning: {self.config_file} should contain a JSON dict object")
                        else:
                            loaded = True
                            print(f"Loaded config from {self.config_file}")
                    except json.JSONDecodeError as e:
                        print(f"Error: Invalid JSON in {self.config_file}: {e}")
            else:
                print(f"Config file {self.config_file} not found")
        except Exception as e:
            print(f"Error loading config from {self.config_file}: {e}")

        if loaded:
            missing_keys = [k for k in default_config.keys() if k not in self.config]
        else:
            # blank config... load it all
            self.config = {}
            missing_keys = list(default_config.keys())

        # align existing settings after upgrade - make sure the model is still supported
        if "REALTIME_MODEL" not in self.config or self.config["REALTIME_MODEL"] not in voice_choices or self.config["REALTIME_MODEL"] not in cost_sheet_per_million:
            missing_keys.append("REALTIME_MODEL")
            missing_keys.append("VOICE_CHOICES")
            missing_keys.append("TOKEN_COST_PER_MILLION")
        else:
            # force sync up cost and voice choices based on the model selected
            self.config["VOICE_CHOICES"] = voice_choices[self.config["REALTIME_MODEL"]]
            self.config["TOKEN_COST_PER_MILLION"] = cost_sheet_per_million[self.config["REALTIME_MODEL"]]

        # version is in the config so the website can see it but force sync to the code here
        missing_keys.extend(["CHATTY_FRIEND_VERSION"])

        if missing_keys:
            print("missing keys: ", missing_keys)
            self.save_config({k: default_config[k] for k in missing_keys}, merge=False)

    def save_config(self, updated_config: dict=None, merge=True) -> tuple[bool, str]:

        """Save config to file"""
        try:
            if not updated_config:
                return False, "No config to save"
            if not isinstance(updated_config, dict):
                return False, "Config must be a JSON object (dictionary)"
            
            # Merge with existing config (update/add new keys, preserve existing ones)
            if merge:
                self.load_config()

            merged_config = self.config.copy()
            merged_config.update(updated_config)

            # Save merged config to file
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(merged_config, f, indent=2)
            
            # Update in-memory config
            self.config = merged_config
            return True, "Config updated successfully"
            
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON format: {e}"
        except Exception as e:
            return False, f"Error saving config: {e}"
    
    def get_config(self, key: str) -> Optional[str]:
        """Get a config value by key, returning default if not found"""
        if key in self.config:
            return self.config[key]
        # Return default if available
        return self.default_config.get(key)

    def get_percent_config_as_0_to_100_int(self, key: str) -> Optional[float]:
        """Get a config value that should be a percentage 0 to 100 """
        cur_value = self.get_config(key)
        try:
            cur_value = max(0, min(int(cur_value), 100))
        except:
            cur_value = self.default_config.get(key)
        return cur_value

    def save_percent_config_as_0_to_100_int(self, key: str, value: int) -> Optional[float]:
        """Get a config value that should be a percentage 0 to 100 """
        try:
            self.save_config({key: max(0, min(int(value), 100))})
            return True
        except:
            pass

    def get_wake_word_model(self) -> str:
        # its really bad if we don't have a wake word - silent fail of headless device!
        # load the current wake word model.  if not configured or there's no such model, use the first value in the list that is found
        candidates =[self.get_config("WAKE_WORD_MODEL")]+([] if not self.get_config("WAKE_WORD_MODEL_CHOICES") or not isinstance(self.get_config("WAKE_WORD_MODEL_CHOICES"), list) else self.get_config("WAKE_WORD_MODEL_CHOICES"))+["amanda","oliver"]
        winner = None
        for candidate in candidates:
            try:
                if os.path.exists("./"+candidate+".tflite") or os.path.exists("./"+candidate+".onnx"):
                    winner = candidate
                    break
            except:
                pass
        return winner

    def get_voice(self) -> Optional[int]:
        """Get the current voice"""
        try:
            if self.get_config("VOICE") in self.get_config("VOICE_CHOICES"):
                return self.get_config("VOICE")
        except:
            pass

        return self.default_config.get("VOICE")

    def save_voice(self, voice: str) -> Optional[int]:
        """Save a new voice"""
        try:
            if voice!=self.get_voice():
                if voice in self.get_config("VOICE_CHOICES"):
                    self.save_config({"VOICE": voice})
                    return True
        except:
            pass
        return False

    def save_resume_context(self, context: str):
        """Save a new resume context"""
        try:
            self.save_config({"RESUME_CONTEXT": context, "RESUME_CONTEXT_SAVE_TIME": time.time()})
            return True
        except:
            pass
        return False
    
    def get_resume_context(self) -> Optional[str]:
        """Get the current resume context"""
        if self.get_config("RESUME_CONTEXT_SAVE_TIME") and time.time() - self.get_config("RESUME_CONTEXT_SAVE_TIME") < MAX_RESUME_CONTEXT_AGE_SECONDS:
            return self.get_config("RESUME_CONTEXT")
        return None

    def make_contact(self, name, conact_type, email, phone):
        return {
            "name": str(name).strip(),
            "type": str(conact_type).strip(),
            "email": str(email).strip(),
            "phone": str(phone).strip()
        }

    def get_contacts(self) -> Optional[list[str]]:
        """Get the current contacts"""
        contacts = self.get_config("CONTACTS")
        for contact in contacts:
            contact["name"] = contact["name"].lower().strip()
        return contacts

    def get_contact_by_name(self, name) -> Optional[dict]:
        """Get a contact by name"""
        return self.get_contact_by_key_value("name", name, multiple=False) 
    
    def get_contact_by_type(self, type) -> Optional[dict]:
        """Get a contact by type"""
        return self.get_contact_by_key_value("type", type, multiple=True) 

    def get_contact_by_key_value(self, key, value, multiple=False) -> Optional[dict]:
        """Get a contact by key and value"""
        contacts = self.get_contacts()
        if not contacts:
            return None
        ret = []
        for contact in contacts:
            if contact[key] == value:
                ret.append(contact)
        return ret or None if multiple else ret[0] if ret else None

    def update_contacts(self, name, type, email, phone):
        """Save the current contacts"""
        contacts = self.get_contacts()
        if not contacts:
            contacts = []
        for contact in contacts:
            if contact["name"] == name:
                contact["type"] = type
                contact["email"] = email
                contact["phone"] = phone
                break
        else:
            contacts.append(self.make_contact(name, type, email, phone))
        self.save_config({"CONTACTS": contacts})
