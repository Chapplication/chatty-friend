cd /home/chatty/chatty-friend

bin/python chatty_friend.py
exit_code=$?

if [ $exit_code -eq 2 ]; then
    echo "Upgrade and restart."
    git pull
    bin/pip install -r requirements.txt
    sudo cp run_chatty.sh /etc/profile.d
    sudo chmod +x /etc/profile.d/run_chatty.sh
    exec "$0" "${@}"
elif [ $exit_code -eq 3 ]; then
    echo "Config mode - exit without restarting."
elif [ $exit_code -eq 0 ]; then
    echo "Master quit - exit without restarting."
else
    echo "Application exited with code $exit_code. Waiting 5 seconds before restart."
    sleep 5
    exec "$0" "${@}"
fi