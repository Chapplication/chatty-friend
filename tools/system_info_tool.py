from .llm_tool_base import LLMTool, LLMToolParameter
import socket

class SystemInfoTool(LLMTool):
    def __init__(self, master_state):
        super().__init__("version_and_ip_address", "Use this tool when the user asks for version information or IP configuration", [], master_state)
        
    def what_is_my_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        try:
            # doesn't even have to be reachable
            s.connect(('10.254.254.254', 1))
            IP = s.getsockname()[0]
        except Exception as e:
            print(f"Warning: Error getting IP address: {e}")
            IP = None
        finally:
            s.close()
        return IP

    async def invoke(self, args):
        return f"Chatty Friend Configuration is accessible by pointing a browser at IP address is {self.what_is_my_ip()}.  The current version of Chatty Friend is  {self.master_state.conman.get_config('VERSION')}"
