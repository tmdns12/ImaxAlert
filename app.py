#!/usr/bin/env python3
"""
CGV IMAX Alert Bot - Flask Web Server for Render Health Check
"""
import os
import sys
import threading
import time
import logging
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
    
    # 첫 실행 전 대기 (헬스체크가 먼저 응답할 수 있도록)
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}] 첫 체크 전 5초 대기 (헬스체크 준비 시간)", flush=True)
    time.sleep(5)
    
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
    """Render health check 엔드포인트 - 빠른 응답을 위해 간단한 응답"""
    # 헬스체크는 빠르게 응답 (상태 정보는 선택적)
    # 봇이 데이터 수집 중이어도 헬스체크는 즉시 응답해야 함
    # Flask는 threaded=True로 실행되므로 백그라운드 작업과 독립적으로 응답 가능
    try:
        response_data = {
            "status": "ok",
            "service": "CGV IMAX Alert Bot",
            "bot_status": bot_status
        }
        # 데이터 수집 중이어도 헬스체크는 즉시 응답
        return jsonify(response_data), 200
    except Exception:
        # 오류 발생 시에도 빠르게 응답
        return jsonify({"status": "ok"}), 200

@app.route("/health")
def health():
    """Health check 엔드포인트"""
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    # Flask 서버가 먼저 시작되도록 설정
    port = int(os.getenv("PORT", 10000))
    
    # 백그라운드 스레드에서 봇 실행 (Flask 시작 후)
    def start_bot_after_delay():
        time.sleep(5)  # Flask가 완전히 시작될 시간 확보
        bot_thread = threading.Thread(target=run_bot_loop, daemon=True)
        bot_thread.start()
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}] 봇 백그라운드 스레드 시작됨", flush=True)
    
    # 별도 스레드에서 봇 시작 스케줄링
    threading.Thread(target=start_bot_after_delay, daemon=True).start()
    
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}] Flask 서버 시작 중... (포트: {port})", flush=True)
    
    # Werkzeug 로거 설정: 봇 실행 중에는 헬스체크 로그 출력 안 함
    log = logging.getLogger('werkzeug')
    original_log = log.log
    
    def quiet_log(level, msg, *args, **kwargs):
        # 봇이 실행 중이고 헬스체크 요청이면 로그 출력 안 함
        if bot_status.get("running", False):
            # 로그 메시지 형식: "IP - - [날짜] \"GET / HTTP/1.1\" 200 -"
            try:
                if args:
                    # args가 있으면 msg % args 형식으로 포맷팅
                    msg_str = str(msg) % args if args else str(msg)
                else:
                    msg_str = str(msg)
                
                # 헬스체크 요청 로그 필터링
                if 'GET / HTTP/1.1' in msg_str or 'GET /health HTTP/1.1' in msg_str:
                    return
            except:
                # 포맷팅 실패 시 원본 메시지 확인
                msg_str = str(msg)
                if 'GET / HTTP/1.1' in msg_str or 'GET /health HTTP/1.1' in msg_str:
                    return
        original_log(level, msg, *args, **kwargs)
    
    log.log = quiet_log
    
    # Flask 서버 실행
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)

