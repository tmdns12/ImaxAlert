import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
import os
from datetime import datetime

# ChromeDriver 경로 (로컬/서버 자동 감지)
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH", r"C:\Users\24011\Downloads\chromedriver-win64\chromedriver.exe")

# 텔레그램 설정 (환경변수 우선, 없으면 기본값)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8445210236:AAEmUtaJ4vGlbBlUKaS8wBVC0XCZyJMlUrs")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7980674556")

# 상태 저장 파일 경로
STATE_FILE = "imax_state.json"


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }
    requests.post(url, data=payload)


def load_previous_state():
    """이전 상태를 파일에서 로드"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"상태 파일 로드 실패: {e}")
            return {}
    return {}


def save_current_state(date_states, movie_states):
    """현재 상태를 파일에 저장 (날짜 활성화 상태 + 영화 정보)"""
    try:
        state = {
            'dates': date_states,
            'movies': movie_states,
            'last_updated': datetime.now().isoformat()
        }
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"상태 파일 저장 실패: {e}")


def compare_states(previous_state, current_state):
    """이전 상태와 현재 상태를 비교하여 새로 추가된 항목 찾기"""
    new_items = []
    
    # 이전 상태가 비어있으면 초기화만 하고 알림 없음
    if not previous_state:
        print("첫 실행: 현재 상태를 저장합니다 (알림 없음)")
        return []
    
    # 이전 상태를 리스트로 변환
    if isinstance(previous_state, dict):
        if 'dates' in previous_state:
            prev_dates = previous_state['dates']
            prev_movies = previous_state.get('movies', [])
        else:
            prev_dates = {}
            prev_movies = list(previous_state.values()) if previous_state else []
    else:
        prev_dates = {}
        prev_movies = previous_state if isinstance(previous_state, list) else []
    
    # 현재 상태를 날짜별로 정리
    current_by_date = {}
    for movie in current_state:
        date = movie.get('date', '')
        if date not in current_by_date:
            current_by_date[date] = []
        current_by_date[date].append(movie)
    
    # 이전 상태도 날짜별로 정리
    previous_by_date = {}
    for movie in prev_movies:
        date = movie.get('date', '')
        if date not in previous_by_date:
            previous_by_date[date] = []
        previous_by_date[date].append(movie)
    
    # 새 날짜 확인
    for date in current_by_date:
        if date not in previous_by_date:
            # 완전히 새로운 날짜
            new_items.append({
                'type': 'new_date',
                'date': date,
                'movies': current_by_date[date]
            })
        else:
            # 기존 날짜에서 새 영화나 새 상영시간 확인
            prev_movies = {m['title'] + '|' + m.get('theater_info', ''): m for m in previous_by_date[date]}
            
            for curr_movie in current_by_date[date]:
                movie_key = curr_movie['title'] + '|' + curr_movie.get('theater_info', '')
                
                if movie_key not in prev_movies:
                    # 새 영화
                    new_items.append({
                        'type': 'new_movie',
                        'date': date,
                        'movie': curr_movie
                    })
                else:
                    # 기존 영화에서 새 상영시간 확인
                    prev_times = set(prev_movies[movie_key].get('times', []))
                    curr_times = set(curr_movie.get('times', []))
                    new_times = curr_times - prev_times
                    
                    if new_times:
                        new_items.append({
                            'type': 'new_showtime',
                            'date': date,
                            'movie': {
                                'title': curr_movie['title'],
                                'theater_info': curr_movie.get('theater_info', ''),
                                'times': list(new_times)
                            }
                        })
    
    return new_items


def init_driver():
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # 서버 환경 (GitHub Actions, Render 등)에서는 headless 모드 사용
    if os.getenv("GITHUB_ACTIONS") or os.getenv("RENDER"):
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-extensions")
        # Render 환경에서는 시스템 ChromeDriver 사용
        driver = webdriver.Chrome(options=chrome_options)
    else:
        # 로컬 환경
        chrome_options.add_argument("--start-maximized")
        if os.path.exists(CHROMEDRIVER_PATH):
            service = Service(CHROMEDRIVER_PATH)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            # ChromeDriver 없으면 자동 설치
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
    
    return driver

def select_region_seoul(driver):
    try:
        seoul_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((
                By.XPATH, "//li/button[contains(., '서울')]"
            ))
        )
        seoul_btn.click()
        print("서울 선택 성공")
    except Exception as e:
        print("서울 선택 실패:", e)


def select_yeongdeungpo(driver):
    try:
        yd_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((
                By.XPATH, "//button[p[text()='영등포타임스퀘어']]"
            ))
        )
        yd_btn.click()
        print("영등포타임스퀘어 선택 성공")
    except Exception as e:
        print("영등포 선택 실패:", e)


def click_imax_filter(driver):
    try:
        # 1) “극장 속성” 버튼 열기 (라벨이 ‘전체’일 때)
        filter_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//div[contains(@class,'cnms01510_movieTitleWrap__69alk')]"
                "//button[contains(@class,'cnms01510_btn__dV0W6') and .//span[text()='전체']]"
            ))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", filter_btn)
        filter_btn.click()

        # 2) 모달 내부 ‘아이맥스’ 버튼 클릭
        imax_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//section[contains(@class,'bot-modal-container')]"
                "//button[normalize-space(text())='아이맥스']"
            ))
        )
        imax_btn.click()

        # 3) 모달 하단 ‘확인’ 버튼 클릭
        confirm_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((
                By.XPATH,
                "//section[contains(@class,'bot-modal-container')]"
                "//button[contains(@class,'btn') and contains(text(),'확인')]"
            ))
        )
        confirm_btn.click()

        # 4) 필터 버튼 라벨이 ‘아이맥스’로 바뀌었는지 확인
        WebDriverWait(driver, 10).until(
            EC.text_to_be_present_in_element(
                (
                    By.XPATH,
                    "//div[contains(@class,'cnms01510_movieTitleWrap__69alk')]"
                    "//button[contains(@class,'cnms01510_btn__dV0W6')]//span"
                ),
                "아이맥스"
            )
        )
        print("IMAX 필터 적용 완료")
    except Exception as e:
        print("IMAX 필터 적용 실패:", e)


def get_selected_date(driver):
    try:
        active = driver.find_element(
            By.CSS_SELECTOR,
            ".dayScroll_scrollItem__IZ35T.dayScroll_itemActive__fZ5Sq"
        )
        day_num = active.find_element(By.CSS_SELECTOR, ".dayScroll_number__o8i9s").text
        day_txt = active.find_element(By.CSS_SELECTOR, ".dayScroll_txt__GEtA0").text
        return f"{day_txt} {day_num}"
    except Exception as e:
        print("날짜 파싱 실패:", e)
        return "날짜 정보 없음"


def scrape_imax_shows(driver):
    try:
        time.sleep(2)
        current_date = get_selected_date(driver)
        
        # 각 영화별 아코디언 컨테이너 찾기
        movie_containers = driver.find_elements(By.CSS_SELECTOR, "div.accordion_container__W7nEs")

        movies_data = []
        for container in movie_containers:
            try:
                # h2 안에서 영화 제목 가져오기 (title2 클래스)
                movie_title = container.find_element(
                    By.CSS_SELECTOR, "h2 .screenInfo_title__Eso6_ .title2"
                ).text.strip()
                
                # h3에서 IMAX관 정보 가져오기
                imax_theater_full = container.find_element(
                    By.CSS_SELECTOR, "div.screenInfo_contentWrap__95SyT h3.screenInfo_title__Eso6_"
                ).text.strip()
                
                if "IMAX" not in imax_theater_full.upper():
                    continue
                
                # IMAX관 정보에서 괄호 안 내용 추출 (예: "IMAX관 IMAX LASER 2D / 자막" -> "IMAX LASER 2D, 자막")
                imax_info_parts = imax_theater_full.replace("IMAX관", "").strip()
                if imax_info_parts:
                    # "IMAX LASER 2D / 자막" -> "IMAX LASER 2D, 자막"
                    imax_info_parts = imax_info_parts.replace(" / ", ", ")
                
                # 시간 리스트 가져오기
                time_items = container.find_elements(
                    By.CSS_SELECTOR, "ul.screenInfo_timeWrap__7GTHr li.screenInfo_timeItem__y8ZXg"
                )
                
                show_times = []
                for item in time_items:
                    start = item.find_element(By.CSS_SELECTOR, ".screenInfo_start__6BZbu").text
                    end = item.find_element(By.CSS_SELECTOR, ".screenInfo_end__qwvX0").text
                    seat = item.find_element(By.CSS_SELECTOR, ".c-blue").text
                    total = item.find_element(By.CSS_SELECTOR, ".screenInfo_seat__NLZUL").text
                    
                    show_times.append(f"{start} ~ {end} | {seat}{total}")
                
                if show_times:
                    movies_data.append({
                        'date': current_date,
                        'title': movie_title,
                        'theater_info': imax_info_parts,
                        'times': show_times
                    })
            except Exception as e:
                print(f"영화 정보 파싱 중 오류: {e}")
                continue

        return movies_data

    except Exception as e:
        print("IMAX 정보 파싱 실패:", e)
        return []


def get_all_date_info(driver):
    """모든 날짜의 활성화 상태 가져오기"""
    try:
        all_dates = []
        date_items = driver.find_elements(By.CSS_SELECTOR, ".dayScroll_scrollItem__IZ35T")
        
        for item in date_items:
            try:
                is_disabled = "dayScroll_disabled__t8HIQ" in item.get_attribute("class")
                day_txt = item.find_element(By.CSS_SELECTOR, ".dayScroll_txt__GEtA0").text
                day_num = item.find_element(By.CSS_SELECTOR, ".dayScroll_number__o8i9s").text
                date_key = f"{day_txt} {day_num}"
                
                all_dates.append({
                    'date': date_key,
                    'enabled': not is_disabled,
                    'button': item if not is_disabled else None
                })
            except Exception as e:
                print(f"날짜 파싱 중 오류: {e}")
                continue
        
        return all_dates
    except Exception as e:
        print(f"날짜 정보 가져오기 실패: {e}")
        return []


def main():
    driver = init_driver()
    driver.get("https://cgv.co.kr/cnm/movieBook/cinema")
    time.sleep(2)

    select_region_seoul(driver)
    time.sleep(1)

    select_yeongdeungpo(driver)
    time.sleep(3)

    click_imax_filter(driver)
    time.sleep(2)

    # 모든 날짜 정보 가져오기 (활성화 여부 포함)
    all_date_info = get_all_date_info(driver)
    print(f"전체 날짜 수: {len(all_date_info)}개")
    
    # 이전 상태 로드
    previous_state = load_previous_state()
    
    # 이전에 비활성화였던 날짜 중 새로 활성화된 날짜 찾기
    newly_enabled_dates = []
    current_date_states = {}
    
    for date_info in all_date_info:
        date_key = date_info['date']
        is_enabled = date_info['enabled']
        current_date_states[date_key] = is_enabled
        
        # 이전 상태가 있고, 이전에는 비활성화였는데 지금 활성화된 경우
        if previous_state and 'dates' in previous_state:
            prev_enabled = previous_state['dates'].get(date_key, False)
            if not prev_enabled and is_enabled:
                newly_enabled_dates.append(date_info)
                print(f"🆕 새로 열린 날짜 발견: {date_key}")
    
    # 새로 열린 날짜가 있으면 해당 날짜의 상영 정보만 수집
    all_shows = []
    
    if newly_enabled_dates:
        print(f"새로 열린 날짜 {len(newly_enabled_dates)}개의 상영 정보 수집 중...")
        for date_info in newly_enabled_dates:
            if date_info['button']:
                try:
                    # 날짜 버튼 클릭
                    driver.execute_script("arguments[0].scrollIntoView(true);", date_info['button'])
                    time.sleep(0.5)
                    date_info['button'].click()
                    time.sleep(2)
                    
                    # 해당 날짜의 상영 정보 수집
                    shows = scrape_imax_shows(driver)
                    all_shows.extend(shows)
                    
                    print(f"날짜 '{date_info['date']}' 체크 완료: {len(shows)}개 영화")
                    
                except Exception as e:
                    print(f"날짜 '{date_info['date']}' 처리 중 오류: {e}")
                    continue
    else:
        print("새로 열린 날짜 없음")
    
    # 새로 열린 날짜의 상영 정보만 알림
    if all_shows:
        # 날짜별로 그룹화
        by_date = {}
        for movie in all_shows:
            date = movie.get('date', '')
            if date not in by_date:
                by_date[date] = []
            by_date[date].append(movie)
        
        # 알림 메시지 생성
        msg_parts = ["🔔 새로운 예매 날짜가 열렸습니다!\n"]
        
        for date, movies in by_date.items():
            msg_parts.append(f"📅 {date}")
            for movie in movies:
                if movie['theater_info']:
                    msg_parts.append(f"\n{movie['title']} ({movie['theater_info']})")
                else:
                    msg_parts.append(f"\n{movie['title']}")
                for time_info in movie['times']:
                    msg_parts.append(f"  {time_info}")
            msg_parts.append("")
        
        msg = "\n".join(msg_parts).strip()
        send_telegram_message(msg)
        print("새로운 날짜 오픈 알림 전송 완료")
        
        # 콘솔에도 출력
        for date, movies in by_date.items():
            print(f"📅 새 날짜: {date}")
            for movie in movies:
                print(f"  - {movie['title']}: {len(movie['times'])}개 상영")
    else:
        print("새로 열린 날짜 없음")
    
    # 현재 상태 저장 (날짜 활성화 상태 + 영화 정보)
    # 모든 날짜의 상영 정보를 저장하기 위해 전체 날짜 순회
    all_movies_for_state = []
    enabled_dates = [d for d in all_date_info if d['enabled'] and d['button']]
    
    for date_info in enabled_dates:
        try:
            driver.execute_script("arguments[0].scrollIntoView(true);", date_info['button'])
            time.sleep(0.5)
            date_info['button'].click()
            time.sleep(2)
            shows = scrape_imax_shows(driver)
            all_movies_for_state.extend(shows)
        except Exception as e:
            print(f"상태 저장용 날짜 '{date_info['date']}' 처리 중 오류: {e}")
            continue
    
    save_current_state(current_date_states, all_movies_for_state)
    print("상태 저장 완료")

    driver.quit()


if __name__ == "__main__":
    main()
