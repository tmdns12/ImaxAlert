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

CHROMEDRIVER_PATH = r"C:\Users\24011\Downloads\chromedriver-win64\chromedriver.exe"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8445210236:AAEmUtaJ4vGlbBlUKaS8wBVC0XCZyJMlUrs")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7980674556")
STATE_FILE = "imax_state.json"


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text
    }
    requests.post(url, data=payload)


def load_previous_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"상태 파일 로드 실패: {e}")
            return {}
    return {}


def save_current_state(date_states, movie_states):
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


def init_driver():
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    if os.getenv("RENDER"):
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=chrome_options)
    else:
        chrome_options.add_argument("--start-maximized")
        if os.path.exists(CHROMEDRIVER_PATH):
            service = Service(CHROMEDRIVER_PATH)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
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
        filter_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((
                By.XPATH,
                "//div[contains(@class,'cnms01510_movieTitleWrap__69alk')]//button"
            ))
        )
        
        current_label = filter_btn.find_element(By.TAG_NAME, "span").text
        if current_label == "아이맥스":
            print("IMAX 필터 이미 적용됨")
            return
        
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", filter_btn)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", filter_btn)
        time.sleep(1)

        imax_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((
                By.XPATH,
                "//section[contains(@class,'bot-modal-container')]//button[text()='아이맥스']"
            ))
        )
        driver.execute_script("arguments[0].click();", imax_btn)
        time.sleep(0.5)

        confirm_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((
                By.XPATH,
                "//section[contains(@class,'bot-modal-container')]//button[contains(text(),'확인')]"
            ))
        )
        driver.execute_script("arguments[0].click();", confirm_btn)
        time.sleep(1)

        WebDriverWait(driver, 10).until(
            EC.text_to_be_present_in_element(
                (By.XPATH, "//div[contains(@class,'cnms01510_movieTitleWrap__69alk')]//button//span"),
                "아이맥스"
            )
        )
        print("IMAX 필터 적용 완료")
    except Exception as e:
        print(f"IMAX 필터 적용 실패: {e}")


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
                movie_title = container.find_element(
                    By.CSS_SELECTOR, "h2 .screenInfo_title__Eso6_ .title2"
                ).text.strip()
                
                accordion_btn = container.find_element(
                    By.CSS_SELECTOR, "h2.accordion_accordionTitleArea__AmnDj button"
                )
                
                is_expanded = accordion_btn.get_attribute("aria-expanded") == "true"
                if not is_expanded:
                    driver.execute_script("arguments[0].click();", accordion_btn)
                    time.sleep(1)
                
                imax_theater_full = container.find_element(
                    By.CSS_SELECTOR, "div.screenInfo_contentWrap__95SyT h3.screenInfo_title__Eso6_"
                ).text.strip()
                
                if "IMAX" not in imax_theater_full.upper():
                    continue
                
                imax_info_parts = imax_theater_full.replace("IMAX관", "").strip().replace(" / ", ", ")
                
                time_items = container.find_elements(
                    By.CSS_SELECTOR, "ul.screenInfo_timeWrap__7GTHr li.screenInfo_timeItem__y8ZXg"
                )
                
                show_times = []
                for item in time_items:
                    try:
                        start = item.find_element(By.CSS_SELECTOR, ".screenInfo_start__6BZbu").text
                        end = item.find_element(By.CSS_SELECTOR, ".screenInfo_end__qwvX0").text
                        
                        try:
                            status_elem = item.find_element(By.CSS_SELECTOR, ".screenInfo_status__lT4zd")
                            seat_info = status_elem.text.strip() or "-"
                        except:
                            seat_info = "-"
                        
                        show_times.append(f"{start} ~ {end} | {seat_info}")
                    except Exception as e:
                        print(f"상영시간 파싱 오류: {e}")
                        continue
                
                if show_times:
                    movies_data.append({
                        'date': current_date,
                        'title': movie_title,
                        'theater_info': imax_info_parts,
                        'times': show_times
                    })
                    print(f"  수집: {movie_title} - {len(show_times)}개 상영")
            except Exception as e:
                print(f"영화 정보 파싱 중 오류: {e}")
                continue

        return movies_data

    except Exception as e:
        print("IMAX 정보 파싱 실패:", e)
        return []


def get_all_date_info(driver):
    try:
        all_dates = []
        date_buttons = driver.find_elements(By.CSS_SELECTOR, "button.dayScroll_scrollItem__IZ35T")
        
        for btn in date_buttons:
            try:
                is_disabled = "dayScroll_disabled__t8HIQ" in btn.get_attribute("class")
                day_txt = btn.find_element(By.CSS_SELECTOR, ".dayScroll_txt__GEtA0").text
                day_num = btn.find_element(By.CSS_SELECTOR, ".dayScroll_number__o8i9s").text
                date_key = f"{day_txt} {day_num}"
                
                all_dates.append({
                    'date': date_key,
                    'enabled': not is_disabled,
                    'button': btn if not is_disabled else None
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

    all_date_info = get_all_date_info(driver)
    print(f"전체 날짜 수: {len(all_date_info)}개")
    
    previous_state = load_previous_state()
    
    newly_enabled_dates = []
    current_date_states = {}
    
    for date_info in all_date_info:
        date_key = date_info['date']
        is_enabled = date_info['enabled']
        current_date_states[date_key] = is_enabled
        
        if previous_state and 'dates' in previous_state:
            prev_enabled = previous_state['dates'].get(date_key, False)
            if not prev_enabled and is_enabled:
                newly_enabled_dates.append(date_info)
                print(f"새로 열린 날짜: {date_key}")
    
    all_movies_current = []
    enabled_dates = [d for d in all_date_info if d['enabled'] and d['button']]
    
    print(f"활성화된 날짜 {len(enabled_dates)}개 체크 중...")
    for date_info in enabled_dates:
        try:
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable(date_info['button']))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", date_info['button'])
            time.sleep(1)
            driver.execute_script("arguments[0].click();", date_info['button'])
            time.sleep(2)
            
            shows = scrape_imax_shows(driver)
            all_movies_current.extend(shows)
            print(f"날짜 '{date_info['date']}' 체크 완료: {len(shows)}개 영화")
        except Exception as e:
            print(f"날짜 '{date_info['date']}' 처리 실패: {e}")
            continue
    
    if not previous_state:
        print("첫 실행: 상태 저장 (알림 없음)")
        save_current_state(current_date_states, all_movies_current)
        driver.quit()
        return
    
    new_date_movies = []
    new_showtimes = []
    
    if newly_enabled_dates:
        newly_enabled_date_keys = [d['date'] for d in newly_enabled_dates]
        for movie in all_movies_current:
            if movie['date'] in newly_enabled_date_keys:
                new_date_movies.append(movie)
    
    if previous_state and 'movies' in previous_state:
        prev_movie_times = {}
        for movie in previous_state['movies']:
            key = f"{movie['date']}|{movie['title']}|{movie.get('theater_info', '')}"
            prev_movie_times[key] = set(movie.get('times', []))
        
        for movie in all_movies_current:
            key = f"{movie['date']}|{movie['title']}|{movie.get('theater_info', '')}"
            current_times = set(movie.get('times', []))
            
            if key in prev_movie_times:
                new_times = current_times - prev_movie_times[key]
                if new_times and movie['date'] not in [d['date'] for d in newly_enabled_dates]:
                    new_showtimes.append({
                        'date': movie['date'],
                        'title': movie['title'],
                        'theater_info': movie.get('theater_info', ''),
                        'new_times': list(new_times)
                    })
    
    has_updates = False
    msg_parts = []
    
    if new_date_movies:
        has_updates = True
        msg_parts.append("🔔 새로운 예매 날짜가 열렸습니다!\n")
        
        by_date = {}
        for movie in new_date_movies:
            date = movie.get('date', '')
            if date not in by_date:
                by_date[date] = []
            by_date[date].append(movie)
        
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
    
    if new_showtimes:
        has_updates = True
        if msg_parts:
            msg_parts.append("\n" + "="*30 + "\n")
        msg_parts.append("⏰ 새로운 상영시간이 추가되었습니다!\n")
        
        for item in new_showtimes:
            msg_parts.append(f"📅 {item['date']}")
            if item['theater_info']:
                msg_parts.append(f"{item['title']} ({item['theater_info']})")
            else:
                msg_parts.append(item['title'])
            for time_info in item['new_times']:
                msg_parts.append(f"  {time_info}")
            msg_parts.append("")
    
    # 알림 전송
    if has_updates:
        msg = "\n".join(msg_parts).strip()
        send_telegram_message(msg)
        print("알림 전송 완료")
        
        if new_date_movies:
            print(f"  - 새로 열린 날짜: {len(newly_enabled_dates)}개")
        if new_showtimes:
            print(f"  - 새로운 상영시간: {len(new_showtimes)}건")
    else:
        print("변화 없음")
    
    save_current_state(current_date_states, all_movies_current)
    print("상태 저장 완료")

    driver.quit()


if __name__ == "__main__":
    main()
