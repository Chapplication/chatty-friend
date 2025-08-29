# Troubleshooting Guide

This guide helps resolve common issues with Chatty Friend. If you can't find your issue here, please [open a GitHub issue](https://github.com/Chapplication/chatty-friend/issues).

## Quick Diagnostics

Run this command to check system status:
```bash
# Check if services are running
sudo systemctl status start_chatty.service

# Check recent logs
sudo journalctl -u start_chatty.service -n 50

# Check audio devices
aplay -l && arecord -l

# Check network
ping -c 4 google.com
```

## Common Issues

### 🔇 Never hear anything - lights on the Pi come on but no sound at all even after a few minutes
**Symptoms:** 
- Power lights on but no sound

**Solutions:**
- Make sure your SD card is in
- Check the colume setting on your speaker or try a different speaker
- check for the Pi's hotspot and join it from wifi if found.  open 10.42.0.1 and check Wifi SSID and password.  paste your openAI key into the secrets config area.
- DISABLE HEADLESS MODE TO DIAGNOSE:  Attach a keyboard, mouse and screen and open a terminal.  "ps aux | grep chatty" to get the list of processes related to chatty friend, then "kill" the "chatty_run_and_upgrade.sh" bash process as well as the chatty_friend.py python process.  This will allow you to run "bin/python chatty_friend.py" and troubleshoot errors.

### 🔇 "Chatty Friend doesn't respond to wake word"

**Symptoms:** 
- Hear intial tones but no response when saying "Hey Jarvis"

**Solutions:**

1. **Check microphone volume**

2. **Attach to Web Server and Check Configuration**
- if your pi is running in hotspot mode, attach to it and provide Wifi credentials
- If your pi is on the same network as your development machine or phone, point at it by browsing to the IP address.  
- Verify volume is set above zero
- see DISABLE HEADLESS MODE TO DIAGNOSE above


### Where to Get Help

1. **GitHub Issues**: [Report bugs](https://github.com/Chapplication/chatty-friend/issues)
2. **Discussions**: [Ask questions](https://github.com/Chapplication/chatty-friend/discussions)
3. **Wiki**: [Community solutions](https://github.com/Chapplication/chatty-friend/wiki)