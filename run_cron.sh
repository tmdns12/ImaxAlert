#!/bin/bash
set -e

echo "Starting IMAX Alert Bot..."

# Git 설정
git config --global user.email "bot@render.com"
git config --global user.name "Render Bot"

# 무한 루프
while true; do
    echo "========================================="
    echo "$(date): 체크 시작"
    
    # 최신 상태 파일 pull
    git pull origin main --rebase --autostash 2>&1 || echo "Pull failed (continuing...)"
    
    # 스크립트 실행
    python imaxAlert.py
    
    # 상태 파일 push
    if [ -f "imax_state.json" ]; then
        git add imax_state.json 2>&1 || true
        git diff --staged --quiet || {
            git commit -m "Update state $(date +%Y%m%d_%H%M%S)" 2>&1
            git push origin main 2>&1 || echo "Push failed (continuing...)"
        }
    fi
    
    echo "$(date): 체크 완료, 60초 대기..."
    sleep 60
done

