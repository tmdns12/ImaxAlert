# CGV 영등포 IMAX 좌석 알림봇

CGV 영등포 타임스퀘어 IMAX관의 새로운 상영 일정이나 좌석이 열리면 텔레그램으로 알림을 보내주는 봇입니다.

## 기능

- 📅 **새로운 날짜 예매 오픈 알림** - 비활성화된 날짜가 활성화되면 즉시 알림
- ⏰ **새로운 상영시간 추가 알림** - 기존 날짜에 새 상영시간이 추가되면 알림
- 🎬 모든 IMAX 상영 정보 자동 수집 및 추적

## Render.com 배포 방법 (추천)

### 1. GitHub 저장소 생성 및 푸시

```bash
cd d:\miniproject
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/본인아이디/저장소이름.git
git push -u origin main
```

### 2. Render.com 가입 및 설정

1. https://render.com 에서 가입 (무료)
2. **New +** → **Cron Job** 클릭
3. **Connect Repository** → GitHub 연동 → 저장소 선택

### 3. Cron Job 설정

- **Name**: `cgv-imax-alert`
- **Region**: Singapore (또는 가까운 지역)
- **Branch**: `main`
- **Runtime**: **Docker**
- **Schedule**: `* * * * *` (1분마다)

### 4. 환경 변수 추가

"Environment" 섹션에서:

- `TELEGRAM_TOKEN`: 텔레그램 봇 토큰
- `TELEGRAM_CHAT_ID`: 텔레그램 Chat ID

### 5. Deploy

- **Create Cron Job** 클릭
- Logs 탭에서 실행 로그 확인

## 로컬 실행

```bash
# 패키지 설치
pip install -r requirements.txt

# 실행
python imaxAlert.py
```

## 작동 원리

1. Selenium으로 CGV 예매 페이지 접속
2. 영등포 타임스퀘어 선택 → IMAX 필터 적용
3. 모든 예매 가능 날짜 순회하며 상영 정보 수집
4. 이전 상태(`imax_state.json`)와 비교:
   - 새로 활성화된 날짜 → 해당 날짜의 모든 상영 정보 알림
   - 기존 날짜의 새 상영시간 → 새 시간만 알림
5. Render가 1분마다 자동 실행

## 알림 예시

**새 날짜 오픈:**
```
🔔 새로운 예매 날짜가 열렸습니다!

📅 월 08

주토피아 2 (IMAX LASER 2D, 자막)
  14:40 ~ 16:38 | 387/387석
  17:00 ~ 18:58 | 387/387석
```

**새 상영시간 추가:**
```
⏰새로운 상영시간이 추가되었습니다!

📅 오늘 03
주토피아 2 (IMAX LASER 2D, 자막)
  24:10 ~ 26:08 | 387/387석
```

## 주의사항

- 텔레그램 토큰과 Chat ID는 환경 변수로 관리하세요
- 공개 저장소에는 절대 올리지 마세요
- Render 무료 플랜: 750시간/월 (충분함)




