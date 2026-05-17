# v32 KST 날짜 처리 전역 보정

## 반영 내용

1. 앱 전체 오늘 날짜 기준을 `date.today()`가 아니라 `Asia/Seoul` 기준 `today_kst()`로 통일했습니다.
2. 조회기간 date picker의 `max_value`를 한국시간 오늘 날짜로 고정했습니다.
   - Streamlit Cloud/서버가 UTC여도 한국시간 18일이면 18일 선택 가능하도록 수정했습니다.
3. 기사 발행일시 파싱을 KST 기준으로 통일했습니다.
   - timezone 정보가 있는 값: KST로 변환
   - timezone 정보가 없는 기존 CSV 값: 이미 KST로 저장된 값으로 간주
4. 날짜 필터, 정렬, 최근 24시간 KPI, 카테고리 추이 기준을 모두 KST 변환 후 계산하도록 수정했습니다.
5. Supabase 캐시 조회/삭제 기준을 KST 달력일 기준 최근 N일로 보정했습니다.
6. Supabase `published_at` 저장 시 `+09:00` 오프셋을 포함해 `timestamptz` 오해석 가능성을 줄였습니다.
7. `collect_once.py` 수집 기준일도 KST 기준으로 변경했습니다.

## 추가 파일

- `modules/time_utils.py`

## 검증

```bash
python -m py_compile app.py modules/*.py collect_once.py
```
