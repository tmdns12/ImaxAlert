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
import re
import subprocess
import platform
from datetime import datetime

CHROMEDRIVER_PATH = r"C:\Users\24011\Downloads\chromedriver-win64\chromedriver.exe"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8445210236:AAEmUtaJ4vGlbBlUKaS8wBVC0XCZyJMlUrs")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "7980674556")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GIST_ID = os.getenv("GIST_ID", "")
STATE_FILE = "imax_state.json"

# 전역 드라이버 변수 (브라우저 유지)
_global_driver = None


def kill_existing_chrome():
    """실행 중인 크롬 프로세스 종료 (리소스 절약)"""
    try:
        system = platform.system()
        if system == "Windows":
            # Windows: taskkill 명령어 사용
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            subprocess.run(["taskkill", "/F", "/IM", "chromedriver.exe"], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        elif system == "Linux":
            # Linux: pkill 명령어 사용
            subprocess.run(["pkill", "-f", "chrome"], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            subprocess.run(["pkill", "-f", "chromedriver"], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        elif system == "Darwin":  # macOS
            # macOS: killall 명령어 사용
            subprocess.run(["killall", "Google Chrome"], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            subprocess.run(["killall", "chromedriver"], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        print("기존 크롬 프로세스 종료 완료")
        time.sleep(1)  # 프로세스 종료 대기
    except Exception as e:
        # 프로세스 종료 실패는 무시 (이미 종료되었거나 권한 문제일 수 있음)
        pass


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
    # 저장 전 데이터 정규화 및 검증
    normalized_movies = []
    for movie in movie_states:
        # 모든 필드 정규화
        normalized_movie = {
            'date': normalize_string(movie.get('date', '')),
            'title': normalize_string(movie.get('title', '')),
            'theater_info': normalize_string(movie.get('theater_info', '')),
            'times': [normalize_string(t) if isinstance(t, str) else t for t in movie.get('times', [])]
        }
        # 유효한 데이터만 저장
        if normalized_movie['date'] and normalized_movie['title'] and normalized_movie['times']:
            normalized_movies.append(normalized_movie)
    
    state = {
        'dates': date_states,
        'movies': normalized_movies,
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
        driver.execute_script("arguments[0].click();", filter_btn)
        time.sleep(0.3)

        imax_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((
                By.XPATH,
                "//section[contains(@class,'bot-modal-container')]//button[text()='아이맥스']"
            ))
        )
        driver.execute_script("arguments[0].click();", imax_btn)
        time.sleep(0.2)

        confirm_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((
                By.XPATH,
                "//section[contains(@class,'bot-modal-container')]//button[contains(text(),'확인')]"
            ))
        )
        driver.execute_script("arguments[0].click();", confirm_btn)
        time.sleep(0.3)

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


def verify_date_selected(driver, expected_date_key):
    """날짜가 실제로 선택되었는지 확인 (정규화된 날짜로 비교)"""
    normalized_expected = normalize_date_key(expected_date_key)
    
    try:
        active_btn = driver.find_element(
            By.CSS_SELECTOR,
            ".dayScroll_scrollItem__IZ35T.dayScroll_itemActive__fZ5Sq"
        )
        day_num = active_btn.find_element(By.CSS_SELECTOR, ".dayScroll_number__o8i9s").text.strip()
        day_txt = active_btn.find_element(By.CSS_SELECTOR, ".dayScroll_txt__GEtA0").text.strip()
        selected_date_raw = f"{day_txt} {day_num}"
        selected_date_normalized = normalize_date_key(selected_date_raw)
        
        # 정규화된 날짜로 비교 (오늘 처리 포함)
        if selected_date_normalized != normalized_expected:
            return False
            
        # 영화가 없어도 날짜 텍스트가 일치하면 선택된 것으로 간주
        return True
    except:
        return False


def verify_showtimes_loaded(driver, container_idx=None, check_all=False):
    """상영시간 데이터가 실제로 로드되었는지 확인
    
    Args:
        check_all: True면 모든 아이템 검증, False면 샘플링 (기본값: False)
    """
    try:
        containers = driver.find_elements(By.CSS_SELECTOR, "div.accordion_container__W7nEs")
        if not containers:
            return False
        
        if container_idx is not None:
            if container_idx >= len(containers):
                return False
            containers = [containers[container_idx]]
        
        for container in containers:
            try:
                time_items = container.find_elements(
                    By.CSS_SELECTOR, "ul.screenInfo_timeWrap__7GTHr li.screenInfo_timeItem__y8ZXg"
                )
                
                if not time_items:
                        continue
                
                if check_all:
                    # 모든 아이템 검증 (정확하지만 느림)
                    for item in time_items:
                        try:
                            start_elem = item.find_element(By.CSS_SELECTOR, ".screenInfo_start__6BZbu")
                            start_text = start_elem.text.strip()
                            end_elem = item.find_element(By.CSS_SELECTOR, ".screenInfo_end__qwvX0")
                            end_text = end_elem.text.strip()
                            
                            # 시작/종료 시간이 모두 유효한 형식인지 확인
                            if not (start_text and re.match(r'^\d{2}:\d{2}$', start_text)):
                                return False
                            if not (end_text and (re.match(r'^\d{2}:\d{2}$', end_text) or re.match(r'^-\s*\d{2}:\d{2}$', end_text))):
                                return False
                        except:
                            return False  # 하나라도 실패하면 아직 로딩 중
                    
                    return True
                else:
                    # 샘플링 검증 (빠름)
                    check_indices = [0]  # 항상 첫 번째 확인
                    if len(time_items) > 1:
                        check_indices.append(len(time_items) - 1)  # 마지막
                    if len(time_items) > 3:
                        check_indices.append(len(time_items) // 2)  # 중간
                    
                    valid_count = 0
                    for idx in check_indices:
                        try:
                            item = time_items[idx]
                            start_elem = item.find_element(By.CSS_SELECTOR, ".screenInfo_start__6BZbu")
                            start_text = start_elem.text.strip()
                            if start_text and re.match(r'^\d{2}:\d{2}$', start_text):
                                valid_count += 1
                        except:
                            return False  # 샘플 중 하나라도 실패하면 아직 로딩 중
                    
                    # 샘플 검증이 모두 성공하면 로드된 것으로 간주
                    if valid_count == len(check_indices):
                        return True
                except:
                    continue
                
        return False
    except:
        return False


def wait_for_date_fully_loaded(driver, expected_date_key, max_wait=2.0):
    """날짜 선택 완료까지 확인 (강화: 더 긴 대기 시간 및 재시도)"""
    normalized_expected = normalize_date_key(expected_date_key)
    
    # 즉시 확인
    if verify_date_selected(driver, expected_date_key):
        return True
    
    # 대기 및 재확인
    start_time = time.time()
    check_count = 0
    while time.time() - start_time < max_wait:
        time.sleep(0.1)
        check_count += 1
        
        if verify_date_selected(driver, expected_date_key):
            if check_count > 1:
                print(f"  ✓ 날짜 '{expected_date_key}' 선택 확인 완료 (재시도 {check_count}회)")
            return True
        
        # 0.5초마다 현재 선택된 날짜 출력 (디버깅)
        if check_count % 5 == 0:
            try:
                actual = get_selected_date(driver)
                actual_normalized = normalize_date_key(actual)
                if actual_normalized != normalized_expected:
                    print(f"  ⏳ 날짜 선택 대기 중... 현재: '{actual}' (정규화: {actual_normalized}), 기대: '{expected_date_key}' (정규화: {normalized_expected})")
            except:
                pass
    
    # 타임아웃 시 최종 확인
    final_result = verify_date_selected(driver, expected_date_key)
    if not final_result:
        try:
            actual = get_selected_date(driver)
            actual_normalized = normalize_date_key(actual)
            print(f"  ❌ 날짜 선택 실패: 기대 '{expected_date_key}' (정규화: {normalized_expected}), 실제 '{actual}' (정규화: {actual_normalized})")
                        except:
            print(f"  ❌ 날짜 선택 실패: 기대 '{expected_date_key}' (정규화: {normalized_expected})")
    return final_result


def wait_for_showtimes_fully_loaded(driver, container_idx=None, max_wait=1.5, strict=True):
    """상영시간 로딩 완료까지 확인 (strict 모드 최적화)"""
    if not strict:
        # strict 모드가 아니면 빠르게 확인
        if verify_showtimes_loaded(driver, container_idx, check_all=False):
            return True
        time.sleep(0.2)
        return verify_showtimes_loaded(driver, container_idx, check_all=False)
    
    # strict 모드: 모든 아이템 검증 (최적화 - 한 번만 정확하게 검증)
    # 즉시 첫 번째 확인
    if verify_showtimes_loaded(driver, container_idx, check_all=True):
        return True
    
    # 실패 시 짧은 대기 후 재확인
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if verify_showtimes_loaded(driver, container_idx, check_all=True):
            return True
        time.sleep(0.1)
    
    # 타임아웃 시 최종 검증
    return verify_showtimes_loaded(driver, container_idx, check_all=True)


def wait_for_dom_stable(driver, selector="div.accordion_container__W7nEs", stable_time=500, max_wait=3000):
    """MutationObserver를 사용하여 DOM이 안정화될 때까지 대기
    
    Args:
        driver: Selenium WebDriver
        selector: 관찰할 요소의 CSS 선택자
        stable_time: DOM 변경이 없어야 하는 시간 (ms)
        max_wait: 최대 대기 시간 (ms)
    
    Returns:
        bool: DOM이 안정화되었는지 여부
    """
    try:
        # 요소가 존재하는지 먼저 확인 (빠른 검사)
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if not elements:
            # 요소가 아예 없으면 짧은 대기 후 바로 리턴 (데이터 없음 상태)
            time.sleep(0.5)
            # 다시 확인
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if not elements:
                return True
        
        result = driver.execute_async_script(f"""
            var callback = arguments[arguments.length - 1];
            var selector = '{selector}';
            var stableTime = {stable_time};
            var maxWait = {max_wait};
            
            var targetNode = document.querySelector(selector) || document.body;
            var stableTimeout = null;
            var maxWaitTimeout = null;
            var observer = null;
            var isResolved = false;
            
            function resolve(result) {{
                if (isResolved) return;
                isResolved = true;
                if (stableTimeout) clearTimeout(stableTimeout);
                if (maxWaitTimeout) clearTimeout(maxWaitTimeout);
                if (observer) observer.disconnect();
                callback(result);
            }}
            
            observer = new MutationObserver(function(mutations) {{
                // 안정화 타이머 재시작
                if (stableTimeout) clearTimeout(stableTimeout);
                stableTimeout = setTimeout(function() {{
                    resolve(true);
                }}, stableTime);
            }});
            
            // DOM 변경 관찰 시작
            observer.observe(targetNode, {{
                childList: true,
                subtree: true,
                attributes: true,
                attributeOldValue: false,
                characterData: true,
                characterDataOldValue: false
            }});
            
            // 초기 안정화 타이머 설정 (DOM이 이미 안정화된 경우)
            stableTimeout = setTimeout(function() {{
                resolve(true);
            }}, stableTime);
            
            // 최대 대기 시간 설정
            maxWaitTimeout = setTimeout(function() {{
                resolve(false);
            }}, maxWait);
        """)
        return result
    except Exception as e:
        # MutationObserver 실패 시 fallback: 짧은 대기
        print(f"  ⚠️ DOM 안정화 검증 실패: {e}, fallback 대기")
        time.sleep(stable_time / 1000.0)
        return True


def scrape_imax_shows(driver, date_key=None):
    """현재 선택된 날짜의 IMAX 상영 정보 수집 (JavaScript로 직접 추출 - 빠르고 안정적)
    
    Args:
        driver: Selenium WebDriver
        date_key: 날짜 키 (None이면 현재 선택된 날짜 사용)
    """
    try:
        # 컨테이너 존재 확인
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.accordion_container__W7nEs"))
            )
                    except:
            return []
        
        if date_key is None:
            current_date = get_selected_date(driver)
        else:
            current_date = date_key
        
        # 1단계: 모든 아코디언을 JavaScript로 한 번에 펼치기 (컨테이너가 있을 때만)
        has_containers = driver.execute_script("""
            var containers = document.querySelectorAll('div.accordion_container__W7nEs');
            if (containers.length === 0) return false;
            
            for (var i = 0; i < containers.length; i++) {
                var btn = containers[i].querySelector('h2.accordion_accordionTitleArea__AmnDj button');
                if (btn && btn.getAttribute('aria-expanded') !== 'true') {
                    btn.click();
                }
            }
            return true;
        """)
        
        if not has_containers:
            # 컨테이너가 없으면(영화 데이터 없음) 대기 없이 빈 리스트 반환
            return []
            
        # 2단계: DOM 안정화 대기 (강화: 더 긴 대기 시간)
        wait_for_dom_stable(driver, selector="div.accordion_container__W7nEs", stable_time=800, max_wait=3000)
        time.sleep(0.3)  # 추가 안정화 대기
        
        # 3단계: JavaScript로 모든 데이터를 한 번에 추출 (Selenium 요소 찾기 완전 제거)
        movies_data_raw = driver.execute_script("""
            var containers = document.querySelectorAll('div.accordion_container__W7nEs');
            var results = [];
            
            for (var i = 0; i < containers.length; i++) {
                var container = containers[i];
                
                // 영화 제목 추출
                var titleElem = container.querySelector('h2 .screenInfo_title__Eso6_ .title2');
                if (!titleElem) continue;
                var movieTitle = titleElem.textContent.trim();
                
                // IMAX 정보 추출
                var theaterElem = container.querySelector('div.screenInfo_contentWrap__95SyT h3.screenInfo_title__Eso6_');
                if (!theaterElem) continue;
                var theaterFull = theaterElem.textContent.trim();
                
                if (theaterFull.toUpperCase().indexOf('IMAX') === -1) continue;
                
                var theaterInfo = theaterFull.replace('IMAX관', '').trim().replace(' / ', ', ');
                
                // 상영시간 추출
                var timeItems = container.querySelectorAll('ul.screenInfo_timeWrap__7GTHr li.screenInfo_timeItem__y8ZXg');
                var showTimes = [];
                
                for (var j = 0; j < timeItems.length; j++) {
                    var item = timeItems[j];
                    var startElem = item.querySelector('.screenInfo_start__6BZbu');
                    var endElem = item.querySelector('.screenInfo_end__qwvX0');
                    var statusElem = item.querySelector('.screenInfo_status__lT4zd');
                    
                    if (!startElem || !endElem) continue;
                    
                    var start = startElem.textContent.trim();
                    var end = endElem.textContent.trim();
                    var seatInfo = statusElem ? statusElem.textContent.trim() : '-';
                    
                    // 시간 형식 검증 (HH:MM)
                    if (!/^\\d{2}:\\d{2}$/.test(start)) continue;
                    
                    // 종료 시간 정리
                    if (end.startsWith('-')) {
                        end = end.substring(1).trim();
                    }
                    
                    // 종료 시간 형식 검증
                    if (!/^\\d{2}:\\d{2}$/.test(end)) continue;
                    
                    // 시간 범위 검증: 종료 시간이 시작 시간보다 이후인지 확인
                    var startParts = start.split(':');
                    var endParts = end.split(':');
                    if (startParts.length !== 2 || endParts.length !== 2) continue;
                    
                    var startHour = parseInt(startParts[0], 10);
                    var startMin = parseInt(startParts[1], 10);
                    var endHour = parseInt(endParts[0], 10);
                    var endMin = parseInt(endParts[1], 10);
                    
                    var startTotal = startHour * 60 + startMin;
                    var endTotal = endHour * 60 + endMin;
                    
                    // 다음날인 경우 고려
                    if (endTotal < startTotal) {
                        endTotal += 24 * 60;
                    }
                    
                    // 상영 시간이 너무 짧거나 길면 제외 (10분 미만 또는 5시간 초과)
                    var duration = endTotal - startTotal;
                    if (duration < 10 || duration > 300) continue;
                    
                    // 좌석 상태 확인: "예매 준비중", "준비중", "예매대기" 등이 있으면 제외
                    // 실제 좌석 수가 있는 경우만 포함 (숫자/숫자석 형식)
                    var isSeatOpen = false;
                    if (seatInfo && seatInfo !== '-') {
                        // 숫자가 포함되어 있고, "준비중", "대기" 같은 텍스트가 없으면 좌석 오픈
                        var hasNumber = /\\d/.test(seatInfo);
                        var hasNotReady = /준비|대기|오픈전|예매전/i.test(seatInfo);
                        isSeatOpen = hasNumber && !hasNotReady;
                    }
                    
                    // 좌석이 오픈된 경우만 추가
                    if (isSeatOpen) {
                        showTimes.push(start + ' ~ ' + end + ' | ' + seatInfo);
                    }
                }
                
                if (showTimes.length > 0) {
                    results.push({
                        title: movieTitle,
                        theater_info: theaterInfo,
                        times: showTimes
                    });
                }
            }
            
            return results;
        """)
        
        # 4단계: Python에서 데이터 정규화 및 반환 (날짜 검증 포함)
        # 실제 선택된 날짜 확인
        actual_selected_date = get_selected_date(driver)
        normalized_actual_date = normalize_date_key(actual_selected_date)
        normalized_expected_date = normalize_date_key(current_date)
        
        # 날짜 검증 (강화): 불일치하면 데이터 수집 중단
        if normalized_actual_date != normalized_expected_date:
            print(f"  ❌ 날짜 불일치: 요청한 날짜 '{current_date}' (정규화: {normalized_expected_date}) vs 실제 선택된 날짜 '{actual_selected_date}' (정규화: {normalized_actual_date})")
            print(f"  ⚠️ 날짜 불일치로 인해 데이터 수집 중단 (잘못된 날짜의 데이터 수집 방지)")
            return []  # 날짜가 불일치하면 빈 배열 반환 (데이터 수집 중단)
        
        movies_data = []
        seen_times = set()  # 중복 제거를 위한 set
        
        for movie in movies_data_raw:
            try:
                title = normalize_string(movie.get('title', ''))
                theater_info = normalize_string(movie.get('theater_info', ''))
                times_raw = movie.get('times', [])
                
                # 기본 검증: 제목과 상영관 정보가 있는지 확인
                if not title or not theater_info:
                    print(f"  ⚠️ 데이터 누락: 제목='{title}', 상영관='{theater_info}' - 건너뜀")
                        continue
                
                # 시간 문자열 검증 및 정규화
                show_times = []
                for time_str in times_raw:
                    # 검증 및 정규화
                    normalized_time = validate_and_normalize_showtime(time_str)
                    if not normalized_time:
                        continue  # 검증 실패 시 제외
                    
                    # 중복 제거 (같은 시간대가 여러 번 수집되는 것 방지)
                    time_key = extract_time_only(normalized_time)  # 시간만 추출하여 비교
                    if time_key in seen_times:
                        continue  # 중복 제거
                    seen_times.add(time_key)
                    
                    show_times.append(normalized_time)
                
                # 상영시간이 없으면 건너뛰기
                if not show_times:
                    print(f"  ⚠️ 유효한 상영시간 없음: {title} - 건너뜀")
                    continue
                
                # 최종 데이터 객체 생성
                movie_data = {
                    'date': normalize_date_key(current_date),  # 정규화된 날짜 사용
                    'title': title,
                    'theater_info': theater_info,
                        'times': show_times
                }
                
                # 최종 검증
                if not validate_movie_data(movie_data):
                    print(f"  ⚠️ 데이터 검증 실패: {title} - 건너뜀")
                    continue
                
                movies_data.append(movie_data)
                print(f"  수집: {title} - {len(show_times)}개 상영 (날짜: {normalize_date_key(current_date)})")
            except Exception as e:
                print(f"  ⚠️ 영화 데이터 처리 중 오류: {e}")
                continue

        return movies_data

    except Exception as e:
        print("IMAX 정보 파싱 실패:", e)
        return []


def scrape_imax_shows_with_verification(driver, date_key, max_retries=3, previous_state_for_date=None):
    """데이터 수집 후 일관성 검증 (여러 번 수집하여 일치하는 결과가 나올 때까지)
    
    Args:
        driver: Selenium WebDriver
        date_key: 날짜 키
        max_retries: 최대 재시도 횟수 (기본값: 3)
        previous_state_for_date: 해당 날짜의 이전 상태 데이터 (있으면 비교하여 최적화)
    
    Returns:
        list: 검증된 영화 데이터 리스트
    """
    results = []
    last_result_count = 0
    
    for attempt in range(max_retries):
        # 데이터 수집
        current_shows = scrape_imax_shows(driver, date_key)
        
        # 현재 수집 결과의 총 상영시간 개수 계산
        current_count = sum(len(movie.get('times', [])) for movie in current_shows)
        
        if not current_shows:
            # 데이터가 없으면 짧은 대기 후 재시도
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            return []
        
        # 첫 번째 수집이면 결과 저장
        if not results:
            results = current_shows
            last_result_count = current_count
            
            # [최적화] 이전 상태와 완전히 일치하면 추가 검증 없이 즉시 반환 (낙관적 검증)
            if previous_state_for_date and attempt == 0:
                if compare_shows_completely(current_shows, previous_state_for_date, date_key):
                    # print(f"  ⚡ 이전 상태와 일치 (빠른 통과)")
                    return current_shows
            
            if max_retries > 1:
                time.sleep(0.3)  # 다음 수집을 위한 짧은 대기
            continue
        
        # 이전 결과와 비교
        # 상영시간 개수가 같으면 상세 비교
        if current_count == last_result_count:
            # 영화별 상영시간 개수 비교
            current_dict = {}
            for movie in current_shows:
                key = create_movie_key(movie)
                current_dict[key] = len(movie.get('times', []))
            
            results_dict = {}
            for movie in results:
                key = create_movie_key(movie)
                results_dict[key] = len(movie.get('times', []))
            
            # 영화별 상영시간 개수가 모두 일치하면 검증 성공
            if current_dict == results_dict:
                # 마지막으로 상영시간 내용까지 비교
                current_times_set = set()
                for movie in current_shows:
                    for time_str in movie.get('times', []):
                        time_only = extract_time_only(time_str)
                        if time_only:
                            current_times_set.add(time_only)
                
                results_times_set = set()
                for movie in results:
                    for time_str in movie.get('times', []):
                        time_only = extract_time_only(time_str)
                        if time_only:
                            results_times_set.add(time_only)
                
                if current_times_set == results_times_set:
                    if attempt > 0:
                        print(f"  ✓ 데이터 일관성 검증 성공 (재시도 {attempt + 1}회)")
                    return current_shows  # 검증된 결과 반환
        else:
            # 상영시간 개수가 다르면 재시도
            if attempt < max_retries - 1:
                print(f"  ⚠️ 데이터 불일치 감지: 이전 {last_result_count}개, 현재 {current_count}개 - 재수집 중...")
                results = current_shows
                last_result_count = current_count
                time.sleep(0.5)  # 재시도를 위한 대기
                continue
        
        # 일치하지 않으면 재시도
        if attempt < max_retries - 1:
            print(f"  ⚠️ 데이터 불일치 감지 (재시도 {attempt + 1}/{max_retries})")
            results = current_shows
            last_result_count = current_count
            time.sleep(0.5)  # 재시도를 위한 대기
    
    # 최대 재시도 횟수 도달 시 마지막 결과 반환
    if max_retries > 1:
        print(f"  ⚠️ 최대 재시도 횟수 도달, 마지막 수집 결과 사용 (총 {last_result_count}개 상영시간)")
    return results


def normalize_string(s):
    """문자열 정규화 (공백, 특수문자 통일)"""
    if not s:
        return ""
    # 앞뒤 공백 제거 및 여러 공백을 하나로
    return " ".join(str(s).strip().split())

def normalize_date_key(date_key):
    """날짜 키 정규화: '오늘'과 실제 요일을 동일하게 처리 (요일 + 날짜 번호 형식으로 통일)"""
    if not date_key:
        return ""
    
    normalized = normalize_string(date_key)
    
    # 날짜 번호 및 요일 추출
    parts = normalized.split()
    date_num = None
    day_txt = None
    
    # 요일 추출 (월, 화, 수, 목, 금, 토, 일)
    day_names = ['월', '화', '수', '목', '금', '토', '일']
    for part in parts:
        if part in day_names:
            day_txt = part
        elif part.isdigit():
            date_num = part
    
    # "오늘"이 포함된 경우: 날짜 번호만 반환 (요일 정보 제거하여 다른 날짜와 매칭)
    # 하지만 이는 위험할 수 있으므로, 요일 정보도 함께 반환하도록 개선
    if "오늘" in normalized or "today" in normalized.lower():
        if date_num:
            # 날짜 번호만 반환 (기존 로직 유지하되, 요일 정보가 있으면 함께 반환)
            if day_txt:
                return f"{day_txt} {date_num}"  # "오늘 16" -> "화 16" (실제 요일 포함)
            return date_num  # 날짜 번호만 반환
        return normalized
    
    # 일반 날짜는 "요일 날짜번호" 형식으로 통일 (예: "화 16")
    if day_txt and date_num:
        return f"{day_txt} {date_num}"
    elif date_num:
        # 날짜 번호만 있는 경우
        return date_num
    else:
        # 그 외는 원본 반환
        return normalized

def is_seat_open(seat_info):
    """좌석이 실제로 오픈되었는지 확인 (예매 준비중이 아닌지)"""
    if not seat_info or seat_info == '-':
        return False
    
    seat_info_lower = seat_info.lower()
    
    # "준비중", "대기", "오픈전", "예매전" 등의 키워드가 있으면 좌석 미오픈
    not_ready_keywords = ['준비', '대기', '오픈전', '예매전', '예매 준비']
    if any(keyword in seat_info_lower for keyword in not_ready_keywords):
        return False
    
    # 숫자가 포함되어 있으면 좌석 오픈 (예: "361/387석", "잔여석 42")
    if re.search(r'\d', seat_info):
        return True
    
    return False

def validate_time_format(time_str):
    """시간 형식 검증 (HH:MM)"""
    if not time_str:
        return False
    return bool(re.match(r'^\d{2}:\d{2}$', time_str.strip()))

def validate_time_range(start_time, end_time):
    """시간 범위 검증: 종료 시간이 시작 시간보다 이후인지 확인"""
    try:
        start_parts = start_time.split(':')
        end_parts = end_time.split(':')
        
        if len(start_parts) != 2 or len(end_parts) != 2:
            return False
        
        start_hour = int(start_parts[0])
        start_min = int(start_parts[1])
        end_hour = int(end_parts[0])
        end_min = int(end_parts[1])
        
        # 시간 범위 검증 (24시간 넘어가는 경우도 고려)
        start_total = start_hour * 60 + start_min
        end_total = end_hour * 60 + end_min
        
        # 종료 시간이 시작 시간보다 이후여야 함 (다음날인 경우도 고려)
        if end_total < start_total:
            # 다음날인 경우 (예: 23:00 ~ 01:00)
            end_total += 24 * 60
        
        # 상영 시간이 너무 짧거나 길면 이상 (10분 미만 또는 5시간 초과)
        duration = end_total - start_total
        if duration < 10 or duration > 300:
            return False
        
        return True
    except:
        return False

def validate_movie_data(movie_data):
    """영화 데이터 검증"""
    # 필수 필드 확인
    if not movie_data:
        return False
    
    title = movie_data.get('title', '').strip()
    theater_info = movie_data.get('theater_info', '').strip()
    times = movie_data.get('times', [])
    date = movie_data.get('date', '').strip()
    
    # 제목이 비어있으면 무효
    if not title or len(title) < 1:
        return False
    
    # 상영관 정보가 비어있으면 무효
    if not theater_info:
        return False
    
    # 날짜가 비어있으면 무효
    if not date:
        return False
    
    # 상영시간이 없으면 무효
    if not times or len(times) == 0:
        return False
    
    return True

def validate_and_normalize_showtime(time_str):
    """상영시간 문자열 검증 및 정규화"""
    if not time_str:
        return None
    
    # 형식: "HH:MM ~ HH:MM | 좌석정보"
    parts = time_str.split(' | ')
    if len(parts) < 2:
        return None
    
    time_part = parts[0].strip()
    seat_part = parts[1].strip() if len(parts) > 1 else '-'
    
    # 좌석 상태 확인
    if not is_seat_open(seat_part):
        return None
    
    # 시간 부분 파싱
    if ' ~ ' not in time_part:
        return None
    
    start, end = time_part.split(' ~ ', 1)
    start = normalize_string(start.strip())
    end = normalize_string(end.strip())
    
    # "-" 제거
    if end.startswith('-'):
        end = end[1:].strip()
    end = normalize_string(end)
    
    # 시간 형식 검증
    if not validate_time_format(start) or not validate_time_format(end):
        return None
    
    # 시간 범위 검증
    if not validate_time_range(start, end):
        return None
    
    # 정규화된 형식으로 반환
    seat_part = normalize_string(seat_part) if seat_part != '-' else '-'
    return f"{start} ~ {end} | {seat_part}"

def extract_time_only(time_str):
    """시간대 문자열에서 시간 부분만 추출 (좌석수 제외, 정규화)"""
    if not time_str:
        return ""
    
    # 정규화 후 추출
    normalized = normalize_string(time_str)
    
    # 좌석 정보 제거
    if " | " in normalized:
        time_part = normalized.split(" | ")[0]
    elif "|" in normalized:
        time_part = normalized.split("|")[0]
    else:
        time_part = normalized
    
    # " ~ " 사이의 공백도 정규화 ("14:40 ~ 16:38" 형식 통일)
    time_part = normalize_string(time_part)
    
    # " ~ "를 기준으로 시작/종료 시간 정규화
    if " ~ " in time_part:
        parts = time_part.split(" ~ ")
        if len(parts) == 2:
            start_time = normalize_string(parts[0])
            end_time = normalize_string(parts[1])
            # 종료 시간에서 앞의 "-" 제거 ("- 16:38" -> "16:38")
            if end_time.startswith("-"):
                end_time = end_time[1:].strip()
            end_time = normalize_string(end_time)
            return f"{start_time} ~ {end_time}"
    
    return time_part

def create_movie_key(movie):
    """영화 키 생성 (날짜 정규화 포함)"""
    date = normalize_date_key(movie.get('date', ''))
    title = normalize_string(movie.get('title', ''))
    theater_info = normalize_string(movie.get('theater_info', ''))
    return f"{date}|{title}|{theater_info}"

def compare_shows_completely(current_shows, previous_movies, target_date_key):
    """현재 수집한 데이터와 이전 상태를 완전히 비교하여 일치 여부 확인
    
    Returns:
        bool: 완전히 일치하면 True, 다르면 False
    """
    normalized_target_date = normalize_date_key(target_date_key)
    
    # 이전 상태에서 해당 날짜의 영화 정보만 가져오기
    prev_movies_dict = {}
    for movie in previous_movies:
        movie_date = normalize_date_key(movie.get('date', ''))
        if movie_date != normalized_target_date:
            continue
        
        key = create_movie_key(movie)
        prev_times_set = set()
        for time_str in movie.get('times', []):
            time_only = extract_time_only(time_str)
            if time_only:
                prev_times_set.add(time_only)
        if prev_times_set:
            prev_movies_dict[key] = prev_times_set
    
    # 현재 상태와 비교
    current_movies_dict = {}
    for movie in current_shows:
        movie_date = normalize_date_key(movie.get('date', ''))
        if movie_date != normalized_target_date:
            continue
        
        key = create_movie_key(movie)
        current_times_set = set()
        for time_str in movie.get('times', []):
            time_only = extract_time_only(time_str)
            if time_only:
                current_times_set.add(time_only)
        if current_times_set:
            current_movies_dict[key] = current_times_set
    
    # 영화 개수 확인
    if len(prev_movies_dict) != len(current_movies_dict):
        return False
    
    # 모든 영화의 상영시간이 일치하는지 확인
    for key in prev_movies_dict:
        if key not in current_movies_dict:
            return False
        if prev_movies_dict[key] != current_movies_dict[key]:
            return False
    
    # 새로운 영화가 있는지 확인
    for key in current_movies_dict:
        if key not in prev_movies_dict:
            return False
    
    return True

def find_new_showtimes_for_date(current_shows, previous_movies, target_date_key):
    """특정 날짜의 새로운 상영시간 찾기"""
    new_showtimes = []
    prev_movie_times = {}
    # 날짜 키 정규화 (오늘 처리 포함)
    normalized_target_date = normalize_date_key(target_date_key)
    
    # 이전 상태에서 해당 날짜의 영화 정보만 가져오기
    for movie in previous_movies:
        movie_date = normalize_date_key(movie.get('date', ''))
        # 날짜 번호만 비교 (오늘 처리)
        if movie_date != normalized_target_date:
            continue
        
        key = create_movie_key(movie)
        prev_times_set = set()
        for time_str in movie.get('times', []):
            time_only = extract_time_only(time_str)
            if time_only:  # 빈 문자열 제외
                prev_times_set.add(time_only)
        if prev_times_set:
            prev_movie_times[key] = prev_times_set
    
    # 현재 상태와 비교
    for movie in current_shows:
        movie_date = normalize_date_key(movie.get('date', ''))
        if movie_date != normalized_target_date:
            continue
        
        key = create_movie_key(movie)
        
        current_times_set = set()
        current_times_full = {}
        for time_str in movie.get('times', []):
            # 좌석 정보 추출
            seat_info = '-'
            if " | " in time_str:
                seat_info = time_str.split(" | ", 1)[1] if len(time_str.split(" | ")) > 1 else '-'
            elif "|" in time_str:
                seat_info = time_str.split("|", 1)[1] if len(time_str.split("|")) > 1 else '-'
            
            # 좌석이 오픈된 경우만 포함
            if not is_seat_open(seat_info):
                continue
            
            time_only = extract_time_only(time_str)
            if time_only:
                current_times_set.add(time_only)
                current_times_full[time_only] = time_str
        
        if key in prev_movie_times:
            prev_times = prev_movie_times[key]
            new_times_only = current_times_set - prev_times
            
            # 새로운 시간이 있으면 바로 알림
            if new_times_only:
                print(f"  ✅ 새로운 상영시간 발견: {movie.get('title')} - {len(new_times_only)}개 추가")
                print(f"     추가된 시간: {sorted(new_times_only)}")
                new_times_full = [current_times_full[t] for t in new_times_only]
                new_showtimes.append({
                    'date': movie_date,
                    'title': normalize_string(movie.get('title', '')),
                    'theater_info': normalize_string(movie.get('theater_info', '')),
                    'new_times': new_times_full
                })
        else:
            # 새로운 영화인 경우 - 이전 상태가 있으면 알림 (첫 배포가 아님)
            # previous_state가 None이면 첫 배포이므로 알림 안 보냄 (호출부에서 처리)
            if current_times_set:
                print(f"  ✅ 새로운 영화 발견: {movie.get('title')} - {len(current_times_set)}개 상영시간")
                print(f"     추가된 시간: {sorted(current_times_set)}")
                new_times_full = [current_times_full[t] for t in current_times_set]
                new_showtimes.append({
                    'date': movie_date,
                    'title': normalize_string(movie.get('title', '')),
                    'theater_info': normalize_string(movie.get('theater_info', '')),
                    'new_times': new_times_full
                })
    
    return new_showtimes

def extract_start_time(time_str):
    """상영시간 문자열에서 시작 시간 추출 (정렬용)"""
    try:
        # 형식: "14:40 ~ 16:38 | 387/387석" 또는 "14:40 ~ 16:38"
        parts = time_str.split(' ~ ')
        if parts:
            time_part = parts[0].strip()
            # 시간을 분으로 변환 (예: "14:40" -> 14*60 + 40 = 880)
            if ':' in time_part:
                hour, minute = map(int, time_part.split(':'))
                return hour * 60 + minute
    except:
        pass
    return 0  # 파싱 실패 시 맨 앞에

def send_notification_for_date(date_key, new_showtimes):
    """새로 생긴 상영시간만 알림 전송 (날짜 전체가 아닌 새로 추가된 시간만)"""
    if not new_showtimes:
        return
    
    msg_parts = []
    msg_parts.append("⏰ 새로운 상영시간 추가!")
    msg_parts.append(f"📅 {date_key}\n")
    
    # 영화별로 정렬 (제목 순)
    sorted_items = sorted(new_showtimes, key=lambda x: x['title'])
    
    for item in sorted_items:
        if item['theater_info']:
            msg_parts.append(f"🎬 {item['title']} ({item['theater_info']})")
        else:
            msg_parts.append(f"🎬 {item['title']}")
        
        # 새로 추가된 상영시간만 표시 (시작 시간 순서로 정렬)
        sorted_times = sorted(item['new_times'], key=lambda t: extract_start_time(t))
        for time_info in sorted_times:
            msg_parts.append(f"  ✨ {time_info}")
        msg_parts.append("")
    
    msg = "\n".join(msg_parts).strip()
    send_telegram_message(msg)
    print(f"⚡ 알림 전송: {date_key} (새 상영시간 {sum(len(item['new_times']) for item in new_showtimes)}개)")

def scrape_all_dates_from_html(driver, enabled_dates, previous_state=None):
    """각 날짜를 빠르게 클릭하면서 모든 날짜의 데이터 수집 및 즉시 알림 (스마트 대기 적용)"""
    try:
        print(f"활성화된 날짜 {len(enabled_dates)}개를 빠르게 클릭하며 수집 중...")
        all_movies_data = []
        
        # 이전 상태에서 날짜별로 영화 정보 분리 (정규화된 날짜 사용, 오늘 처리 포함)
        prev_movies_by_date = {}
        if previous_state and 'movies' in previous_state:
            for movie in previous_state['movies']:
                date = normalize_date_key(movie.get('date', ''))
                if date and date not in prev_movies_by_date:
                    prev_movies_by_date[date] = []
                if date:
                    prev_movies_by_date[date].append(movie)
        
        for idx, date_info in enumerate(enabled_dates):
            try:
                date_key = date_info['date']
                normalized_date_key = normalize_date_key(date_key)
                
                # target_button 변수 초기화
                target_button = None
                
                # 빠른 체크 제거: 데이터 수집 불안정으로 인한 잘못된 스킵 방지
                # 모든 날짜를 정확하게 수집하여 비교
                
                print(f"[{idx+1}/{len(enabled_dates)}] 날짜 '{date_key}' 처리 중...")
                
                # 빠른 체크에서 이미 클릭했으면 target_button이 설정되어 있음
                # 빠른 체크를 하지 않았거나 실패한 경우에만 버튼 찾기
                if not target_button:
                    # 저장된 버튼 객체를 우선 사용 (이미 get_all_date_info에서 찾았음)
                    if date_info.get('button'):
                        try:
                            btn = date_info['button']
                            btn.is_displayed()  # stale element 체크
                            target_button = btn
                        except:
                            pass
                        
                    # 저장된 버튼이 유효하지 않으면 빠르게 다시 찾기 (fallback)
                    if not target_button:
                        # XPath로 빠르게 찾기 시도 (텍스트 기반)
                        try:
                            parts = date_key.split()
                                    if len(parts) >= 2:
                                day_txt, day_num = parts[0], parts[1]
                                # XPath로 직접 찾기
                                target_button = driver.find_element(
                                    By.XPATH,
                                    f"//button[contains(@class, 'dayScroll_scrollItem__IZ35T') and .//span[@class='dayScroll_txt__GEtA0' and text()='{day_txt}'] and .//span[@class='dayScroll_number__o8i9s' and text()='{day_num}'] and not(contains(@class, 'dayScroll_disabled__t8HIQ')) and not(@disabled)]"
                                )
                            except:
                            # XPath 실패 시 기존 방식으로 폴백 (디버깅용 정보 포함)
                            date_buttons = driver.find_elements(By.CSS_SELECTOR, ".dayScroll_container__e9cLv button.dayScroll_scrollItem__IZ35T")
                            found_dates = []
                            
                            for btn in date_buttons:
                                try:
                                    day_txt_elem = btn.find_element(By.CSS_SELECTOR, ".dayScroll_txt__GEtA0")
                                    day_num_elem = btn.find_element(By.CSS_SELECTOR, ".dayScroll_number__o8i9s")
                                    day_txt = day_txt_elem.text.strip()
                                    day_num = day_num_elem.text.strip()
                        
                        if day_txt and day_num:
                            btn_date_key = f"{day_txt} {day_num}"
                                        found_dates.append(btn_date_key)
                            
                            if btn_date_key == date_key:
                                class_attr = btn.get_attribute("class") or ""
                                            is_disabled = "dayScroll_disabled__t8HIQ" in class_attr or btn.get_attribute("disabled") is not None
                                            if not is_disabled:
                                    target_button = btn
                                    break
                    except:
                        continue
                
                if not target_button:
                    print(f"  ⚠️ 날짜 '{date_key}' 버튼을 찾을 수 없음")
                    continue
                
                # 빠른 체크에서 이미 클릭했는지 확인
                # (빠른 체크에서 클릭했다면 이미 날짜가 선택되어 있음)
                already_clicked = False
                try:
                    active_btn = driver.find_element(
                        By.CSS_SELECTOR,
                        ".dayScroll_scrollItem__IZ35T.dayScroll_itemActive__fZ5Sq"
                    )
                    day_num = active_btn.find_element(By.CSS_SELECTOR, ".dayScroll_number__o8i9s").text.strip()
                    day_txt = active_btn.find_element(By.CSS_SELECTOR, ".dayScroll_txt__GEtA0").text.strip()
                    current_date = normalize_string(f"{day_txt} {day_num}")
                    normalized_current = normalize_date_key(current_date)
                    if normalized_current == normalized_date_key:
                        already_clicked = True
                        except:
                            pass
                    
                # 빠른 체크에서 클릭하지 않았으면 클릭
                if not already_clicked:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_button)
                    time.sleep(0.1)  # 스크롤 후 잠시 대기
                driver.execute_script("arguments[0].click();", target_button)
                    time.sleep(0.2)  # 클릭 후 DOM 업데이트 대기
                
                # 날짜 선택 완료 확인 (강화: 더 긴 대기 시간)
                if not wait_for_date_fully_loaded(driver, date_key, max_wait=2.0):
                    # 날짜 선택 실패 시 재시도 (최대 2회)
                    print(f"  ⚠️ 날짜 '{date_key}' 선택 실패, 재시도 중...")
                    for retry in range(2):
                        try:
                            # 버튼 다시 찾기
                            target_button_retry = None
                            date_buttons_retry = driver.find_elements(By.CSS_SELECTOR, ".dayScroll_container__e9cLv button.dayScroll_scrollItem__IZ35T")
                            for btn in date_buttons_retry:
                                try:
                                    day_txt_elem = btn.find_element(By.CSS_SELECTOR, ".dayScroll_txt__GEtA0")
                                    day_num_elem = btn.find_element(By.CSS_SELECTOR, ".dayScroll_number__o8i9s")
                                    day_txt = day_txt_elem.text.strip()
                                    day_num = day_num_elem.text.strip()
                                    if day_txt and day_num:
                                        btn_date_key = f"{day_txt} {day_num}"
                                        if normalize_date_key(btn_date_key) == normalized_date_key:
                                            class_attr = btn.get_attribute("class") or ""
                                            is_disabled = "dayScroll_disabled__t8HIQ" in class_attr or btn.get_attribute("disabled") is not None
                                            if not is_disabled:
                                                target_button_retry = btn
                                                break
                                except:
                                    continue
                            
                            if target_button_retry:
                                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_button_retry)
                                time.sleep(0.1)
                                driver.execute_script("arguments[0].click();", target_button_retry)
                                time.sleep(0.3)
                                
                                if wait_for_date_fully_loaded(driver, date_key, max_wait=2.0):
                                    print(f"  ✓ 날짜 '{date_key}' 재시도 성공")
                                    break
                        except Exception as e:
                            print(f"  ⚠️ 재시도 {retry + 1} 실패: {e}")
                    
                    # 재시도 후에도 실패하면 건너뛰기
                    if not verify_date_selected(driver, date_key):
                        print(f"  ❌ 날짜 '{date_key}' 선택 실패로 인해 건너뜀")
                        continue
                
                # 데이터 수집 전 최종 날짜 확인
                final_check_date = get_selected_date(driver)
                final_check_normalized = normalize_date_key(final_check_date)
                if final_check_normalized != normalized_date_key:
                    print(f"  ❌ 최종 날짜 확인 실패: 기대 '{date_key}' (정규화: {normalized_date_key}), 실제 '{final_check_date}' (정규화: {final_check_normalized}) - 건너뜀")
                    continue
                
                # 이전 상태에서 해당 날짜의 영화 정보만 추출
                prev_movies_for_date = []
                if previous_state:
                    prev_movies_for_date = prev_movies_by_date.get(normalized_date_key, [])
                
                # MutationObserver로 DOM 안정화 후 데이터 수집 (일관성 검증 포함, 이전 상태와 비교하여 최적화)
                shows = scrape_imax_shows_with_verification(driver, date_key, previous_state_for_date=prev_movies_for_date)
                
                if shows:
                    # 날짜 키 정규화 (오늘 처리 포함)
                    # normalized_date_key는 이미 위에서 계산됨
                    
                    # 수집한 데이터의 날짜 검증 및 정규화
                    for show in shows:
                        collected_date = show.get('date', '')
                        normalized_collected = normalize_date_key(collected_date)
                        # 날짜가 일치하는지 확인
                        if normalized_collected != normalized_date_key:
                            print(f"  ⚠️ 날짜 불일치 수정: '{collected_date}' -> '{normalized_date_key}'")
                        show['date'] = normalized_date_key
                    
                    # 최적화: 이전 상태와 완전히 일치하면 이전 상태 재사용 (속도 향상)
                    if previous_state:
                        prev_movies = prev_movies_by_date.get(normalized_date_key, [])
                        
                        # 완전히 일치하는지 빠르게 확인
                        if prev_movies and compare_shows_completely(shows, prev_movies, date_key):
                            print(f"  ✓ 날짜 '{date_key}' 변화 없음 (이전 상태 재사용)")
                            # 이전 상태를 그대로 사용 (이미 수집한 데이터는 버림)
                            for prev_movie in prev_movies:
                                all_movies_data.append(prev_movie.copy())
                            continue  # 다음 날짜로 바로 넘어감
                        
                        # 일치하지 않으면 상세 비교 및 알림
                        new_showtimes = find_new_showtimes_for_date(shows, prev_movies, date_key)
                        
                        if new_showtimes:
                            print(f"  🔔 알림 대상 발견: {len(new_showtimes)}개 영화에 새로운 상영시간")
                            send_notification_for_date(date_key, new_showtimes)
                            # 새로운 상영시간이 있으면 수집한 데이터 사용
                            all_movies_data.extend(shows)
                        else:
                            print(f"  ✓ 날짜 '{date_key}' 체크 완료: {len(shows)}개 영화, 총 {sum(len(s.get('times', [])) for s in shows)}개 상영시간 (변화 없음)")
                            # 변화 없지만 완전 일치하지 않았으므로 수집한 데이터 사용
                            all_movies_data.extend(shows)
                    else:
                        # 첫 실행이면 그냥 저장
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
                                swiper.slideTo(arguments[1], 0);  // 애니메이션 없이 즉시 이동
                            }
                        """, swiper_container, slide_idx)
                        time.sleep(0.02)  # 슬라이드 이동 대기 시간 최소화
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
                            swiper.slideTo(0, 0);  // 애니메이션 없이 즉시 이동
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
                # 버튼이 보이도록 스크롤 (텍스트 로드를 위해 필요)
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'auto'});", btn)
                    time.sleep(0.05)  # 최소 대기 시간
                except:
                    pass
                
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
    global _global_driver
    
    # 전역 드라이버가 없거나 유효하지 않으면 초기화 (재배포 시)
    if _global_driver is None:
        # 재배포 시 기존 크롬 프로세스 종료
        kill_existing_chrome()
        
        try:
            _global_driver = init_driver()
            _global_driver.get("https://cgv.co.kr/cnm/movieBook/cinema")
            
            # 스마트 대기: 페이지 로딩 완료
            try:
                WebDriverWait(_global_driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//li/button[contains(., '서울')]"))
                )
            except:
                time.sleep(1)  # fallback

            select_region_seoul(_global_driver)
            # 스마트 대기: 지역 선택 후 로딩
            try:
                WebDriverWait(_global_driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//button[p[text()='영등포타임스퀘어']]"))
                )
            except:
                time.sleep(0.5)  # fallback

            select_yeongdeungpo(_global_driver)
            # 스마트 대기: 극장 선택 후 로딩
            try:
                WebDriverWait(_global_driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'cnms01510_movieTitleWrap__69alk')]//button"))
                )
            except:
                time.sleep(1)  # fallback

            click_imax_filter(_global_driver)
            # 스마트 대기: 필터 적용 후 로딩
            try:
                WebDriverWait(_global_driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".dayScroll_container__e9cLv"))
                )
            except:
                time.sleep(0.5)  # fallback
            
            print("크롬 브라우저 초기화 완료 (유지 모드)")
        except Exception as e:
            print(f"드라이버 초기화 실패: {e}")
            # 실패 시 재시도
            try:
                if _global_driver:
                    _global_driver.quit()
            except:
                pass
            _global_driver = None
            return
    else:
        # 기존 드라이버가 있으면 새로고침만 수행
        try:
            # 드라이버가 유효한지 확인
            _global_driver.current_url
            print("기존 브라우저 사용 (새로고침)")
            _global_driver.refresh()
            
            # 스마트 대기: 페이지 로딩 완료
            try:
                WebDriverWait(_global_driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//li/button[contains(., '서울')]"))
                )
            except:
                time.sleep(1)  # fallback

            select_region_seoul(_global_driver)
            # 스마트 대기: 지역 선택 후 로딩
            try:
                WebDriverWait(_global_driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//button[p[text()='영등포타임스퀘어']]"))
                )
            except:
                time.sleep(0.5)  # fallback

            select_yeongdeungpo(_global_driver)
            # 스마트 대기: 극장 선택 후 로딩
            try:
                WebDriverWait(_global_driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class,'cnms01510_movieTitleWrap__69alk')]//button"))
                )
            except:
                time.sleep(1)  # fallback

            click_imax_filter(_global_driver)
            # 스마트 대기: 필터 적용 후 로딩
            try:
                WebDriverWait(_global_driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".dayScroll_container__e9cLv"))
                )
            except:
                time.sleep(0.5)  # fallback
        except Exception as e:
            # 드라이버가 유효하지 않으면 재초기화
            print(f"기존 드라이버 무효화 감지: {e}, 재초기화 중...")
            try:
                _global_driver.quit()
            except:
                pass
            _global_driver = None
            # 재초기화 시 기존 크롬 프로세스 종료
            kill_existing_chrome()
            # 재귀 호출로 재초기화
            return main()
    
    driver = _global_driver

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
        all_movies_current = scrape_all_dates_from_html(driver, enabled_dates, None)
        
        save_current_state(current_date_states, all_movies_current)
        print("초기 상태 저장 완료")
        # 첫 실행 시에도 드라이버 유지
        return
    
    # 기존 상태가 있는 경우: HTML에서 모든 데이터 수집 및 즉시 알림
    print(f"활성화된 날짜 {len(enabled_dates)}개 체크 중...")
    all_movies_current = scrape_all_dates_from_html(driver, enabled_dates, previous_state)
    
    print("변화 감지 완료 (즉시 알림은 이미 전송됨)")
    
    save_current_state(current_date_states, all_movies_current)
    print("상태 저장 완료")

    # 드라이버 유지 (quit 제거)


if __name__ == "__main__":
    main()