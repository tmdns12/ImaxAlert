#!/bin/bash

# 첫 실행
python imaxAlert.py

# 이후 1분마다 실행
while true; do
    sleep 60
    python imaxAlert.py
done

