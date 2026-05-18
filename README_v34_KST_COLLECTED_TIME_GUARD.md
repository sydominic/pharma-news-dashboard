# v34 KST collected-time guard

## 수정 목적
v33에서도 일부 Google News RSS 기사 시간이 같은 날 오후처럼 표시되는 문제를 보정했습니다.

## 핵심 변경
- Google News RSS의 GMT/+0000 시각을 무조건 UTC→KST(+9h) 변환하지 않고, RSS의 clock time을 KST 기준으로 우선 해석합니다.
- 기존 Supabase/CSV 캐시에 남아 있는 `17:24` 같은 미래 시각은 `collected_at` 기준으로 판단해 9시간 과보정을 차감합니다.
- 화면 표시, 정렬, Supabase 저장 시 동일한 보정 함수를 사용합니다.

## 예시
- collected_at: 2026-05-18 08:57:12
- 기존 표시: 2026-05-18 17:24:20
- v34 보정: 2026-05-18 08:24:20

