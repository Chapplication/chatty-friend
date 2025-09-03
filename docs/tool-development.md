# Tool Development Guide

This guide explains how to create custom tools for Chatty Friend, extending its capabilities to better serve seniors.

## Understanding Tools

Tools are Python modules that give Chatty Friend new abilities. When a user asks something like "What's the weather?" or "Send a message to my daughter", tools handle these requests.

## Tool Architecture

```
User speaks → OpenAI processes → Identifies tool needed → Tool executes → Response spoken
```

### Base Tool Class

All tools inherit from `LLMTool` in tools/llm_tool_base.py

## Creating Your First Tool

Let's build a medication reminder tool as an example:

### Step 1: Create the Tool File

Create `tools/joker_tool.py`:

```python
from .llm_tool_base import LLMTool, LLMToolParameter

class JokerTool(LLMTool):
    def __init__(self, master_state):
        joke_subject = LLMToolParameter("subject","what's the joke supposed to be about?  if not specified just say 'whatever'.", required=True)
        joke_length = LLMToolParameter("length","length of the joke.  one of 'short' or 'long'")

        super().__init__("joke_writer_tool", 
                         "use this tool when the user asks for a joke",
                         [joke_subject, joke_length], 
                         master_state)
        
    async def invoke(self, args):
        try:
            subject = args.get("subject") or "whatever"
            length = args.get("length") or "short"

            # make sure we have a model
            if master_state.async_openai and master_state.conman.get_config("SUPERVISOR_MODEL"):

                # optimistic invoke for demo tool
                return await master_state.async_openai.responses.create(
                    model=master_state.conman.get_config("SUPERVISOR_MODEL"),
                    reasoning={"effort": "low"},
                    instructions="light hearted and whimsical",
                    input=f"Make a {length} joke about {subject} to entertain the user please."
                ).output_text

        except Exception as e:
            print("Joker tool exception "+str(e))

        # fallback 
        return "Why did the chicken cross the road?  To get to the other side"

```

### Step 2: Register the Tool

Add your tool to `chatty_tools.py`:

```python
# Import your new tool
from tools.joker_tool import JokerTool

# In the get_tools() function, add:
tools.append(JokerTool(master_state))
```

### Step 3: Test Your Tool

Test conversation examples:
- "Can you tell me a long joke about two fighting cats"
- "tell me a knock knock joke"

## Best Practices

### 1. Error Handling

Always handle potential errors gracefully - whatever you return from the invoke() method will be proivided to the Chatty Friend so it can be shared with the user.

### 2. Validation

Validate inputs to prevent confusion:

```python
def validate_time(self, time_str: str) -> bool:
    """Ensure time is in a format seniors understand"""
    # Accept formats like "9 AM", "9:00 AM", "morning"
    pass
```

### Common Issues
1. **Tool not being called**
   - The function name matters a LOT.  In the example above, you can see where this is set to "joke_writer_tool" as the first parameter to super().__init__("joke_writer_tool",...)
   - Verify parameter descriptions are clear.  Are you expecting text or a structure like XML or json?  one value or many?
   - Ensure tool is registered in chatty_tools.py

2. **Parameters missing**
   - Mark required parameters in metadata
   - Provide defaults for optional params
   - Add validation with helpful errors

3. **Response not spoken**
   - make sure your invoke() function is returning a string
   - Keep messages conversational
   - Avoid technical jargon

## Contributing Your Tool

1. Ensure it follows best practices
2. Add documentation in the tool file
3. Include example conversations
4. Test with various phrasings
5. Submit PR with clear description

Remember: The best tools are those that make life easier and safer for seniors!