# Supabase 최근 30일 캐시 사용방법

## 목적
Google News RSS를 매번 다시 수집하지 않고, 최근 30일 기사 메타데이터를 Supabase에 캐시하여 앱 최초 로딩 속도를 개선합니다.

저장 대상은 기사 전문이 아니라 아래 메타데이터입니다.

- 제목
- 언론사
- 발행일시
- 링크
- 요약
- 카테고리
- 중요도
- 키워드
- RSS 검색식 정보

## 1. Supabase 테이블 생성

Supabase 프로젝트에서 SQL Editor를 열고 `supabase_schema.sql` 내용을 1회 실행합니다.

생성되는 테이블은 2개입니다.

```text
news_articles
collection_log
```

## 2. Streamlit Cloud Secrets 설정

Streamlit Cloud → App → Settings → Secrets에 아래 값을 입력합니다.

```toml
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "여기에 Supabase key 입력"
```

권장:
- 개인/내부용이면 service_role key 사용 가능
- 공개 앱이면 key 노출 위험을 고려하여 Supabase RLS/권한 설정 필요

## 3. 앱 동작 방식

```text
앱 실행
→ Supabase 설정 있으면 최근 30일 캐시 먼저 로드
→ 캐시가 있으면 화면 즉시 표시
→ RSS 수집 버튼 클릭 시 Google News RSS 수집
→ 정규화/분류 후 Supabase에 upsert
→ 30일 초과 기사 자동 삭제
```

Supabase 설정이 없거나 오류가 나면 기존 로컬 CSV 방식으로 자동 전환됩니다.

## 4. 배포 후 확인

앱에서 `ⓘ 수집범위` 또는 진단 정보를 확인하고, 수집 후 Supabase `news_articles` 테이블에 데이터가 들어오는지 확인합니다.

## 5. 주의

- 최근 30일 캐시만 유지합니다.
- 기사 본문/이미지는 저장하지 않습니다.
- Google News RSS 자체의 누락 가능성은 여전히 있습니다.


## v1.30 속도 개선 메모

- Supabase에는 최근 30일 기사 메타데이터를 보관합니다.
- 앱 최초 실행 시에는 최근 3일만 우선 로드합니다.
- 사용자가 조회기간을 최근 3일보다 길게 선택하면 그때 최근 30일 캐시를 추가 로드합니다.
- Streamlit은 버튼/탭/필터 조작 시 rerun되는 구조입니다. 본 버전은 rerun을 없애는 것이 아니라 Supabase 조회 범위와 캐시를 줄여 체감 속도를 개선하는 방식입니다.


## v1.31 변경
- 앱 최초 실행 및 기본 조회기간은 최근 3일입니다.
- Supabase 캐시 보관기간은 기존과 동일하게 최근 30일입니다.
- 조회기간을 최근 3일보다 길게 선택하면 그때 최근 30일 캐시를 추가 로드합니다.
- RSS 수집 버튼은 선택한 수집기간 기준으로 재검색하며, upsert/중복제거로 기존 기사와 병합합니다. 자동으로 신규 2일만 골라 수집하는 구조는 아닙니다.
