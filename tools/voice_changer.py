from .llm_tool_base import LLMTool, LLMToolParameter

class VoiceChanger(LLMTool):
    def __init__(self, master_state):
        setting_type = LLMToolParameter("setting_type","'volume' to change audio volume or 'speed' to change speech rate or 'voice' to change the voice", enum=["volume", "speed", "voice"], required=True)
        new_value = LLMToolParameter("new_value","The desired new value as a percentage (10-100) for volume or speed or the voice to change to if provided", required=False)
        direction = LLMToolParameter("direction","'up' to increase or 'down' to decrease speed or volume by 10%. 'next' or 'previous' to change voices.  Only used when new_value is not provided.", enum=["up", "down"], required=False)
        go_back = LLMToolParameter("go_back","if the user specifically says they want to go back or undo the last change, set this to 'yes' otherwise set it to 'no'", required=True)
        super().__init__("voice_changer", "Use this function change the volume, speed or voice of the assistant", [setting_type,new_value,direction,go_back], master_state)

        self.prior_voice = master_state.conman.get_voice()
        self.prior_volume = master_state.conman.get_percent_config_as_0_to_100_int("VOLUME")
        self.prior_speed = master_state.conman.get_percent_config_as_0_to_100_int("SPEED")

    def new_setting_for_key(self, key: str, prior_value: int, go_back: bool, new_value: str, direction: str) -> int:
        current_value = self.master_state.conman.get_percent_config_as_0_to_100_int(key)
        if go_back:
            new_value = prior_value
        elif direction in ["up","down"]:
            new_value = max(0,min(current_value + 10 if direction=="up" else current_value - 10,100))
        if self.master_state.conman.save_percent_config_as_0_to_100_int(key,new_value):
            return current_value
        else:
            return None


    async def invoke(self, args):
        try:
            go_back = args.get("go_back","no").lower()=="yes"
            new_value = args.get("new_value","").lower()
            direction = args.get("direction","").lower()
            setting_type = args.get("setting_type","").lower()

            if setting_type == "voice":
                current_voice = self.master_state.conman.get_voice()
                if go_back:
                    new_value = self.prior_voice
                elif new_value:
                    new_value = new_value.lower()
                elif direction in ["next","previous"]:
                    voice_choices = self.master_state.conman.get_config("VOICE_CHOICES")
                    if current_voice in voice_choices:
                        next_voice_index = (voice_choices.index(current_voice)+1 if direction=="next" else -1)%len(voice_choices)
                        new_value = voice_choices[next_voice_index]
                else:
                    return f"Error changing voice.  Incorrect parameters. Please try again."

                if self.master_state.conman.save_voice(new_value):
                    self.prior_voice = current_voice
                else:
                    return f"Error changing voice: {str(e)}. Please try again."
            else:
                new_value = self.new_setting_for_key(setting_type.upper(),self.prior_volume if setting_type=="volume" else self.prior_speed,go_back,new_value,direction)
                if new_value is not None:
                    if setting_type=="volume":
                        self.prior_volume = new_value
                    else:
                        self.prior_speed = new_value
                else:
                    return f"Error changing {setting_type}: {str(e)}. Please try again."
        except Exception as e:
            return f"Error changing voice: {str(e)}. Please try again."

        return f"Let the user know that the change will take effect next time the assistant is goes to sleep and wakes up. Successfully changed {setting_type} to {new_value} on next wake event."