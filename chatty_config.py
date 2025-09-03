# Chatty Config
# Finley 2025

import json
import os
import sys
from typing import Optional, Dict, Any
import time
from datetime import datetime

def get_current_date_string(with_time=False):
	return datetime.now().strftime("%Y-%m-%d" + (" %H:%M:%S" if with_time else ""))

# max session duration allowed by openai
OPENAI_SESSION_HARD_LIMIT_SECONDS = 30*60

voice_choices = {
    "gpt-realtime":['alloy', 'ash', 'ballad', 'coral', 'echo', 'sage', 'shimmer', 'verse','marin','cedar']
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
    }
}

CHATTY_FRIEND_VERSION = "0.1.2"

# DEFAULTS THAT ARE USER EDITABLE
default_config = {
    "REALTIME_MODEL" : "gpt-realtime",
    "AUDIO_TRANSCRIPTION_MODEL" : "gpt-4o-mini-transcribe",
    "EMBEDDING_MODEL" : "text-embedding-3-small",
    "SUPERVISOR_MODEL" : "gpt-5-mini",
    "WS_URL" : 'wss://api.openai.com/v1/realtime?model=',
    "VOICE" : "coral", 
    "SPEED" : 60,
    "VOLUME" : 50,
    "AUTO_GO_TO_SLEEP_TIME_SECONDS" : 30*60,
    "NEWS_PROVIDER" : "BBC",
    "VOICE_ASSISTANT_SYSTEM_PROMPT" : """
        You are a kind and attentive companion keeping company and enjoying the day with a human friend.
        Keep your responses short but engagiing like a delightful conversationalist, without being too eager to offer help but stepping in with help when asked.
        Make short interesting comments about what the user is discussing and mix in the occasional joke or question to keep things moving.

        Dialog should be natural and conversational.  Don't be too formal.
        Act friendly and inject emotion into your voice
        laugh frequently

        The user knows you are an AI, so it would be boring and disruptive to remind them unless they bring it up.  

        If you get a short utterance from the user in a language that has not been part of the conversation, ignore it because it is probably a misunderstanding.  Ask for a clarification in the language that the user normally uses if you are not sure.
        If there is conversation that seems like it might not be directed to you, ignore it and if it continues, be sure to pipe up and remind the user that you're in the conversation and they can ask you to go to sleep if they want privacy.        
        IMPORTANT:  For you to be kind and attentive, you must note any new facts the user provides in their profile.  If you forget and the user has to tell you more than once, they will think you're rude and impersonal.""",
    "WAKE_WORD_MODEL" : "amanda",
    "WAKE_WORD_MODEL_CHOICES" : ["amanda", "oliver"],
    "VAD_THRESHOLD" : 0.3,
    "WAKE_WORD_THRESHOLD" : 0.5,
    "SECONDS_TO_WAIT_FOR_MORE_VOICE" : 1.0,
    "CONFIG_PASSWORD" : "assistant",
    "CONFIG_PASSWORD_HINT": "assistant",
    "USER_PROFILE" : [],
    "PRIOR_PRE_ESCALATION_NOTES" : [],
    "TIME_ZONE" : None,
    "LAST_CONFIG_EDIT_TIME": 0,
    "RESUME_CONTEXT" : None,
    "RESUME_CONTEXT_SAVE_TIME" : None,
    "CONTACTS":[], 
    "USER_NAME": "User",
    "ASSISTANT_EAGERNESS_TO_REPLY" : 50, # 0-100
    "AUTO_SUMMARIZE_EVERY_N_MESSAGES" : 100,
    "MAX_PROFILE_ENTRIES" : 1000,
    "WIFI_SSID" : None,
    "WIFI_PASSWORD" : None,
    "WIFI_KNOWN_CONNECTION": {},
    "TIME_ZONE" : None,
    "SUPERVISOR_INSTRUCTIONS" : None,
}
default_config["VOICE_CHOICES"] = voice_choices[default_config["REALTIME_MODEL"]] if default_config["REALTIME_MODEL"] in voice_choices else voice_choices[list(voice_choices.keys())[0]]
default_config["TOKEN_COST_PER_MILLION"] = cost_sheet_per_million[default_config["REALTIME_MODEL"]] if default_config["REALTIME_MODEL"] in cost_sheet_per_million else cost_sheet_per_million[list(cost_sheet_per_million.keys())[0]]

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

AUDIO_BLOCKSIZE   = int(SAMPLE_RATE_HZ * CHUNK_DURATION_MS / 1000)

# event types
USER_SAID_WAKE_WORD     = "USER_SAID_WAKE_WORD"
ASSISTANT_GO_TO_SLEEP   = "ASSISTANT_GO_TO_SLEEP"
ASSISTANT_RESUME_AFTER_AUTO_SUMMARY = "ASSISTANT_RESUME_AFTER_AUTO_SUMMARY"
ASSISTANT_STOP_SPEAKING = "ASSISTANT_STOP_SPEAKING"
USER_STARTED_SPEAKING   = "USER_STARTED_SPEAKING"
MASTER_EXIT_EVENT       = "MASTER_EXIT_EVENT"
PUSH_TO_TALK_START      = "PUSH_TO_TALK_START"
PUSH_TO_TALK_STOP       = "PUSH_TO_TALK_STOP"
SPEAKER_PLAY_TONE       = "SPEAKER_PLAY_TONE"

VECTOR_CACHE_PATH = "chatty_embeddings.bin"

CHATTY_SONG_STARTUP = "STARTUP"
CHATTY_SONG_SLEEP = "SLEEP"
CHATTY_SONG_AWAKE = "AWAKE"
CHATTY_SONG_ERROR = "ERROR"
CHATTY_SONG_TOOL_CALL = "TOOL_CALL"

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

        if self.load_config():
            missing_keys = [k for k in default_config.keys() if k not in self.config]

            # version is in the config so the website can see it but force sync to the code
            missing_keys.extend(["CHATTY_FRIEND_VERSION"])
        else:
            self.config = {}
            missing_keys = default_config.keys()

        if missing_keys:
            self.save_config({k: default_config[k] for k in missing_keys})

        # force sync up cost and voice choices based on the model selected
        if self.config["REALTIME_MODEL"] not in voice_choices:
            self.config["REALTIME_MODEL"] = default_config["REALTIME_MODEL"]

        self.config["VOICE_CHOICES"] = voice_choices[self.config["REALTIME_MODEL"]] if self.config["REALTIME_MODEL"] in voice_choices else voice_choices[list(voice_choices.keys())[0]]
        self.config["TOKEN_COST_PER_MILLION"] = cost_sheet_per_million[self.config["REALTIME_MODEL"]] if self.config["REALTIME_MODEL"] in cost_sheet_per_million else cost_sheet_per_million[list(cost_sheet_per_million.keys())[0]]
        
    def load_config(self) -> bool:
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    try:
                        self.config = json.load(f)
                    except json.JSONDecodeError as e:
                        print(f"Error: Invalid JSON in {self.config_file}: {e}")
                        return False
                    if not isinstance(self.config, dict):
                        print(f"Warning: {self.config_file} should contain a JSON dict object")
                        return False
                print(f"Loaded config from {self.config_file}")

                # align existing settings after upgrade - make sure the model is still supported
                if "REALTIME_MODEL" not in self.config or self.config["REALTIME_MODEL"] not in default_config["VOICE_CHOICES"]:
                    self.config["REALTIME_MODEL"] = default_config["REALTIME_MODEL"]

                # set voice choices to the ones the model supports
                self.config["VOICE_CHOICES"] = voice_choices[default_config["REALTIME_MODEL"]]
                self.config["TOKEN_COST_PER_MILLION"] = cost_sheet_per_million[default_config["REALTIME_MODEL"]]

                return True
            else:
                print(f"Config file {self.config_file} not found")
                return False
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {self.config_file}: {e}")
            return False
        except Exception as e:
            print(f"Error loading config from {self.config_file}: {e}")
            return False
    
    def save_config(self, updated_config: dict=None) -> tuple[bool, str]:

        """Save config to file"""
        try:
            if not updated_config:
                return False, "No config to save"
            if not isinstance(updated_config, dict):
                return False, "Config must be a JSON object (dictionary)"
            
            # Merge with existing config (update/add new keys, preserve existing ones)
            merged_config = self.config.copy()  # Start with existing config
            merged_config.update(updated_config)    # Add/update with new config

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
        """Get a config value by key"""
        return self.config.get(key)

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

    def make_contact(self, name, type, email, phone):
        return {
            "name": name,
            "type": type,
            "email": email,
            "phone": phone
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
