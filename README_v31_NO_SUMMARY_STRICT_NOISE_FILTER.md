# v31 - 기사요약보기 폐기 및 경조사/인사/목록형 기사 차단 강화

## 반영 내용

1. 기사요약보기 기능 폐기 유지
   - 원문 열기 옆 기사 요약 보기 버튼/팝업을 사용하지 않습니다.
   - 기존 캐시에 남아 있던 article_summary도 화면/분류 근거로 사용하지 않도록 비웁니다.

2. 화촉/부음/부고/인사/동정/사령류 기사 제외 강화
   - RSS 수집 단계에서 1차 제외합니다.
   - 본문 일부 수집 후에도 해당 유형이면 다시 제외합니다.
   - 기존 Supabase/CSV 캐시에 남아 있는 데이터도 앱 로드 및 재분류 시 화면에서 제외합니다.

3. 언론사 목록형 쓰레기 기사 제외 강화
   - 예: 데일리팜 데일리팜, 데일리팜 - 데일리팜 등
   - 원문 열기 시 화촉/부음/인사 모음으로 연결되는 홈/목록형 항목을 제외합니다.

4. 무관한 긴 영문 조각 제외
   - 예: When evaluating your system..., communications system, image processing system 등
   - 규제/품질/허가 신호가 없는 외국어 조각은 유사 이슈 묶음 및 화면 표시에서 제외합니다.

5. 유사 이슈 묶음 방어 강화
   - 규제/품질/허가/회수/정책 신호가 없는 일반 잡뉴스는 이슈 묶음 대표로 올리지 않습니다.
   - 경조사/인사/목록형 기사도 이슈 묶음에 표시되지 않도록 2중 필터를 적용했습니다.

## 검증

```bash
python -m py_compile app.py modules/*.py collect_once.py
```

## Git commit message

```bash
git commit -m "Remove article summary UI and strengthen notice noise filters"
```
