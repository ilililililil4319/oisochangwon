# 화면 캡처

기능 구현 **과정**의 테스트 캡처와 기능 구현 **이후**(일정 알림까지 완성 후)의 테스트 캡처를 나눠 둡니다. 그 안은 `tests/` 폴더와 같은 기준(AI 테스트 · 팀 자체 테스트 · 실사용자 테스트)으로, 날짜별 하위 폴더에 넣습니다.

| 폴더 | 내용 |
|---|---|
| `during_development/` (기능 구현 과정 테스트) | |
| `during_development/ai_test/20261002/` | AI 자동 실행 캡처 26장 — 대표 Test Case 6건을 Chrome(Playwright)으로 PC 1600×950·모바일 390×844에서 자동 실행한 화면 (`tests/team_self_test/자체테스트_TestCase.md`의 ‘자동 실행 결과’) |
| `during_development/work_process/20261002/` | 개발 작업 과정 캡처 31장 — 수정 전·후, 에러와 조치, 배포·공유 (`docs/work_process/` 설명 문서) |
| `after_development/` (기능 구현 이후 테스트) | |
| `after_development/team_self_test/20261003/` | 팀 자체 테스트 캡처 37장 — 배포 앱 전체 기능 테스트(01~24), 진해 링크 중복 수정 전·후(25~29), 배포 앱 수정 확인(30~33), 이미영 휴대폰 점검(34~37) |
| `after_development/user_test/` | 실사용자 테스트 캡처 (설문 응답 화면 등, 이름·연락처는 가리고 저장) |
| `after_development/ui_update/20261004/` | UX/UI 수정 후 최신 화면 11장(PC 10·휴대폰 1, 로컬 캡처) |
