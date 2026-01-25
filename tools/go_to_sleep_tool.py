from .llm_tool_base import LLMTool, LLMToolParameter

description = """Use this tool when the user asks the assistant to take any one of the allowed actions:
- 'sleep' - the user asks the assistant anything like "go to sleep" or "take a nap".  Note that "stop" is NOT a sleep command, its just part of conversation but if the user says "I would like to stop our conversation now" that's like saying go to sleep.
- 'bye' - the user says bye or good bye or goodbye or anything like that.
- 'exit' - the user specifically instructs the assistant to exit.
- 'upgrade' - the user asks the assistant to check for updates, get a new version, perform an upgrade, or anything like that.
"""

class GoToSleepTool(LLMTool):
    def __init__(self, master_state):
        action = LLMToolParameter("action","which of the available actions is the user requesting", enum=["exit", "sleep", "bye", "upgrade"], required=True)

        super().__init__("sleep_or_bye_tool", 
                         description,
                         [action], 
                         master_state)
        
    async def invoke(self, args):
        try:
            args["action"] = args.get("action","sleep").lower()
            self.master_state.dismiss_assistant(args["action"])
            return "OK"
                
        except Exception as e:
            return f"sleep exception: {str(e)}."
