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
    # 로컬 파일 우선 체크 (개발용)
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"로컬 상태 파일 로드 실패: {e}")
    
    # Gist에서 로드 (프로덕션)
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
            else:
                print(f"Gist 로드 실패: {response.status_code}")
        except Exception as e:
            print(f"Gist 로드 오류: {e}")
    
    return {}


def save_current_state(date_states, movie_states):
    state = {
        'dates': date_states,
        'movies': movie_states,
        'last_updated': datetime.now().isoformat()
    }
    
    # 로컬 파일 저장 (개발용)
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"로컬 상태 파일 저장 실패: {e}")
    
    # Gist에 저장 (프로덕션)
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
            if response.status_code == 200:
                print("Gist 저장 완료")
            else:
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
        
        # webdriver-manager 사용 (자동으로 올바른 버전 다운로드)
        try:
            # webdriver-manager가 반환하는 경로
            driver_path = ChromeDriverManager().install()
            print(f"webdriver-manager 반환 경로: {driver_path}")
            
            # 경로가 디렉토리인 경우 chromedriver 실행 파일 찾기
            chromedriver_exe = None
            search_dir = driver_path
            
            # 반환된 경로가 파일이면 부모 디렉토리로 이동
            if os.path.isfile(driver_path):
                search_dir = os.path.dirname(driver_path)
                print(f"반환된 경로가 파일이므로 부모 디렉토리로 이동: {search_dir}")
            elif not os.path.isdir(driver_path):
                # 경로가 존재하지 않으면 부모 디렉토리 확인
                search_dir = os.path.dirname(driver_path)
                print(f"경로가 존재하지 않으므로 부모 디렉토리 확인: {search_dir}")
            
            if os.path.isdir(search_dir):
                # 일반적인 구조: search_dir/chromedriver-linux64/chromedriver
                possible_paths = [
                    os.path.join(search_dir, "chromedriver-linux64", "chromedriver"),
                    os.path.join(search_dir, "chromedriver"),
                    os.path.join(os.path.dirname(search_dir), "chromedriver-linux64", "chromedriver"),
                    os.path.join(os.path.dirname(search_dir), "chromedriver"),
                ]
                
                print(f"가능한 경로 확인 중: {possible_paths[:2]}")
                for path in possible_paths:
                    if os.path.exists(path) and os.path.isfile(path):
                        # ELF 바이너리 파일인지 확인
                        try:
                            with open(path, 'rb') as f:
                                header = f.read(4)
                                if header[0:4] == b'\x7fELF':
                                    chromedriver_exe = path
                                    print(f"ELF 실행 파일 발견: {chromedriver_exe}")
                                    break
                        except:
                            pass
                
                # 여전히 없으면 디렉토리 내에서 찾기
                if not chromedriver_exe:
                    print(f"디렉토리 내에서 검색 중: {search_dir}")
                    for root, dirs, files in os.walk(search_dir):
                        for file in files:
                            # 파일명이 정확히 "chromedriver"이고, 확장자가 없어야 함
                            if file == "chromedriver":
                                candidate = os.path.join(root, file)
                                # 경로에 THIRD_PARTY, NOTICES, .txt, .md 등이 포함된 경우 제외
                                if ("THIRD_PARTY" in candidate.upper() or 
                                    "NOTICES" in candidate.upper() or
                                    candidate.endswith(".txt") or 
                                    candidate.endswith(".md") or
                                    candidate.endswith(".chromedriver")):
                                    print(f"제외된 파일: {candidate}")
                                    continue
                                
                                # ELF 바이너리 파일인지 먼저 확인 (Linux 실행 파일)
                                try:
                                    with open(candidate, 'rb') as f:
                                        header = f.read(4)
                                        # ELF 파일 시그니처 확인 (0x7f 'ELF')
                                        if header[0:4] == b'\x7fELF':
                                            chromedriver_exe = candidate
                                            print(f"ELF 실행 파일 발견: {chromedriver_exe}")
                                            break
                                except Exception as e:
                                    print(f"파일 확인 실패 {candidate}: {e}")
                        if chromedriver_exe:
                            break
                
                if not chromedriver_exe or not os.path.exists(chromedriver_exe):
                    raise FileNotFoundError(f"ChromeDriver 실행 파일을 찾을 수 없습니다: {search_dir}")
            else:
                # 파일 경로로 직접 사용 시도
                if os.path.isfile(driver_path):
                    # ELF 바이너리인지 확인
                    try:
                        with open(driver_path, 'rb') as f:
                            header = f.read(4)
                            if header[0:4] == b'\x7fELF':
                                chromedriver_exe = driver_path
                            else:
                                raise FileNotFoundError(f"ChromeDriver가 ELF 바이너리가 아닙니다: {driver_path}")
                    except:
                        raise FileNotFoundError(f"ChromeDriver를 읽을 수 없습니다: {driver_path}")
                else:
                    raise FileNotFoundError(f"ChromeDriver를 찾을 수 없습니다: {driver_path}")
            
            print(f"사용할 ChromeDriver 경로: {chromedriver_exe}")
            
            # 실행 권한 부여
            os.chmod(chromedriver_exe, 0o755)
            
            service = Service(chromedriver_exe)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
        except Exception as e:
            print(f"webdriver-manager 사용 실패: {e}")
            print("Service 객체 없이 재시도...")
            # Service 객체 없이 시도 (webdriver-manager가 자동으로 처리)
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
        time.sleep(1)
        if date_key is None:
            current_date = get_selected_date(driver)
        else:
            current_date = date_key
        
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
                    time.sleep(0.5)
                
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
                        
                        show_times.append(f"{start} {end} | {seat_info}")
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


def scrape_all_dates_from_html(driver, enabled_dates):
    """각 날짜를 빠르게 클릭하면서 모든 날짜의 데이터 수집 (대기 시간 최소화)"""
    try:
        print(f"활성화된 날짜 {len(enabled_dates)}개를 빠르게 클릭하며 수집 중...")
        all_movies_data = []
        
        for idx, date_info in enumerate(enabled_dates):
            try:
                date_key = date_info['date']
                print(f"[{idx+1}/{len(enabled_dates)}] 날짜 '{date_key}' 처리 중...")
                
                # 저장된 버튼 객체를 우선 사용 (이미 get_all_date_info에서 찾았음)
                target_button = None
                if date_info.get('button'):
                    try:
                        btn = date_info['button']
                        btn.is_displayed()  # stale element 체크
                        target_button = btn
                    except:
                        pass
                
                # 저장된 버튼이 유효하지 않으면 다시 찾기 (fallback)
                if not target_button:
                    date_buttons = driver.find_elements(By.CSS_SELECTOR, ".dayScroll_container__e9cLv button.dayScroll_scrollItem__IZ35T")
                    found_dates = []  # 디버깅용
                    
                    for btn in date_buttons:
                        try:
                            day_txt = ""
                            day_num = ""
                            try:
                                day_txt_elem = btn.find_element(By.CSS_SELECTOR, ".dayScroll_txt__GEtA0")
                                day_txt = day_txt_elem.text.strip()
                            except:
                                pass
                            
                            try:
                                day_num_elem = btn.find_element(By.CSS_SELECTOR, ".dayScroll_number__o8i9s")
                                day_num = day_num_elem.text.strip()
                            except:
                                pass
                            
                            if not day_txt or not day_num:
                                try:
                                    btn_text = btn.text.strip()
                                    lines = [line.strip() for line in btn_text.split('\n') if line.strip()]
                                    if len(lines) >= 2:
                                        day_txt = lines[0]
                                        day_num = lines[1]
                                    elif len(lines) == 1:
                                        parts = lines[0].split()
                                        if len(parts) >= 2:
                                            day_txt = parts[0]
                                            day_num = parts[1]
                                except:
                                    pass
                            
                            if day_txt and day_num:
                                btn_date_key = f"{day_txt} {day_num}"
                                found_dates.append(btn_date_key)  # 디버깅용
                                
                                if btn_date_key == date_key:
                                    class_attr = btn.get_attribute("class") or ""
                                    is_disabled_class = "dayScroll_disabled__t8HIQ" in class_attr
                                    is_disabled_attr = btn.get_attribute("disabled") is not None
                                    if not (is_disabled_class or is_disabled_attr):
                                        target_button = btn
                                        break
                        except:
                            continue
                    
                    if not target_button:
                        print(f"  ⚠️ 날짜 '{date_key}' 버튼을 찾을 수 없음")
                        if found_dates:
                            print(f"     발견된 날짜 목록: {', '.join(found_dates[:10])}")  # 처음 10개만 출력
                        continue
                
                # 날짜 버튼 클릭
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_button)
                time.sleep(0.1)  # 스크롤 대기 시간 단축
                driver.execute_script("arguments[0].click();", target_button)
                time.sleep(0.8)  # 페이지 업데이트 대기 시간 약간 단축
                
                # 데이터 수집
                shows = scrape_imax_shows(driver, date_key)
                if shows:
                    all_movies_data.extend(shows)
                    print(f"  ✓ 날짜 '{date_key}' 체크 완료: {len(shows)}개 영화, 총 {sum(len(s.get('times', [])) for s in shows)}개 상영시간")
                else:
                    print(f"  ⚠️ 날짜 '{date_key}' 데이터 없음")
                    
            except Exception as e:
                print(f"  ✗ 날짜 '{date_info['date']}' 처리 실패: {e}")
                continue
        
        print(f"전체 수집 완료: {len(all_movies_data)}개 영화 데이터")
        return all_movies_data
        
    except Exception as e:
        print(f"HTML에서 모든 날짜 데이터 수집 실패: {e}")
        return []


def get_all_date_info(driver):
    try:
        all_dates = []
        
        # 날짜 스크롤 영역 찾기
        try:
            date_container = driver.find_element(By.CSS_SELECTOR, ".dayScroll_container__e9cLv")
            # 날짜 스크롤 영역을 화면에 보이도록 스크롤
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", date_container)
            time.sleep(0.5)
        except Exception as e:
            print(f"날짜 스크롤 영역 찾기 실패 (무시하고 계속): {e}")
        
        # Swiper 인스턴스를 찾아서 모든 슬라이드를 순회
        try:
            swiper_container = driver.find_element(By.CSS_SELECTOR, ".dayScroll_container__e9cLv .swiper")
            
            # Swiper 인스턴스의 슬라이드 개수 가져오기
            total_slides = driver.execute_script("""
                var container = arguments[0];
                // Swiper 인스턴스 찾기
                var swiper = container.swiper;
                if (!swiper && window.Swiper) {
                    // 직접 찾기
                    var swipers = document.querySelectorAll('.dayScroll_container__e9cLv .swiper');
                    for (var i = 0; i < swipers.length; i++) {
                        if (swipers[i].swiper) {
                            swiper = swipers[i].swiper;
                            break;
                        }
                    }
                }
                if (swiper && swiper.slides) {
                    return swiper.slides.length;
                }
                // DOM에서 직접 찾기
                var slides = container.querySelectorAll('.swiper-slide');
                return slides ? slides.length : 0;
            """, swiper_container)
            
            if total_slides > 0:
                print(f"Swiper 슬라이드 총 개수: {total_slides}개")
                # 각 슬라이드로 이동하여 모든 날짜 버튼이 로드되도록
                for slide_idx in range(total_slides):
                    try:
                        # 해당 슬라이드로 이동
                        driver.execute_script("""
                            var container = arguments[0];
                            var swiper = container.swiper;
                            if (!swiper) {
                                var swipers = document.querySelectorAll('.dayScroll_container__e9cLv .swiper');
                                for (var i = 0; i < swipers.length; i++) {
                                    if (swipers[i].swiper) {
                                        swiper = swipers[i].swiper;
                                        break;
                                    }
                                }
                            }
                            if (swiper && swiper.slideTo) {
                                swiper.slideTo(arguments[1], 0);  # 애니메이션 없이 즉시 이동
                            }
                        """, swiper_container, slide_idx)
                        time.sleep(0.05)  # 슬라이드 이동 대기 시간 단축
                    except:
                        pass
                
                # 모든 슬라이드를 순회한 후 첫 번째 슬라이드로 돌아가기
                try:
                    driver.execute_script("""
                        var container = arguments[0];
                        var swiper = container.swiper;
                        if (!swiper) {
                            var swipers = document.querySelectorAll('.dayScroll_container__e9cLv .swiper');
                            for (var i = 0; i < swipers.length; i++) {
                                if (swipers[i].swiper) {
                                    swiper = swipers[i].swiper;
                                    break;
                                }
                            }
                        }
                        if (swiper && swiper.slideTo) {
                            swiper.slideTo(0, 0);  # 애니메이션 없이 즉시 이동
                        }
                    """, swiper_container)
                    time.sleep(0.1)  # 첫 번째 슬라이드로 돌아가는 대기 시간 단축
                    print("첫 번째 슬라이드로 복귀 완료")
                except Exception as e:
                    print(f"첫 번째 슬라이드로 복귀 실패: {e}")
        except Exception as e:
            print(f"Swiper 슬라이드 순회 중 오류 (무시하고 계속): {e}")
        
        # 모든 날짜 버튼 찾기 (DOM에 있는 모든 버튼)
        date_buttons = driver.find_elements(By.CSS_SELECTOR, ".dayScroll_container__e9cLv button.dayScroll_scrollItem__IZ35T")
        print(f"발견된 날짜 버튼 수: {len(date_buttons)}개")
        
        # 각 버튼을 찾을 때마다 해당 버튼이 보이도록 스크롤
        found_dates = []
        unique_dates = set()  # 중복 제거를 위한 set
        skipped_count = 0
        
        for idx, btn in enumerate(date_buttons):
            try:
                # disabled 클래스와 disabled 속성 모두 확인 (더 안전)
                class_attr = btn.get_attribute("class") or ""
                is_disabled_class = "dayScroll_disabled__t8HIQ" in class_attr
                is_disabled_attr = btn.get_attribute("disabled") is not None
                is_disabled = is_disabled_class or is_disabled_attr
                
                # 날짜 텍스트 가져오기 (여러 방법 시도)
                day_txt = ""
                day_num = ""
                
                # 방법 1: CSS 선택자로 각 요소 찾기
                try:
                    day_txt_elem = btn.find_element(By.CSS_SELECTOR, ".dayScroll_txt__GEtA0")
                    day_txt = day_txt_elem.text.strip()
                except:
                    day_txt = ""
                
                try:
                    day_num_elem = btn.find_element(By.CSS_SELECTOR, ".dayScroll_number__o8i9s")
                    day_num = day_num_elem.text.strip()
                except:
                    day_num = ""
                
                # 방법 2: 요소를 찾지 못했으면 버튼의 전체 텍스트에서 추출
                if not day_txt or not day_num:
                    try:
                        btn_text = btn.text.strip()
                        # 버튼 텍스트 예: "오늘\n08" 또는 "화 09"
                        lines = [line.strip() for line in btn_text.split('\n') if line.strip()]
                        if len(lines) >= 2:
                            day_txt = lines[0]
                            day_num = lines[1]
                        elif len(lines) == 1:
                            # 공백으로 구분된 경우: "화 09"
                            parts = lines[0].split()
                            if len(parts) >= 2:
                                day_txt = parts[0]
                                day_num = parts[1]
                    except Exception as parse_error:
                        pass
                
                # 빈 날짜는 건너뛰기
                if not day_txt or not day_num:
                    skipped_count += 1
                    print(f"  날짜 버튼 {idx+1} 건너뛰기: day_txt='{day_txt}', day_num='{day_num}'")
                    continue
                
                date_key = f"{day_txt} {day_num}"
                
                # 중복 제거
                if date_key in unique_dates:
                    skipped_count += 1
                    print(f"  날짜 버튼 {idx+1} 중복 건너뛰기: {date_key}")
                    continue
                unique_dates.add(date_key)
                found_dates.append(date_key)
                
                all_dates.append({
                    'date': date_key,
                    'enabled': not is_disabled,
                    'button': btn if not is_disabled else None
                })
            except Exception as e:
                skipped_count += 1
                print(f"  날짜 버튼 {idx+1} 처리 실패: {e}")
                continue
        
        if skipped_count > 0:
            print(f"건너뛴 날짜 버튼 수: {skipped_count}개")
        
        if found_dates:
            print(f"발견된 날짜 목록: {', '.join(found_dates)}")
        
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
    
    # 날짜 상태 저장
    current_date_states = {}
    for date_info in all_date_info:
        current_date_states[date_info['date']] = date_info['enabled']
    
    enabled_dates = [d for d in all_date_info if d['enabled'] and d['button']]
    
    if not previous_state:
        print("첫 실행: 모든 데이터 수집 후 상태 저장 (알림 없음)")
        # HTML에서 모든 날짜 데이터를 한 번에 수집
        all_movies_current = scrape_all_dates_from_html(driver, enabled_dates)
        
        save_current_state(current_date_states, all_movies_current)
        print("초기 상태 저장 완료")
        driver.quit()
        return
    
    # 기존 상태가 있는 경우: HTML에서 모든 데이터 수집
    print(f"활성화된 날짜 {len(enabled_dates)}개 체크 중...")
    all_movies_current = scrape_all_dates_from_html(driver, enabled_dates)
    
    def extract_time_only(time_str):
        """시간대 문자열에서 시간 부분만 추출 (좌석수 제외)"""
        if " | " in time_str:
            return time_str.split(" | ")[0]
        return time_str
    
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
            msg_parts = []
            msg_parts.append("⏰ 새로운 상영시간이 추가되었습니다!\n")
            msg_parts.append(f"📅 {date}\n")
            
            for item in items:
                if item['theater_info']:
                    msg_parts.append(f"{item['title']} ({item['theater_info']})")
                else:
                    msg_parts.append(item['title'])
                for time_info in item['new_times']:
                    msg_parts.append(f"  {time_info}")
                msg_parts.append("")
            
            msg = "\n".join(msg_parts).strip()
            send_telegram_message(msg)
            print(f"알림 전송 완료: 새로운 상영시간 '{date}'")
        
        print(f"  - 새로운 상영시간: {len(new_showtimes)}건")
    else:
        print("변화 없음 - 알림 없음")
    
    save_current_state(current_date_states, all_movies_current)
    print("상태 저장 완료")

    driver.quit()


if __name__ == "__main__":
    main()
