# Chatty Tools
# Finley 2025

import json
from chatty_config import SPEAKER_PLAY_TONE, CHATTY_SONG_TOOL_CALL


#
#  Model Context Tools
#

def load_tool_config(master_state):

    tool_dispatch_map = {}

    model_tools = []

    from tools.google_search import GoogleSearch
    from tools.go_to_sleep_tool import GoToSleepTool
    from tools.get_date_time import GetDateTime
    from tools.news_service import NewsService
    from tools.research_topic import ResearchTopic
    from tools.voice_changer import VoiceChanger
    from tools.weather_service import WeatherService
    from tools.chatty_math import MathTool
    from tools.communication_tool import CommunicationTool
    from tools.system_info_tool import SystemInfoTool
    installed_tools = [
        GoogleSearch(master_state),
        GoToSleepTool(master_state),
        GetDateTime(master_state),
        NewsService(master_state),
        ResearchTopic(master_state),
        VoiceChanger(master_state),
        WeatherService(master_state),
        MathTool(master_state),
        CommunicationTool(master_state),
        SystemInfoTool(master_state),
    ]

    for new_tool in installed_tools:
        if new_tool.can_invoke():
            model_tools.append(new_tool)
            tool_dispatch_map[new_tool.name] = new_tool.invoke
    
    return tool_dispatch_map, model_tools

async def dispatch_tool_call(event, master_state):
    """
    Dispatch a tool call to the appropriate tool.
    """
    tool_name = event.get("name")
    tool_arguments = json.loads(event.get("arguments", "{}"))
    ret = None
    if tool_name in master_state.tool_dispatch_map:
        try:
            print("🔧",tool_name, tool_arguments, ret)
            master_state.task_managers["speaker"].command_q.put_nowait(SPEAKER_PLAY_TONE+":"+CHATTY_SONG_TOOL_CALL)
            ret = await master_state.tool_dispatch_map[tool_name](tool_arguments)
        except Exception as e:
            import traceback
            traceback.print_exc()
            ret = f"Tool {tool_name} exception: {str(e)}"
    else:
        ret = f"Tool {tool_name} not found"

    print(ret[:100])
    return ret
