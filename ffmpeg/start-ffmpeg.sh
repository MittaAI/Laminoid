#!/bin/bash

while true; do
    screen -dmS gunicorn_ffmpeg gunicorn -b 0.0.0.0:6969 ffmpeg:app -w 2 --timeout 120
    sleep 1
    
    while screen -list | grep -q gunicorn_ffmpeg; do
        sleep 10
    done
    
    echo "Gunicorn exited. Restarting..."
    sleep 5
done