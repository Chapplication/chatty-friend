from .llm_tool_base import LLMTool, LLMToolParameter

class MathTool(LLMTool):
    def __init__(self, master_state):
        expression = LLMToolParameter("expression","a math calculation to perform in pyton eval format that does not require any imports or packages", required=True)

        super().__init__("math_tool", 
                         "use this tool when the user asks to perform a math calculation",
                         [expression], 
                         master_state)
        
    async def invoke(self, args):
        try:
            res  = eval(args["expression"])
            return "The answer is "+str(res)

        except Exception as e:
            return f"The calculation failed: {str(e)}."
