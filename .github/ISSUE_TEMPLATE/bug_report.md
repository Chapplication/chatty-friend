---
name: Bug report
about: Create a report to help us improve Chatty Friend
title: '[BUG] '
labels: bug
assignees: ''

---

**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Say wake word "Hey Jarvis"
2. Ask '...'
3. Observe '...'
4. See error

**Expected behavior**
A clear and concise description of what you expected to happen.

**Actual behavior**
What actually happened instead.

**System Information:**
 - Device: [e.g. Raspberry Pi 4B 4GB]
 - OS: [e.g. Ubuntu 23.04]
 - Python version: [e.g. 3.11.2]
 - Chatty Friend version/commit: [e.g. v0.1.0 or commit hash]
 - Audio device: [e.g. Jabra Speak 410]

**Logs**
If applicable, add logs to help explain your problem.
```bash
sudo journalctl -u start_chatty.service -n 100
```

**Additional context**
Add any other context about the problem here. For example:
- Does it happen consistently or intermittently?
- Did it work before and recently stop?
- Any recent changes to your setup?
