import os
dirname = os.path.dirname(__file__)
filename = os.path.join(dirname, 'chatty_web.py')

import runpy
import sys

try:
    from chatty_wifi import IS_PI, is_online, connect_to_wifi, start_hotspot_mode
    from chatty_config import ConfigManager
    import time
    if IS_PI and not is_online():
        conman = ConfigManager()
        ssid = conman.get_config('WIFI_SSID')
        password = conman.get_config('WIFI_PASSWORD')
        if ssid and password:
            connect_to_wifi(ssid, password)
            time.sleep(10)
        if not is_online():
            start_hotspot_mode()
except Exception as e:
    print(e)

sys.argv = ["streamlit", "run", filename, "--server.port=80","--server.headless=true"]; 
runpy.run_module("streamlit", run_name="__main__")