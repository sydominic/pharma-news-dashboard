# 제약뉴스 RSS 대시보드 온라인 배포본 v1.12-online

## 1. 배포 대상

이 패키지는 Streamlit Community Cloud 배포용입니다.

## 2. GitHub 업로드 구조

GitHub repository 루트에 아래 파일/폴더가 바로 보이도록 업로드합니다.

```text
app.py
requirements.txt
runtime.txt
.streamlit/config.toml
data/rss_sources.json
modules/
README_ONLINE_DEPLOY.md
```

`data/news_raw.csv`, `data/news_clean.csv`는 실행 중 생성되는 파일입니다. GitHub에 올리지 않아도 됩니다.

## 3. Streamlit Community Cloud 설정

1. Streamlit Community Cloud 접속
2. GitHub 계정 연결
3. New app 선택
4. Repository 선택
5. Branch 선택
6. Main file path에 `app.py` 입력
7. Deploy 클릭

## 4. 접속 비밀번호 설정 선택사항

기본 상태에서는 비밀번호 없이 실행됩니다.
온라인 링크를 제한하고 싶으면 Streamlit Cloud의 Secrets에 아래 값을 추가합니다.

```toml
APP_PASSWORD = "원하는비밀번호"
```

설정 후 앱을 재부팅하면 접속 시 비밀번호 입력 화면이 표시됩니다.

## 5. 데이터 저장 관련 주의

현재 온라인 1차본은 Streamlit Cloud 컨테이너 내부의 CSV 파일에 임시 저장합니다.
컨테이너 재시작 또는 재배포 시 누적 데이터가 초기화될 수 있습니다.
장기 누적 이력이 필요하면 다음 단계에서 Supabase 저장 방식으로 전환하는 것을 권장합니다.

## 6. 사용 방법

- 최초 접속 시 최근 7일 Google News RSS를 자동 수집합니다.
- 상단 조회조건에서 기간, 카테고리, 언론사, 검색어를 조정합니다.
- `RSS 수집` 버튼으로 최신 기사를 다시 수집합니다.
- `진단 정보 보기`는 기본 접힘 상태이며, 링크/수집 문제가 있을 때만 확인합니다.

## 7. 주요 탭

```text
📊 Dashboard
📰 뉴스목록
🔎 키워드 인텔리전스
🛰️ 규제 레이더
🏛️ 규제기관 정책
```
