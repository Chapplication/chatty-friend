import platform
import os
# Platform detection
IS_PI = platform.machine().lower() in ['armv6l', 'armv7l', 'aarch64'] and platform.system().lower() == 'linux'
IS_MAC = platform.system().lower() == 'darwin'
import subprocess
import time
import socket
import json
import threading
LAST_WEB_ACTIVITY_FILE = os.path.join(os.path.dirname(__file__), "last_web_activity.json")

def record_web_activity():
    """Persist last web interaction timestamp for hotspot recovery logic."""
    try:
        timestamp = {"last_web_user_time": time.time()}
        temp_path = LAST_WEB_ACTIVITY_FILE + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(timestamp, handle)
        os.replace(temp_path, LAST_WEB_ACTIVITY_FILE)
    except Exception:
        pass

def found_recent_web_activity():
    """Check if recent web activity was detected."""
    try:
        with open(LAST_WEB_ACTIVITY_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return time.time() - data.get("last_web_user_time", 0) < 60
    except Exception:
        return False

def is_online():
    for _ in range(10):
        if 0==os.system("ping -c 1 8.8.8.8"):
            return True
        time.sleep(.5)
    return False


def start_hotspot_mode(no_calls=False):
    """Start hotspot mode on Pi; if we don't see web activity and there is wifi config, retry periodically"""
    """this solves the problem of chatty being ready before the wifi router is up after a power outage"""
    if not IS_PI:
        return

    threading.Thread(target=hotspot_with_wifi_retry, args=(no_calls,), daemon=True).start()

def hotspot_with_wifi_retry(no_calls=False):

    """ loop starting hotspot and occasionally checking for wifi config, then exit """
    while True:
        # first, turn on hotspot
        try:
            if not no_calls:
                os.system("systemctl restart NetworkManager")
                os.system("nmcli radio wifi on")
                os.system("nmcli device wifi rescan")
                os.system("nmcli device wifi hotspot")
        except Exception as exc:
            print(f"Error starting hotspot mode: {exc}")

        time.sleep(60)

        if not found_recent_web_activity():
            from chatty_config import ConfigManager
            conman = ConfigManager()
            ssid = conman.get_config('WIFI_SSID')
            password = conman.get_config('WIFI_PASSWORD')
            if ssid and connect_to_wifi(ssid, password):
                time.sleep(10)
                if is_online():
                    break

def what_is_my_ip():
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
    speak("Now Scanning")
    os.system("nmcli device wifi rescan")
    time.sleep(5)
    
    # Check if network is available
    if not network_available(ssid):
        speak(f"Network {ssid} not found")
        return False
    
    password = password or ""

    # Create connection if it doesn't exist
    if not connection_exists():
        speak(f"Creating connection to {ssid}")
        if password:
            cmd = ['nmcli', 'con', 'add', 'type', 'wifi', 'con-name', connection_name,
                   'ifname', interface, 'ssid', ssid, 'wifi-sec.key-mgmt', 'wpa-psk',
                   'wifi-sec.psk', password]
        else:
            cmd = ['nmcli', 'con', 'add', 'type', 'wifi', 'con-name', connection_name,
                   'ifname', interface, 'ssid', ssid, 'wifi-sec.key-mgmt', 'none']
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            speak("Failed to create connection")
            return False
    else:
        speak(f"Updating connection {ssid}")
        if password:
            subprocess.run(['nmcli', 'con', 'modify', connection_name, 'wifi-sec.key-mgmt', 'wpa-psk'], capture_output=True)
            subprocess.run(['nmcli', 'con', 'modify', connection_name, 'wifi-sec.psk', password], capture_output=True)
        else:
            subprocess.run(['nmcli', 'con', 'modify', connection_name, 'wifi-sec.key-mgmt', 'none'], capture_output=True)
            subprocess.run(['nmcli', 'con', 'modify', connection_name, '-wifi-sec.psk'], capture_output=True)

    # Try to connect
    speak(f"Connecting to {ssid}")
    result = subprocess.run(['nmcli', 'con', 'up', connection_name], capture_output=True, text=True)

    if result.returncode == 0:
        ip = what_is_my_ip() or "Not Known"
        ip_string = " dot ".join(ip.split("."))
        speak(f"WiFi connected successfully.  Configure at {ip_string}")
        return True
    else:
        speak("WiFi connection failed")
        # Delete failed profile
        subprocess.run(['nmcli', 'con', 'delete', connection_name], capture_output=True)
        return False
