sudo apt update
sudo apt upgrade
sudo apt install python3-pip
sudo apt install python3-venv
python3 -m venv .
bin/pip install openai
bin/pip install SpeechRecognition
bin/pip install twilio
bin/pip install numpy
sudo apt install portaudio19-dev
bin/pip install pyaudio
sudo apt install espeak
bin/pip install Wikipedia
bin/pip install openwakeword==0.6.0 --force-reinstall --no-deps
bin/pip install websockets
bin/pip install feedparser

sudo apt-get install flac
sudo apt-get install libreta pico-utils
sudo apt install sox
bin/pip install flask
bin/pip install streamlit
sudo apt-get install libttspico-utils
sudo apt install mpg123


bin/python init_oww_models.py

# Install UFW if not already installed
sudo apt install -y ufw

# Set default rules: deny all incoming and outgoing traffic
sudo ufw default deny incoming
sudo ufw default deny outgoing

# Allow SSH (port 22 by default)
sudo ufw allow OpenSSH

# Allow Tornado web server (assuming it runs on default HTTP and HTTPS ports)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8501

# For Python programs using web services:
# Depending on what web services your Python programs use, you might need to open additional ports.
# For this example, I'll assume they make standard web requests. 
# If you need other ports, just add them similarly to the ones below:
sudo ufw allow out 80/tcp    # allow outgoing HTTP
sudo ufw allow out 443/tcp   # allow outgoing HTTPS

# Allow email client using SMTP on port 587 (send only)
sudo ufw allow out 587/tcp

# Allow DNS for domain name resolution
sudo ufw allow out 53/udp    # allow outgoing UDP on port 53 for DNS
sudo ufw allow out 53/tcp    # allow outgoing TCP on port 53 for DNS (less common but sometimes used)

# Allow NTP for time synchronization
sudo ufw allow out 123/udp

sudo ufw enable
# UFW - breaks the web server config as of last test Dec 31 2023
sudo ufw disable

sudo chmod 744 start_chatty.sh
sudo cp start_chatty.sh /usr/local/bin
sudo chmod 744 /usr/local/bin/start_chatty.sh
sudo cp start_chatty.service /etc/systemd/system
sudo chmod 664 /etc/systemd/system/start_chatty.service
sudo systemctl daemon-reload
sudo systemctl enable start_chatty.service
sudo cp run_chatty.sh /etc/profile.d
sudo chmod +x /etc/profile.d/run_chatty.sh
