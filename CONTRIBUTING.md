# Contributing to Chatty Friend

First off, thank you for considering contributing to Chatty Friend! It's people like you that help make Chatty Friend a better companion for seniors.

## Code of Conduct

By participating in this project, you are expected to uphold our simple code: be kind, be respectful, and remember that this project aims to help seniors stay connected.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When you create a bug report, include:

- **Clear descriptive title**
- **Steps to reproduce** (1... 2... 3...)
- **Expected vs actual behavior**
- **System information** (OS, Python version, Pi model if applicable)
- **Logs** if available (check `sudo journalctl -u start_chatty.service`)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, include:

- **Clear descriptive title**
- **Step-by-step description** of the suggested enhancement
- **Explain why** this would be useful for seniors
- **Examples** of how it would work

### Pull Requests

1. **Fork** the repo and create your branch from `main`
2. **Name your branch** descriptively (e.g., `add-medication-reminder-tool`)
3. **Test your changes** on both macOS (development) and Raspberry Pi if possible
4. **Update documentation** as needed
5. **Write clear commit messages**
6. **Create the Pull Request** with a clear title and description

## Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/your-username/chatty-friend.git
   cd chatty_friend
   ```

2. Create virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Copy configuration templates:
   ```bash
   cp chatty_secrets.example.json chatty_secrets.json
   # Add your OpenAI API key
   ```

4. Run in development mode:
   ```bash
   python chatty_friend.py
   ```

## Creating New Tools

Tools extend Chatty Friend's capabilities. To create a new tool:

1. Create a new file in `tools/` directory
2. Inherit from `LLMTool` base class
3. Implement required methods:
   - `can_invoke()` - Returns True if this tool handles the function
   - `invoke()` - Executes the tool functionality
   - `get_model_function_call_metadata()` - Describes the tool for the AI

Example tool structure:
```python
from tools.llm_tool_base import LLMTool

class ReminderTool(LLMTool):
    def can_invoke(self, function_name: str) -> bool:
        return function_name == "set_reminder"
    
    def invoke(self, function_name: str, parameters: dict) -> dict:
        # Your implementation here
        time = parameters.get("time")
        message = parameters.get("message")
        # ... set the reminder ...
        return {"status": "success", "message": f"Reminder set for {time}"}
    
    def get_model_function_call_metadata(self) -> list:
        return [{
            "name": "set_reminder",
            "description": "Sets a reminder for the user",
            "parameters": {
                "type": "object",
                "properties": {
                    "time": {"type": "string", "description": "When to remind"},
                    "message": {"type": "string", "description": "What to remind about"}
                },
                "required": ["time", "message"]
            }
        }]
```

## Style Guidelines

- Follow PEP 8
- Use descriptive variable names (avoid single letters except for indices)
- Add type hints where practical
- Document complex logic with comments
- Keep functions focused and under 50 lines when possible

## Testing

Currently, Chatty Friend uses manual testing. When testing:

1. **Voice interaction**: Test wake word and conversation flow
2. **Web interface**: Verify all configuration options work
3. **Tools**: Ensure your tool works with various inputs
4. **Error cases**: Test what happens when APIs fail or return errors

## Questions?

Feel free to open an issue with the "question" label or start a discussion in GitHub Discussions.

## Recognition

Contributors will be recognized in our README. Every contribution, no matter how small, helps make Chatty Friend better for seniors!

Thank you for helping make technology more accessible! 🎙️❤️