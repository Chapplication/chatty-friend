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

import os
import subprocess
import time
import shlex

def connect_to_wifi(ssid, password):
    """Connect to WiFi with audio feedback for headless operation"""
    
    connection_name = f"conn-{ssid}"
    
    def speak(message):
        os.system(f'espeak -a 50 "{message}" 2>/dev/null')
    
    def get_wifi_interface():
        result = subprocess.run(['nmcli', 'dev', 'status'], 
                              capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'wifi' in line:
                return line.split()[0]
        return 'wlan0'  # fallback
    
    def connection_exists():
        result = subprocess.run(['nmcli', 'con', 'show', connection_name], 
                              capture_output=True)
        return result.returncode == 0
    
    def is_connected():
        result = subprocess.run(['nmcli', 'con', 'show', '--active'], 
                              capture_output=True, text=True)
        return connection_name in result.stdout
    
    def network_available(ssid):
        result = subprocess.run(['nmcli', 'dev', 'wifi', 'list'], 
                              capture_output=True, text=True)
        return ssid in result.stdout
    
    # Check if already connected
    if is_connected():
        speak(f"connected to {ssid}")
        return True
    
    speak("WiFi setup")
    
    # Ensure WiFi is on
    os.system("nmcli radio wifi on")
    time.sleep(2)
    
    # Get the WiFi interface
    interface = get_wifi_interface()
    
    # Scan for networks
    speak("Scanning")
    os.system("nmcli device wifi rescan")
    time.sleep(5)
    
    # Check if network is available
    if not network_available(ssid):
        speak(f"Network {ssid} not found")
        return False
    
    # Escape special characters
    ssid_escaped = shlex.quote(ssid)
    password_escaped = shlex.quote(password)
    connection_name_escaped = shlex.quote(connection_name)
    
    # Create connection if it doesn't exist
    if not connection_exists():
        speak(f"Creating connection to {ssid}")
        cmd = f'nmcli con add type wifi con-name {connection_name_escaped} ifname {interface} ssid {ssid_escaped} wifi-sec.key-mgmt wpa-psk wifi-sec.psk {password_escaped}'
        result = subprocess.run(cmd, shell=True, capture_output=True)
        
        if result.returncode != 0:
            speak("Failed to create connection profile")
            return False
    
    # Try to connect
    speak(f"Connecting to {ssid}")
    result = subprocess.run(f'nmcli con up {connection_name_escaped}', 
                          shell=True, capture_output=True)
    
    if result.returncode == 0:
        speak("WiFi connected successfully")
        return True
    else:
        speak("WiFi connection failed")
        # Delete failed profile
        os.system(f'nmcli con delete {connection_name_escaped} 2>/dev/null')
        return False