# CGV 영등포 IMAX 좌석 알림봇

CGV 영등포 타임스퀘어 IMAX관의 새로운 상영 일정이나 좌석이 열리면 텔레그램으로 알림을 보내주는 봇입니다.

## 기능

- 📅 새로운 날짜 예매 오픈 알림
- 🎬 새로운 IMAX 영화 추가 알림
- ⏰ 기존 영화의 새 상영시간 추가 알림

## GitHub Actions 설정 방법

### 1. GitHub 저장소 생성

1. GitHub에 새 저장소 생성
2. 이 폴더의 모든 파일을 저장소에 업로드

### 2. Secrets 설정

GitHub 저장소 → Settings → Secrets and variables → Actions → New repository secret

다음 2개의 Secret 추가:

- `TELEGRAM_TOKEN`: `8445210236:AAEmUtaJ4vGlbBlUKaS8wBVC0XCZyJMlUrs`
- `TELEGRAM_CHAT_ID`: `7980674556`

### 3. Actions 권한 설정

Settings → Actions → General → Workflow permissions:
- "Read and write permissions" 선택
- "Allow GitHub Actions to create and approve pull requests" 체크

### 4. 자동 실행 확인

- Actions 탭에서 "CGV IMAX Alert" 워크플로우 확인
- 5분마다 자동 실행됩니다
- 수동 실행: Actions → CGV IMAX Alert → Run workflow

## 로컬 실행

```bash
# 패키지 설치
pip install -r requirements.txt

# 실행
python imaxAlert.py
```

## 작동 원리

1. Selenium으로 CGV 예매 페이지 접속
2. 영등포 타임스퀘어 IMAX 필터 적용
3. 현재 상영 정보를 `imax_state.json`에 저장
4. 이전 상태와 비교해 새로운 내용이 있으면 텔레그램 알림
5. GitHub Actions가 5분마다 자동 실행

## 주의사항

- 텔레그램 토큰과 Chat ID는 절대 공개 저장소에 직접 올리지 마세요
- GitHub Secrets를 사용하세요


