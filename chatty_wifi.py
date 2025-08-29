import platform
import os
# Platform detection
IS_PI = platform.machine().lower() in ['armv6l', 'armv7l', 'aarch64'] and platform.system().lower() == 'linux'
IS_MAC = platform.system().lower() == 'darwin'
import subprocess
import time



def is_online():
    return 0==os.system("ping -c 1 8.8.8.8")

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
    except:
        pass

def connect_to_wifi(ssid, password, no_calls=False):
    """Attempt to connect to WiFi on Pi"""
    if not IS_PI:
        return True  # Always succeed on Mac for testing
    
    try:
        # Use nmcli to connect to WiFi network
        if not no_calls:
            os.system("systemctl restart NetworkManager")
            os.system("nmcli radio wifi on")
            os.system("nmcli device wifi rescan")
            time.sleep(5)

            for retry in range(5):
                result = os.system("nmcli d wifi connect \""+ssid+"\" password "+password)
                if result == 0:
                    break
                time.sleep(2)
            
            if result == 0:
                # Wait a moment and verify the connection
                time.sleep(3)
                return is_online()
            else:
                print(f"nmcli connection failed: {result.stderr}")
                return False
                
    except subprocess.TimeoutExpired:
        print("WiFi connection attempt timed out")
        return False
    except Exception as e:
        print(f"Error connecting to WiFi: {e}")
        return False
