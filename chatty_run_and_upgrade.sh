#!/bin/bash
cd /home/chatty/chatty-friend

while true; do
    bin/python chatty_friend.py
    exit_code=$?
    
    if [ $exit_code -eq 2 ]; then
        echo "Upgrade and restart."
        git pull
        bin/pip install -r requirements.txt
        cp run_chatty.sh /etc/profile.d
        chmod +x /etc/profile.d/run_chatty.sh
    elif [ $exit_code -eq 3 ] || [ $exit_code -eq 0 ]; then
        echo "Exiting without restart (code $exit_code)"
        break
    else
        echo "Application exited with code $exit_code. Waiting 5 seconds before restart."
        sleep 5
    fi
done