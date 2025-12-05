#!/bin/bash

echo "Starting IMAX Alert Bot..."

while true; do
    echo "========================================="
    echo "$(date): 체크 시작"
    
    python imaxAlert.py
    
    echo "$(date): 체크 완료, 60초 대기..."
    sleep 60
done

