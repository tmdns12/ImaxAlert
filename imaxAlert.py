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
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GIST_ID = os.getenv("GIST_ID", "")
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
            print(f"로컬 상태 파일 로드 실패: {e}")
    
    if GITHUB_TOKEN and GIST_ID:
        try:
            url = f"https://api.github.com/gists/{GIST_ID}"
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                gist_data = response.json()
                content = gist_data['files']['imax_state.json']['content']
                return json.loads(content)
        except Exception as e:
            print(f"Gist 로드 오류: {e}")
    
    return {}


def save_current_state(date_states, movie_states):
    state = {
        'dates': date_states,
        'movies': movie_states,
        'last_updated': datetime.now().isoformat()
    }
    
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"로컬 상태 파일 저장 실패: {e}")
    
    if GITHUB_TOKEN and GIST_ID:
        try:
            url = f"https://api.github.com/gists/{GIST_ID}"
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            data = {
                "files": {
                    "imax_state.json": {
                        "content": json.dumps(state, ensure_ascii=False, indent=2)
                    }
                }
            }
            response = requests.patch(url, headers=headers, json=data, timeout=10)
            if response.status_code != 200:
                print(f"Gist 저장 실패: {response.status_code}")
        except Exception as e:
            print(f"Gist 저장 오류: {e}")


def init_driver():
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    if os.getenv("RENDER"):
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        try:
            driver_path = ChromeDriverManager().install()
            search_dir = os.path.dirname(driver_path) if os.path.isfile(driver_path) else driver_path
            
            chromedriver_exe = None
            if os.path.isdir(search_dir):
                for root, dirs, files in os.walk(search_dir):
                    for file in files:
                        if file == "chromedriver" and not any(x in root.upper() for x in ["THIRD_PARTY", "NOTICES"]):
                            candidate = os.path.join(root, file)
                            try:
                                with open(candidate, 'rb') as f:
                                    if f.read(4) == b'\x7fELF':
                                        chromedriver_exe = candidate
                                        break
                            except:
                                continue
                    if chromedriver_exe:
                        break
            
            if chromedriver_exe:
                os.chmod(chromedriver_exe, 0o755)
                service = Service(chromedriver_exe)
                driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            print(f"ChromeDriver 초기화 실패, 재시도: {e}")
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


def scrape_imax_shows(driver, date_key=None):
    """현재 선택된 날짜의 IMAX 상영 정보 수집"""
    try:
        time.sleep(1)  # 페이지 로딩 대기
        if date_key is None:
            current_date = get_selected_date(driver)
        else:
            current_date = date_key
        
        movie_containers = driver.find_elements(By.CSS_SELECTOR, "div.accordion_container__W7nEs")
        movies_data = []
        
        for container in movie_containers:
            try:
                # 영화 제목 먼저 찾기
                movie_title = container.find_element(By.CSS_SELECTOR, "h2 .screenInfo_title__Eso6_ .title2").text.strip()
                
                # 아코디언 펼치기
                accordion_btn = container.find_element(By.CSS_SELECTOR, "h2.accordion_accordionTitleArea__AmnDj button")
                is_expanded = accordion_btn.get_attribute("aria-expanded") == "true"
                if not is_expanded:
                    driver.execute_script("arguments[0].click();", accordion_btn)
                    time.sleep(0.5)  # 아코디언 펼친 후 DOM 업데이트 대기
                
                # IMAX 정보 확인
                try:
                    imax_theater_full = container.find_element(By.CSS_SELECTOR, "div.screenInfo_contentWrap__95SyT h3.screenInfo_title__Eso6_").text.strip()
                    if "IMAX" not in imax_theater_full.upper():
                        continue
                    imax_info_parts = imax_theater_full.replace("IMAX관", "").strip().replace(" / ", ", ")
                except:
                    continue
                
                # 상영시간 수집
                time_items = container.find_elements(By.CSS_SELECTOR, "ul.screenInfo_timeWrap__7GTHr li.screenInfo_timeItem__y8ZXg")
                show_times = []
                for item in time_items:
                    try:
                        start = item.find_element(By.CSS_SELECTOR, ".screenInfo_start__6BZbu").text
                        end = item.find_element(By.CSS_SELECTOR, ".screenInfo_end__qwvX0").text
                        try:
                            seat_info = item.find_element(By.CSS_SELECTOR, ".screenInfo_status__lT4zd").text.strip() or "-"
                        except:
                            seat_info = "-"
                        show_times.append(f"{start} {end} | {seat_info}")
                    except:
                        continue
                
                if show_times:
                    movies_data.append({
                        'date': current_date,
                        'title': movie_title,
                        'theater_info': imax_info_parts,
                        'times': show_times
                    })
            except:
                continue

        return movies_data
    except Exception as e:
        return []


def scrape_all_dates_from_html(driver, enabled_dates):
    """각 날짜를 클릭하면서 모든 날짜의 데이터 수집"""
    try:
        print(f"활성화된 날짜 {len(enabled_dates)}개 수집 중...")
        all_movies_data = []
        
        for idx, date_info in enumerate(enabled_dates):
            try:
                date_key = date_info['date']
                date_buttons = driver.find_elements(By.CSS_SELECTOR, ".dayScroll_container__e9cLv button.dayScroll_scrollItem__IZ35T")
                target_button = None
                
                for btn in date_buttons:
                    try:
                        day_txt = btn.find_element(By.CSS_SELECTOR, ".dayScroll_txt__GEtA0").text.strip()
                        day_num = btn.find_element(By.CSS_SELECTOR, ".dayScroll_number__o8i9s").text.strip()
                    except:
                        btn_text = btn.text.strip()
                        parts = btn_text.split()
                        if len(parts) >= 2:
                            day_txt, day_num = parts[0], parts[1]
                        else:
                            continue
                    
                    if day_txt and day_num:
                        btn_date_key = f"{day_txt} {day_num}"
                        if btn_date_key == date_key:
                            class_attr = btn.get_attribute("class") or ""
                            is_disabled = "dayScroll_disabled__t8HIQ" in class_attr or btn.get_attribute("disabled") is not None
                            if not is_disabled:
                                target_button = btn
                                break
                
                if not target_button and date_info.get('button'):
                    try:
                        date_info['button'].is_displayed()
                        target_button = date_info['button']
                    except:
                        pass
                
                if not target_button:
                    continue
                
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_button)
                time.sleep(0.2)
                driver.execute_script("arguments[0].click();", target_button)
                time.sleep(1.5)  # 날짜 변경 후 페이지 업데이트 대기 시간 증가
                
                shows = scrape_imax_shows(driver, date_key)
                if shows:
                    all_movies_data.extend(shows)
                    print(f"  [{idx+1}/{len(enabled_dates)}] {date_key}: {len(shows)}개 영화")
                    
            except Exception as e:
                print(f"  날짜 '{date_info['date']}' 처리 실패: {e}")
                continue
        
        return all_movies_data
        
    except Exception as e:
        print(f"날짜 데이터 수집 실패: {e}")
        return []


def get_all_date_info(driver):
    """모든 날짜 정보 수집"""
    try:
        all_dates = []
        unique_dates = set()
        
        try:
            swiper_container = driver.find_element(By.CSS_SELECTOR, ".dayScroll_container__e9cLv .swiper")
            total_slides = driver.execute_script("""
                var container = arguments[0];
                var swiper = container.swiper || document.querySelector('.dayScroll_container__e9cLv .swiper')?.swiper;
                return swiper?.slides?.length || container.querySelectorAll('.swiper-slide').length || 0;
            """, swiper_container)
            
            if total_slides > 0:
                for slide_idx in range(total_slides):
                    try:
                        driver.execute_script("""
                            var container = arguments[0];
                            var swiper = container.swiper || document.querySelector('.dayScroll_container__e9cLv .swiper')?.swiper;
                            if (swiper?.slideTo) swiper.slideTo(arguments[1], 0);
                        """, swiper_container, slide_idx)
                        time.sleep(0.1)
                    except:
                        pass
        except:
            pass
        
        date_buttons = driver.find_elements(By.CSS_SELECTOR, ".dayScroll_container__e9cLv button.dayScroll_scrollItem__IZ35T")
        
        for btn in date_buttons:
            try:
                class_attr = btn.get_attribute("class") or ""
                is_disabled = "dayScroll_disabled__t8HIQ" in class_attr or btn.get_attribute("disabled") is not None
                
                try:
                    day_txt = btn.find_element(By.CSS_SELECTOR, ".dayScroll_txt__GEtA0").text.strip()
                    day_num = btn.find_element(By.CSS_SELECTOR, ".dayScroll_number__o8i9s").text.strip()
                except:
                    btn_text = btn.text.strip()
                    parts = btn_text.split()
                    if len(parts) >= 2:
                        day_txt, day_num = parts[0], parts[1]
                    else:
                        continue
                
                if not day_txt or not day_num:
                    continue
                
                date_key = f"{day_txt} {day_num}"
                if date_key in unique_dates:
                    continue
                unique_dates.add(date_key)
                
                all_dates.append({
                    'date': date_key,
                    'enabled': not is_disabled,
                    'button': btn if not is_disabled else None
                })
            except:
                continue
        
        return all_dates
    except Exception as e:
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
    
    # 날짜 상태 저장
    current_date_states = {}
    for date_info in all_date_info:
        current_date_states[date_info['date']] = date_info['enabled']
    
    enabled_dates = [d for d in all_date_info if d['enabled'] and d['button']]
    
    all_movies_current = scrape_all_dates_from_html(driver, enabled_dates)
    
    if not previous_state:
        print("첫 실행: 초기 상태 저장")
        save_current_state(current_date_states, all_movies_current)
        driver.quit()
        return
    
    def extract_time_only(time_str):
        """시간대 문자열에서 시간 부분만 추출"""
        return time_str.split(" | ")[0] if " | " in time_str else time_str
    
    prev_movie_times = {}
    if 'movies' in previous_state:
        for movie in previous_state['movies']:
            key = f"{movie['date']}|{movie['title']}|{movie.get('theater_info', '')}"
            prev_times_set = set()
            for time_str in movie.get('times', []):
                prev_times_set.add(extract_time_only(time_str))
            prev_movie_times[key] = prev_times_set
    
    new_showtimes = []
    
    for movie in all_movies_current:
        movie_date = movie['date']
        key = f"{movie_date}|{movie['title']}|{movie.get('theater_info', '')}"
        
        current_times_set = set()
        current_times_full = {}
        for time_str in movie.get('times', []):
            time_only = extract_time_only(time_str)
            current_times_set.add(time_only)
            current_times_full[time_only] = time_str
        
        if key in prev_movie_times:
            prev_times = prev_movie_times[key]
            new_times_only = current_times_set - prev_times
            if new_times_only:
                new_times_full = [current_times_full[t] for t in new_times_only]
                new_showtimes.append({
                    'date': movie_date,
                    'title': movie['title'],
                    'theater_info': movie.get('theater_info', ''),
                    'new_times': new_times_full
                })
    
    if new_showtimes:
        by_date = {}
        for item in new_showtimes:
            date = item['date']
            if date not in by_date:
                by_date[date] = []
            by_date[date].append(item)
        
        for date, items in sorted(by_date.items()):
            msg_parts = ["⏰ 새로운 상영시간이 추가되었습니다!\n", f"📅 {date}\n"]
            
            for item in items:
                title = f"{item['title']} ({item['theater_info']})" if item['theater_info'] else item['title']
                msg_parts.append(title)
                for time_info in item['new_times']:
                    msg_parts.append(f"  {time_info}")
                msg_parts.append("")
            
            send_telegram_message("\n".join(msg_parts).strip())
            print(f"알림 전송: {date}")
        
        print(f"새로운 상영시간: {len(new_showtimes)}건")
    else:
        print("변화 없음")
    
    save_current_state(current_date_states, all_movies_current)

    driver.quit()


if __name__ == "__main__":
    main()
