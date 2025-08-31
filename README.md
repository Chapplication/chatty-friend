# Chatty Friend 🎙️

A smart speaker companion for senior citizens, powered by AI and running on Raspberry Pi.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## Overview

Chatty Friend is an AI-powered voice assistant specifically designed to provide companionship and support for senior citizens. Built on OpenAI's real-time API, it offers natural conversation with safety features like primary contact notifications and activity monitoring by authorized caregivers.

Special care was given to the configuration of speech parameters (how fast the user talks, easy interruptability) and privacy (local voice activity detection and local hotword 'wake up') as well as supervisory needs.  The supervisor runs a reasoning model on conversation transripts to determine the need for immediate escalations or notes for future interactions.

**AI Models**
The default AI model to use for realtime interactions (from chatty_config.py) is gpt-4o-mini-realtime-preview
because it has a cost effective profile.  OpenAI's latest "gpt-realtime" model can be provided through the web UI
or by updating the code but the cost is significantly higher.

**Key Features:**
- 🍓 Simple smartspeaker deployment to senior citizen living evironment on Raspberry Pi (no phone/mac/tablet/laptop needed)
- 🗣️ Natural voice conversations with "Hey Jarvis" wake word (customizable)
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
- Is it warmer where Noah liveS? -> gets the live weather (if weather key is configured) weather in the current city (learned from conversation and stored in user's profile) as well as from the city where Noah lives (also learned) and compares the two, composing a nice reply.
- "My friend Barbara is from Kentucky" -> remembers Barbara for future conversations, with facts related to her
- "what day is it" -> its Wendesday, October 5, 2024.  What do you want to do today?!
- "how much is 128 times 42" -> "Its 5,376!  why do you ask?"
- "get the latest upgrade" -> pulls latest repository from chatty-friend

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

5. **Talk to Chatty** - Hold `space` and speak (push-to-talk mode)

6. **Have a conversation!** 🎉

### Next Steps

- **Configure additional tools**: Add weather, news, and search API keys
- **Customize personality**: Set voice, speed, volume, and system prompts
- **Set up contacts**: Configure primary contacts for summaries and escalations

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
- boot the Pi and attach to the hotspot it provides using the chatty_friend SSID (password 'assistant')
- point your browser to 10.42.0.1 and configure:
   - provide a wifi SSID and Wifi Password for it to use insteasd of its hotspot
   - enter the default password chatty friend password 'assistant'
   - configure a new password
   - condigure a primary email contact and email server credentials
   - configure an OpenAI realtime key under the 'secrets' configuration by pasting json into the window:
   {
     "chat_api_key": "sk-proj-your-openai-api-key-here"
   }
   - reboot.  Pi should get online and begin interacting over voice.  If unable to connect, it will re-enter hotspot mode and you can connect again and correct the error.

### Wake Word Configuration

The default wake word is "Hey Jarvis" but can be customized using [OpenWakeWord](https://github.com/dscripka/openWakeWord). To train a custom wake word:

1. Follow the [OpenWakeWord training guide](https://github.com/dscripka/openWakeWord#training-custom-models)
2. Generate your custom `.tflite` model
3. Replace the model file in the project
4. Update the wake word in configuration

*Note: Future versions will support "Amanda" as the default wake word.*

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
                      │ "Hey Jarvis" heard  │               
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
     │ User │────────▶│   VAD/Wake Word     │────────▶│ Chatty      │────────▶│ Speaker │
     │      │ [voice] │   Detector          │[voice]  │ Friend      │ [audio] │         │
     └──────┘         │                     │         └─────────────┘         └─────────┘
                      │ 🔒 Local Processing │              
                      │ "Hey Jarvis" → Open │              
                      │ Otherwise → Silent  │              
                      └─────────────────────┘
```

### 4. Adding Tool Ecosystem
```
                                                    ☁️ OpenAI Real-time API
                                                        ┌─────────────┐
                                                        │  GPT-4o     │
                                                        │ Mini/Audio  │
                                                        └─────────────┘
                                                            ▲ │
                                                        [websocket]
                                                            │ ▼
     ┌──────┐         ┌─────────────────────┐         ┌─────────────┐         ┌─────────┐
     │ User │────────▶│   VAD/Wake Word     │────────▶│ Chatty      │────────▶│ Speaker │
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
                                                        │  GPT-4o     │
                                                        │ Mini/Audio  │
                                                        └─────────────┘
                                                            ▲ │
                                                        [websocket]
                                                            │ ▼
     ┌──────┐         ┌─────────────────────┐         ┌─────────────┐         ┌─────────┐
     │ User │────────▶│   VAD/Wake Word     │────────▶│ Chatty      │────────▶│ Speaker │
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
                      │                     │─────────────────▶│   GPT-4o    │
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
               │ [reads/writes]              [reads/writes] │
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

- **Privacy First**: Nothing leaves the device until "Hey Jarvis" is detected
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
   - **OS**: Other general purpose OS → Ubuntu → Ubuntu Desktop 23.04 (64-bit)
   - **Storage**: Your SD card
d. Click "Write" and wait for completion

### Step 2: Initial Pi Setup

a. Insert the SD card into your Raspberry Pi and power on
b. Complete Ubuntu setup with these settings:
   - **Name**: Chatty Friend
   - **Computer name**: chatty
   - **Username**: friend
   - **Password**: (your choice)
   - **Important**: Enable auto Log-in

c. Connect the raspberry pi to your WiFi network

d. Configure system settings:
   # update/upgrade your OS
   ```bash
   # Update system
   sudo apt update && sudo apt upgrade -y
   ```   
   # Disable screen blanking - in the Pi desktop:
   #     Settings → Power → Screen Blank → Never
   
   # Create WiFi hotspot for later use on the Pi desktop:
   #    Settings → WiFi → ⋮ → Turn On Wi-Fi Hotspot
   #    Note the SSID and password, then disable it for now

### Step 3: Enable SSH Access

On the Raspberry Pi:
```bash
# Install SSH and Git
sudo apt install -y openssh-server git

# Get your Pi's IP address
ip a
# Note the IP address (e.g., 192.168.1.100)
```

### Step 4: Install Chatty Friend

From your development machine:

# Copy script to Pi (replace XXX with your Pi's IP that was noted earlier)
scp git_clone_chatty.sh friend@192.168.1.XXX:

On the Raspberry Pi:
```bash
# Clone and set up Chatty Friend
bash git_clone_chatty.sh


# Install all prerequisites and configure services
bash install_chatty_friend_prereqs.sh
# Answer 'yes' when prompted, will take some time
```

Enable the hotspot and Reboot the Pi.  You can now run it headless.

### Step 5: Access Web Interface

- Connect your development machine to the Pi's wifi hotspot
- On your development machine point a browser to: 10.42.0.1
- in the browser configure the WiFi SSID and Wifi password that you want it to use for normal operation
- in the browser login with 'assistant' and change the password for Chatty Friend administtration
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