#!/usr/bin/env python3
"""
CGV IMAX Alert Bot - Flask Web Server for Render Health Check
"""
import os
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
    
    while True:
        try:
            bot_status["running"] = True
            bot_status["error"] = None
            bot_status["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            
            print(f"[{bot_status['last_check']}] IMAX 체크 시작")
            run_imax_check()
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}] IMAX 체크 완료")
            
        except Exception as e:
            error_msg = str(e)
            bot_status["error"] = error_msg
            print(f"봇 실행 중 오류: {error_msg}")
        
        finally:
            bot_status["running"] = False
        
        # 60초 대기
        time.sleep(60)

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

