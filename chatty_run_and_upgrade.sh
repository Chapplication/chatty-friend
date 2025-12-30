#!/bin/bash
cd /home/chatty/chatty-friend

while true; do
    bin/python chatty_friend.py
    exit_code=$?
    
    if [ $exit_code -eq 2 ]; then
        echo "Upgrade and restart."
        git pull
        bin/pip install -r requirements.txt
    elif [ $exit_code -eq 3 ] || [ $exit_code -eq 0 ]; then
        echo "Exiting without restart (code $exit_code)"
        break
    else
        echo "Application exited with code $exit_code. Checking for updates before restart."
        git pull
        bin/pip install -r requirements.txt --quiet
        sleep 5
    fi
done