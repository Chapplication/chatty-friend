#!/bin/bash
cd /home/chatty/chatty-friend

# Wait for network to come up on boot
sleep 10

while true; do
    bin/python chatty_friend.py
    exit_code=$?
    
    if [ $exit_code -eq 2 ]; then
        echo "Upgrade and restart."
        git fetch
        git reset --hard origin/main
        bin/pip install -r requirements.txt
    elif [ $exit_code -eq 3 ] || [ $exit_code -eq 0 ]; then
        echo "Exiting without restart (code $exit_code)"
        break
    else
        echo "Application exited with code $exit_code. Checking for updates before restart."
        git fetch
        git reset --hard origin/main
        bin/pip install -r requirements.txt --quiet
        sleep 5
    fi
done