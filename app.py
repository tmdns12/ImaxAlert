#!/usr/bin/env python3
"""
CGV IMAX Alert Bot - Flask Web Server for Render Health Check
"""
import os
import sys
import threading
import time
from flask import Flask, jsonify

# imaxAlert 모듈에서 main 함수 import
from imaxAlert import main as run_imax_check

app = Flask(__name__)

# 봇 실행 상태
bot_status = {
    "running": False,
    "last_check": None,
    "error": None
}

def run_bot_loop():
    """백그라운드에서 봇을 주기적으로 실행"""
    global bot_status
    
    check_interval = 30  # 30초마다 체크
    last_check_time = None
    
    # 출력 버퍼링 비활성화
    sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None
    
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}] 봇 루프 시작 - {check_interval}초 간격으로 체크", flush=True)
    
    while True:
        try:
            current_time = time.time()
            if last_check_time:
                elapsed = current_time - last_check_time
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}] 다음 체크까지 대기 중... (이전 체크로부터 {elapsed:.1f}초 경과)", flush=True)
            
            bot_status["running"] = True
            bot_status["error"] = None
            bot_status["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            
            check_start_time = time.time()
            print(f"[{bot_status['last_check']}] IMAX 체크 시작 (예상 간격: {check_interval}초)", flush=True)
            run_imax_check()
            check_duration = time.time() - check_start_time
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}] IMAX 체크 완료 (소요 시간: {check_duration:.1f}초)", flush=True)
            
        except Exception as e:
            error_msg = str(e)
            bot_status["error"] = error_msg
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}] 봇 실행 중 오류: {error_msg}", flush=True)
        
        finally:
            bot_status["running"] = False
            last_check_time = time.time()
        
        # 60초 대기
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}] {check_interval}초 대기 중...", flush=True)
        time.sleep(check_interval)

@app.route("/")
def health_check():
    """Render health check 엔드포인트"""
    return jsonify({
        "status": "ok",
        "service": "CGV IMAX Alert Bot",
        "bot_status": bot_status
    }), 200

@app.route("/health")
def health():
    """Health check 엔드포인트"""
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    # 백그라운드 스레드에서 봇 실행
    bot_thread = threading.Thread(target=run_bot_loop, daemon=True)
    bot_thread.start()
    print("봇 백그라운드 스레드 시작됨")
    
    # Flask 서버 실행
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)

