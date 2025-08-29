#!/bin/bash
cd /home/chatty-friend

while true; do
    bin/python run_chatty_web.py
    exit_code=$?
    
    echo "Web server exited with code $exit_code. Waiting 5 seconds before restart."
    sleep 5
done