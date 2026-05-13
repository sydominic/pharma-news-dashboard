# v28 / v1.34 변경사항

## 반영 내용

1. 제목 위주 분류를 폐기하고 다음 텍스트를 함께 사용합니다.
   - 제목
   - RSS 요약
   - 원문 기사 본문 일부(수집 성공 시)
   - 기사 3~5줄 요약
   - 언론사명 / RSS 검색식

2. 전체 카테고리를 하나의 통합 분류 엔진에서 점수화합니다.
   - 회수/처분
   - 정책/가이드라인
   - 식약처/규제
   - GMP/품질
   - 허가/임상
   - 해외규제
   - 약가/보험
   - 산업/경영

3. 기사별로 대표 카테고리와 다중 태그를 분리했습니다.
   - 예: `FDA Warning Letter` → 대표분류 `GMP/품질`, 다중태그 `GMP/품질, 해외규제`
   - 예: `FDA 1상 IND 승인` → 대표분류 `허가/임상`, 다중태그 `허가/임상, 해외규제`

4. 각 기사 카드의 `원문 열기` 옆에 `기사 요약 보기` 토글을 추가했습니다.
   - 원문 본문 수집 성공 시 본문 일부 기반 요약
   - 본문 수집 실패 시 RSS 제목/요약 기반 요약
   - 정책 탭에서는 분류근거도 같이 표시

5. 저장 컬럼이 추가되었습니다.
   - `article_summary`
   - `article_text`
   - `sub_tags`
   - `classification_reason`
   - `classification_score`
   - `body_fetch_status`

## Supabase 사용 시

기존 Supabase 테이블을 쓰고 있으면 `supabase_migration_v28.sql`을 SQL Editor에서 1회 실행하세요.

실행하지 않아도 앱은 로컬 CSV 기준으로 동작할 수 있으나, Supabase에는 신규 요약/본문/분류근거 컬럼이 저장되지 않습니다.

## 수집 속도 관련

`data/rss_sources.json`의 설정값으로 원문 본문 수집량을 조정할 수 있습니다.

```json
"fetch_article_body": true,
"article_body_timeout_sec": 4,
"article_body_max_chars": 6000,
"max_body_fetch_per_run": 50
```

속도가 너무 느리면 `max_body_fetch_per_run`을 20~30으로 낮추면 됩니다. 더 넓게 본문 기반 분류를 하고 싶으면 80 이상으로 올릴 수 있습니다.
