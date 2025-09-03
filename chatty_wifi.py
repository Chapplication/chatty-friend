import platform
import os
# Platform detection
IS_PI = platform.machine().lower() in ['armv6l', 'armv7l', 'aarch64'] and platform.system().lower() == 'linux'
IS_MAC = platform.system().lower() == 'darwin'
import subprocess
import time



def is_online():
    for _ in range(10):
        if 0==os.system("ping -c 1 8.8.8.8"):
            return True
        time.sleep(.5)
    return False

def start_hotspot_mode(no_calls=False):
    """Start hotspot mode on Pi"""
    if not IS_PI:
        return
    
    try:
        if not no_calls:
            os.system("systemctl restart NetworkManager")
            os.system("nmcli radio wifi on")
            os.system("nmcli device wifi rescan")
            os.system(f"nmcli device wifi hotspot")
    except Exception as e:
        print(f"Error starting hotspot mode: {e}")
        pass

def connect_to_wifi(ssid, password):
    """Connect to WiFi with audio feedback for headless operation"""
    
    connection_name = f"conn-{ssid}"
    
    def speak(message):
        os.system(f'espeak "{message}" 2>/dev/null')
    
    def connection_exists():
        result = subprocess.run(['nmcli', 'con', 'show', connection_name], 
                              capture_output=True, stderr=subprocess.DEVNULL)
        return result.returncode == 0
    
    def is_connected():
        result = subprocess.run(['nmcli', 'con', 'show', '--active'], 
                              capture_output=True, text=True)
        return connection_name in result.stdout
    
    # Check if already connected
    if is_connected():
        speak(f"Already connected to {ssid}")
        return True
    
    speak("Starting WiFi setup")
    
    # Ensure WiFi is on
    os.system("nmcli radio wifi on")
    time.sleep(2)
    
    # Scan for networks
    speak("Scanning for networks")
    os.system("nmcli device wifi rescan")
    time.sleep(5)
    
    # Create connection if it doesn't exist
    if not connection_exists():
        speak(f"Creating connection to {ssid}")
        cmd = f'nmcli con add type wifi con-name "{connection_name}" ifname wlan0 ssid "{ssid}" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "{password}"'
        result = subprocess.run(cmd, shell=True, capture_output=True)
        
        if result.returncode != 0:
            speak("Failed to create connection profile")
            return False
    
    # Try to connect
    speak(f"Connecting to {ssid}")
    result = subprocess.run(f'nmcli con up "{connection_name}"', 
                          shell=True, capture_output=True)
    
    if result.returncode == 0:
        speak("WiFi connected successfully")
        return True
    else:
        speak("WiFi connection failed")
        # Optionally delete failed profile
        os.system(f'nmcli con delete "{connection_name}" 2>/dev/null')
        return False