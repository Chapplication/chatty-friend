# Chatty Friend 🎙️

A smart speaker companion for senior citizens, powered by AI and running on Raspberry Pi.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## Demo

**[▶️ Click for Demo](https://youtu.be/KJMjCZYRz5s?si=1WS6eXdjLY9bFooA)** *(Ctrl+Click to open in new tab)*

## Overview

Chatty Friend is an AI-powered voice assistant specifically designed to provide companionship and support for senior citizens. Built on OpenAI's real-time API, it offers natural conversation with safety features like primary contact notifications and activity monitoring by authorized caregivers.

Special care was given to the configuration of speech parameters (how fast the user talks, easy interruptability) and privacy (local voice activity detection and local hotword 'wake up') as well as supervisory needs.  The supervisor runs a reasoning model on conversation transripts to determine the need for immediate escalations or notes for future interactions.

**AI Models**
The default AI model to use for realtime interactions (from chatty_config.py) is gpt-realtime

**Key Features:**
- 🍓 Simple smartspeaker deployment to senior citizen living evironment on Raspberry Pi (no phone/mac/tablet/laptop needed)
- 🗣️ Natural voice conversations with wake word ("Amanda" or "Oliver")
- 👥 Primary contact system with email summaries and SMS escalations (requires Twilio config)
- 🌐 Web-based configuration interface (mobile-friendly)
- 🛠️ Extensible tool system (weather, news, search, and more)
- 🔒 Privacy-focused: local audio processing unless explicitly awakened for action.
- runs on MacOS during development

**Whats Different:**
There are a lot of OpenAI realtime projects on github.  Here's what's unique:
- Private - No cloud communication until the user says the wake phrase.  No cost, nothing shared.
- Dialog is fluid and engaging until user dismisses the friend (or timeout happens)
- Smoothly handles interruptions, talking-over, and slow speakers, etc.
- Gets news, web searches, wiki entries, weather, time, etc. 
- Remembers (persistent, local) conversations over time, building up a relationship between the user and the friend
- Supervisor function (reasoning model) allows designated contact to receive activity summaries so caregivers can monitor loved ones
- Supervisor escalates situations (danger, lost items, etc.) if needed
- Monitors and communicates AI costs to supervisor
- Uses embeddings to semantically match commands (ie "go to sleep") as a backup to stubborn tool calling models
- includes web server (on the device) to configure all details of personality, voice, speed, volume, learned history, etc.

**Some Examples:**
- "What was the name of the lady in that hemingway book about Spain" -> discusses all of Hemingways work in a friendly conversation
- "Tell cindy to bring some peanut butter" -> emails contact "Cindy" a request to bring peanut butter
- "I can't find my medication" -> emails or SMS the primary caregiver as configured
- "Talk to you later" -> goes to sleep.  Records the conversation including summarized notes, new profile memories, new early warning signs of concerns.  Emails the summary to primary contact, escalates as needed for urgent concerns
- "Can you go a little slower and louder" -> udpates voice to be slower and louder
- "Is there any news about the floods" -> checks online RSS feeds for related news
- "was there a war during Ford's presidency" -> looks at wikipedia entry for US President Ford
- "What's the new superman movie" -> Google searches (if the key is configured) the name
- Is it warmer where Noah lives? -> gets the live weather (if weather key is configured) weather in the current city (learned from conversation and stored in user's profile) as well as from the city where Noah lives (also learned) and compares the two, composing a nice reply.
- "My friend Barbara is from Kentucky" -> remembers Barbara for future conversations, with facts related to her
- "what day is it" -> its Wendesday, October 5, 2024.  What do you want to do today?!
- "how much is 128 times 42" -> "Its 5,376!  why do you ask?"
- "get the latest upgrade" -> pulls latest repository from chatty-friend (running in headless mode on the Pi)

Coming soon: Learn more at [chattyfriend.com](https://chattyfriend.com)

## 🚀 Quick Start (macOS Development)

Get Chatty Friend running in QA/test mode on mac quickly:

1. **Clone and sync**
   ```bash
   git clone https://github.com/Chapplication/chatty-friend.git
   cd chatty-friend

2. **Sync with uv**
   ```bash
   uv --version
   ```
   if you get an error from that, 
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
   THEN CLOSE THE TERMINAL WINDOW AND RE-OPEN
   Finally,
   ```bash
   brew install portaudio
   uv pip install 
   uv sync
   ```

3. **Set your OpenAI API key**
   ```bash
   export CHAT_API_KEY="sk-proj-your-openai-api-key-here"
   ```

4. **Open the Config Web Page**
   ```bash
   uv run python -m streamlit run chatty_web.py
   ```
   Review and configure various options (see Config Guide)

5. **Run Chatty Friend**
   ```bash
   python chatty_friend.py
   ```

4. **Simulate wake word** - Press `w` to wake up Chatty
   wake word detection only works in headless mode on raspberry Pi where there is a lot of control over audio and system resources.
   On Mac, use keboard "push to talk" with the space bar to simulate VAD, and use W key to simulate wake word detection.
   This also allows for fast interactive prompt development as you don't have to go through the sleep/supervise cycle to iterate.

5. **Talk to Chatty** - Hold `space` and speak (push-to-talk mode)

6. **Have a conversation!** 🎉

### Next Steps

- **Configure additional tools**: Add weather, news, and search API keys
- **Customize personality**: Set voice, speed, volume, and system prompts (https://cookbook.openai.com/examples/realtime_prompting_guide)
     provide a Role & Objective (ex:you are a playful old friend...)
     provide a personality (ex:Friendly, calm and approachable counselor, older than the user and with more wisdom and patience)
     provide a tone (ex:Warm, concise, confident)
     provide a length (ex:one or two sentences per turn)
     provide a speed (ex:speak slowly and pace yourself)
     provide an indication of languages supported (ex:the conversation will be in English or Spanish but not other languages.  Even if you think you hear a different language, respond in english or spanish always)
     ask for variety (ex:vary your responses so you don't sound like a robot!)
     tell the model how to say unusual words (ex:say Toledo in Spanish like toh-leh-do)
     clarify what to do when audio quality is poor (ex:if there is too much background noise and the user is not clear, ask for clarification)
     ask the model to use tools (weather, news, internet search, etc.) freely (ex:When calling a tool, do not ask for any user confirmation. Be proactive)

- **Set up contacts**: Configure primary contacts for summaries and escalation

### Full Installation (All Features)

For complete functionality including weather, news, communication tools:

1. **Clone the repository**
   ```bash
   git clone https://github.com/Chapplication/chatty-friend.git
   cd chatty_friend
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Configure API keys** (create `chatty_secrets.json`):
   ```json
   {
     "chat_api_key": "sk-proj-your-openai-api-key-here",
     "openweather_api_key": "your-weather-key",
     "google_search_api_key": "your-google-key",
     "twilio_account_sid": "your-twilio-sid",
     "email_smtp_server": "smtp.gmail.com"
   }
   ```

4. **Run the application**
   ```bash
   python chatty_friend.py
   ```

## 🔧 Configuration

### Web Interface

Access at `http://localhost:8501` (development) or `http://<pi-ip-address>` (production)

The web interface allows configuration of:
- 📶 WiFi credentials (Raspberry Pi only)
- 👤 User profile and preferences
- 📧 Primary contact details (email/SMS)
- 🔑 API keys for additional services
- 🗣️ Voice settings

# Configuration Guide

The Chatty Friend configuration interface provides a comprehensive way to customize your AI assistant. Access the configuration by running the web interface with `uv run streamlit run chatty_web.py`.

## Configuration Sections

### 👤 Basic Settings
Configure fundamental user and voice settings:
- **Name** - The user's name that Chatty will use in conversations
- **Time Zone** - Set your local timezone for accurate time-based interactions
- **Assistant Voice** - Choose from available voice options (alloy, echo, fable, onyx, nova, shimmer)
- **Speech Speed** - Control how fast Chatty speaks (0-100, lower = slower)
- **Speech Volume** - Control Chatty's speaking volume (0-100, lower = quieter)
- **Max Profile Entries** - Maximum number of biographical entries allowed (10-10,000)
- **Seconds to Wait for More Voice** - How long Chatty waits for you to continue speaking (0.1-5.0 seconds)
- **Assistant Eagerness to Reply** - How quickly Chatty jumps into conversation (0=very eager, 100=patient)
- **Auto Sleep Time** - Seconds of inactivity before Chatty goes to sleep (60-7200)

### 📝 What Chatty Knows About You
Manage biographical information that helps Chatty understand the user better:
- Add short paragraphs or sentences about the user
- Edit existing entries
- Delete individual entries or clear all
- Each entry helps Chatty provide more personalized interactions

### 📋 Supervisory Notes
Pre-escalation notes from the AI supervisor that monitors conversations:
- View observations made by the supervisor AI
- Add important notes about user care
- Edit or delete existing notes
- These notes inform future supervision decisions

### 👥 Contacts that Chatty can Reach
Manage contacts for summaries and escalations:
- **Name** - Contact's full name
- **Type** - Primary (receives summaries) or Other
- **Email** - Valid email address for notifications
- **Phone** - Phone number with country code
- Add, edit, or delete contacts as needed

### 🔑 Password
Security settings for the configuration interface:
- Set a new password for accessing configuration
- Add a password hint for recovery
- Primary contacts can request password resets via email (if configured)

### 👥 Supervisor Setup
Configure the AI supervisor that reviews conversations:
- **Auto Summarize Every N Messages** - Frequency of intermediate conversation summaries (1-100)
- **Supervisor Instructions** - Custom instructions for what the supervisor should watch for and include in reports

### 📡 WiFi (Raspberry Pi only)
Network configuration for Raspberry Pi devices:
- View current WiFi connection
- Change WiFi network (requires restart)
- Automatically manages hotspot mode if connection fails

### 🤖 AI Settings
Advanced AI model configuration:
- **Realtime Model** - The main conversational AI model
- **Audio Transcription Model** - Model for converting speech to text
- **Supervisor Model** - Model used for conversation supervision
- **WebSocket URL** - Connection endpoint for real-time communication

### 🎭 Chatty Personality
Customize how Chatty interacts:
- **System Prompt** - Core instructions that define Chatty's behavior and personality
- **Voice Settings** - Fine-tune voice, volume, and speed
- **Assistant Eagerness** - Response timing preferences

### 📰 Chatty Content Settings
Configure content sources:
- **News Provider** - Select from available news sources (BBC, CNN, NPR, etc.)

### 🔧 Voice Technical Config
Advanced voice detection settings:
- **Voice Activity Detection Threshold** - Sensitivity for detecting speech (0.2-0.5)
- **Wake Word Detection Threshold** - Sensitivity for wake word recognition (0.4-0.9)
- **Seconds to Wait for More Voice** - Pause duration before processing speech

### 🔐 Secrets
Manage API keys and sensitive data:
- View configured/unconfigured API keys
- Update secrets in JSON format
- Keys are hidden for security

### 💀 DANGER! Reset
System management options:
- Reset all configuration to defaults (preserves passwords and secrets)
- Restart system (Raspberry Pi only)

## Navigation

The interface uses a locked-section approach:
- Click any section in the left sidebar to view it
- When you make changes, the section locks automatically
- Use the **Save Changes** or **Cancel Changes** buttons to commit or discard edits
- You cannot switch sections while editing - save or cancel first

## Platform Differences

- **Mac**: Network and restart features are disabled
- **Raspberry Pi**: Full functionality including WiFi management and system restart

## Session Security

On Raspberry Pi, sessions automatically timeout after 10 minutes of inactivity, requiring re-authentication.


### Cold-start on the Pi:
- install chatty friend using the Pi image instructions (see deployment instructions below)
- boot the Pi and attach an external device (phone/browser) to the hotspot it provides (chatty / assistant)
- point your browser to 10.42.0.1 and configure:
   - provide a wifi SSID and Wifi Password for it to use insteasd of its hotspot
   - enter the default password chatty friend password 'assistant'
   - configure a new password
   - configure a primary email contact and email server credentials
   - configure an OpenAI realtime key under the 'secrets' configuration by pasting json into the window:
   {
     "chat_api_key": "sk-proj-your-openai-api-key-here"
   }
   - reboot.  Pi should get online and begin interacting over voice.  If unable to connect, it will re-enter hotspot mode and you can connect again and correct the error.

### Wake Word Configuration

The default wake word is "Amanda" but can be changed to "oliver" or customized using [OpenWakeWord](https://github.com/dscripka/openWakeWord). To train a custom wake word:

1. Follow the [OpenWakeWord training guide](https://github.com/dscripka/openWakeWord#training-custom-models)
2. Generate your custom `.tflite` model
3. Replace the model file in the project
4. Update the wake word in configuration

### Primary Contact System

Configure a primary contact to receive:
- **Daily summaries**: Overview of conversations and activity
- **Health checks**: Periodic status updates
- **Escalations**: Urgent notifications via SMS

### Development Mode (macOS)

When running on macOS:
- Press `w` to simulate wake word detection
- Hold `space` for push-to-talk mode
- WiFi management and authentication disabled


## 🧩 Architecture

The architecture evolves through layers of complexity, starting simple and adding privacy, intelligence, and supervision:

### 1. Basic Conversation
```
     ┌──────┐                        ┌─────────────┐
     │ User │──── [mic speech] ──────│ Chatty      │
     │      │── [speaker audio] ─────│ Friend      │
     └──────┘                        └─────────────┘
```

### 2. Adding Privacy/expense reduction Layer (Local Processing)
```
     ┌──────┐         ┌─────────────────────┐         ┌─────────────┐         ┌─────────┐
     │ User │────────▶│   VAD/Wake Word     │────────▶│ Chatty      │────────▶│ Speaker │
     │      │ [voice] │   Detector          │[voice]  │ Friend      │ [audio] │         │
     └──────┘         │                     │         └─────────────┘         └─────────┘
                      │ 🔒 Local Processing │                                      
                      │ Nothing sent until  │                                      
                      │ "Amanda" heard      │               
                      └─────────────────────┘
```

### 3. Adding Cloud Intelligence
```
                                                ☁️ OpenAI Real-time API
                                                        ┌─────────────┐
                                                        │ cloud model │
                                                        └─────────────┘
                                                            ▲ │
                                                        [websocket]
                                                            │ ▼
     ┌──────┐         ┌─────────────────────┐         ┌─────────────┐         ┌─────────┐
     │ User │────────▶│  VAD/Open Wake Word │────────▶│ Chatty      │────────▶│ Speaker │
     │      │ [voice] │   Detector          │[voice]  │ Friend      │ [audio] │         │
     └──────┘         │                     │         └─────────────┘         └─────────┘
                      │ 🔒 Local Processing │              
                      │ "Amanda" → Open     │              
                      │ Otherwise → Silent  │              
                      └─────────────────────┘
```

### 4. Adding Tool Ecosystem
```
                                                    ☁️ OpenAI Real-time API
                                                        ┌─────────────┐
                                                        │gpt-realtime │
                                                        │             │
                                                        └─────────────┘
                                                            ▲ │
                                                        [websocket]
                                                            │ ▼
     ┌──────┐         ┌─────────────────────┐         ┌─────────────┐         ┌─────────┐
     │ User │────────▶│VAD/Open Wake Word   │────────▶│ Chatty      │────────▶│ Speaker │
     │      │ [voice] │   Detector          │[voice]  │ Friend      │ [audio] │         │
     └──────┘         └─────────────────────┘         └─────┬───────┘         └─────────┘
                                                            │
                                                       [tool calls]
                                                            │
                      ┌──────────────────────────────────────┼──────────────────────────────────────┐
                      │                                      ▼                                      │
                   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │
                   │Weather  │  │  News   │  │ Google  │  │  Math   │  │  Email  │  │   ...   │    │
                   │Service  │  │ Feed    │  │ Search  │  │ Tool    │  │   SMS   │  │         │    │
                   └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘    │
                      └──────────────────────────────────────────────────────────────────────────┘
```

### 5. Complete System with Supervision
```
                                                ☁️ OpenAI Real-time API
                                                        ┌─────────────┐
                                                        │gpt-realtime │
                                                        │             │
                                                        └─────────────┘
                                                            ▲ │
                                                        [websocket]
                                                            │ ▼
     ┌──────┐         ┌─────────────────────┐         ┌─────────────┐         ┌─────────┐
     │ User │────────▶│ VAD/Open Wake Word  │────────▶│ Chatty      │────────▶│ Speaker │
     │      │ [voice] │   Detector          │[voice]  │ Friend      │ [audio] │         │
     └──────┘         └─────────────────────┘         └─────┬───────┘         └─────────┘
                                ▲                           │                       
                                │                      [tool calls]                 
                           [transcript]                     │                 
                                │                           ▼                       
                                │         ┌──────────────────────────────────────────────────┐
                                │         │ ┌─────────┐  ┌─────────┐  ┌─────────┐            │
                                │         │ │Weather  │  │  News   │  │ Google  │ ┌─────────┐│
                                │         │ │Service  │  │ Feed    │  │ Search  │ │   ...   ││
                                │         │ └─────────┘  └─────────┘  └─────────┘ └─────────┘│
                                │         └──────────────────────────────────────────────────┘
                                │
                                ▼
                      ┌─────────────────────┐              ☁️ OpenAI Reasoning
                      │    Supervisor       │                  ┌─────────────┐
                      │                     │─────────────────▶│   GPT       │
                      │ 🧠 Monitors         │  [analysis]      │ Reasoning   │
                      │ 📧 Summarizes       │◀─────────────────│   Model     │
                      │ 🚨 Escalates        │  [insights]      └─────────────┘
                      └─────────────────────┘
                                │
                           [notifications]
                                │
                                ▼
                      ┌─────────────────────┐
                      │   Email/SMS         │────────────▶ 📧 Primary Contact
                      │   Gateway           │              📱 Caregivers
                      └─────────────────────┘
```

### 6. Configuration Architecture
```
     ┌─────────────────┐                    ┌─────────────────┐
     │  Chatty Friend  │                    │ Chatty Web      │
     │   Application   │                    │ Admin Interface │
     │                 │                    │                 │
     └─────────┬───────┘                    └─────────┬───────┘
               │                                      │
         [reads/writes]                        [reads/writes]
               │                                      │
               └──────────────┬───────────────────────┘
                              │
                              ▼
               ┌──────────────────────────────────────────┐
               │          Local Storage                   │
               │                                          │
               │  ┌─────────────────┐ ┌─────────────────┐ │
               │  │ chatty_config   │ │ chatty_secrets  │ │
               │  │     .json       │ │     .json       │ │
               │  │                 │ │                 │ │
               │  │ • Voice settings│ │ • API keys      │ │
               │  │ • User profile  │ │ • Passwords     │ │
               │  │ • Contacts      │ │ • SMTP config   │ │
               │  │ • Preferences   │ │ • Tokens        │ │
               │  └─────────────────┘ └─────────────────┘ │
               └──────────────────────────────────────────┘
```

### Key Architecture Principles

- **Privacy First**: Nothing leaves the device until "Amanda" or "Oliver" (as configured) is detected
- **Local Processing**: Wake word detection and VAD run entirely on-device  
- **Cloud Intelligence**: Only activated conversations use OpenAI's real-time API
- **Tool Extensibility**: Modular system for adding weather, news, search, etc.
- **Supervisory Care**: All interactions monitored for safety and connection
- **Caregiver Integration**: Summaries and escalations sent to designated contacts
- **Dual Configuration**: Both voice app and web admin share the same local config files

## 🛠️ Available Tools

| Tool | Description | Required API |
|------|-------------|--------------|
| Weather | Current conditions & forecasts | OpenWeather |
| News | RSS feed aggregation | None |
| Search | Web search capabilities | Google |
| Math | Calculations and conversions | None |
| Communication | Email/SMS notifications | Twilio/SMTP |
| Research | Deep web research | Google |
| System Info | Device status | None |

## 👩‍💻 Development

### Adding New Tools

1. Create new file in `tools/` directory based on any of the simple examples there
2. Register in `chatty_tools.py` by adding your new tool to the list

## 🍓 Raspberry Pi Deployment

### Recommended Hardware

- **Raspberry Pi**: Model 4B (4GB or 8GB RAM)
- **SD Card**: 32GB minimum, Class 10
- **Speakerphone**: Jabra Speak 410/510 (tested)
- **Power Supply**: Official USB-C adapter (5V, 3A)



## 🍓 Raspberry Pi Installation Guide

This guide covers setting up Chatty Friend as a headless smart speaker on a Raspberry Pi.  You can execute these steps and get everything set up as you want, then duplicate the SD card to make additional units.

### Prerequisites

- Raspberry Pi 4 (4GB or 8GB recommended)
- MicroSD card (32GB minimum)
- USB speakerphone (Jabra Speak 410/510 tested)
- Computer with SD card reader
- [Raspberry Pi Imager Software (free)](https://www.raspberrypi.com/software/)

### Step 1: Prepare the SD Card

a. Download and install [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
b. Insert your SD card into your computer
c. Open Raspberry Pi Imager and select:
   - **Device**: your device type (raspberry pi 4 and 5 tested)
   - **OS**: Other general purpose OS → Ubuntu → Ubuntu Desktop 25.04 (64-bit)
   - **Storage**: Your SD card
d. Click "Write" and wait for completion

### Step 2: Initial Pi Setup

a. Insert the SD card into your Raspberry Pi and power on
b. Complete Ubuntu setup with these settings:
   - **Wifi**: attach to your wifi
   - **Name**: chatty
   - **Computer name**: chatty
   - **Username**: chatty
   - **Password**: (your choice)

c. Take the following steps on ubuntu
   - **Check for Updates**: Run "software updater" and get the latest.  reboot if needed
   - **Screen Blank**: Disable screen blank in settings->privacy->screen blank delay->Never
   - **Hot Spotk**: settings->Wifi->hotspot create SSID and Password for your hotspot.  turn it on (snap the QR code now if you want) and back off again.
   - **Important**: Enable auto Log-in settings->system->users->chatty->unlock->Automatic Login

d. Configure system settings:
   # Setting up the environment for chatty: open a Terminal window and enter:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```   

### Step 3: Install Chatty Friend

# Sync the git repo for Chatty Friend to your pi
**run this from terminal on the pi:**
- git clone https://github.com/Chapplication/chatty-friend.git
- cd chatty-friend
- bash install_chatty_friend_prereqs.sh (Provide the password you created earlier (for the user) and Answer 'yes' when prompted repeatedly, will take some time)
- bin/streamlit run chatty_web.py (wait a few seconds, will bring up the web interface to configure chatty friend)
- enter "assistant" which is the default password on the browser screen

Enable the hotspot and Reboot the Pi.  You can now run it headless.

### Step 5: Access Web Interface

- Connect your development machine to the Pi's wifi hotspot
- On your development machine point a browser to: 10.42.0.1
- in the browser configure the WiFi SSID and Wifi password that you want it to use for normal operation
- in the browser login with 'assistant' and change the password for Chatty Friend administtration
- spend some time on https://www.openai.fm/ to figure out how you want chatty friend to sound
- in the browser Configure the Chatty Friend.  Personality, voice, speed, volume, supervisor characteristics.
  - Special attention should be paid to supervisor instructions if there is concern that a user may engage
    in deluded thinkining with their companion, such as assigning a human "self" to the AI companion or 
    attributing excessive emotion to the AI.  Use the supervisor instructions to request warnings of this 
    type so that escalations occur as appropriate.
- in the browser Set contact details (primary contacts will receive email summaries of chat activity if email is configured)

### What Was Installed By the Prereqs script

The installation script (`install_chatty_friend_prereqs.sh`) set up:

**System packages:**
- Python 3 and pip
- Audio libraries (PortAudio, ALSA, Sox)
- Text-to-speech engines (espeak, pico)
- Network security (UFW firewall - currently disabled)
- Development tools

**Python packages:**
- OpenAI API client
- Speech recognition
- Wake word detection (OpenWakeWord)
- Communication libraries (Twilio)
- Web frameworks (Flask, Streamlit)

**Services:**
- `start_chatty.service` - Systemd service for auto-start
- Web server on port 80 (pi, enabled in run_chatty_web.py) or 8501 (mac, default)
- Audio processing pipeline


### Code Style

- Follow PEP 8
- Use type hints where possible
- Document all public methods
- Keep functions focused and testable

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md).

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: [Wiki](https://github.com/yourusername/chatty-friend/wiki)
- **Issues**: [GitHub Issues](https://github.com/yourusername/chatty-friend/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/chatty-friend/discussions)
- **Website**: [chattyfriend.com](https://chattyfriend.com)

## 🙏 Acknowledgments

- OpenAI for the real-time API
- [OpenWakeWord](https://github.com/dscripka/openWakeWord) for wake word detection
- The open-source community for the amazing libraries
- All contributors who help make Chatty Friend better

---

Built with ❤️ to help seniors stay connected and engaged