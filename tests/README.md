# 테스트

오이소창원은 세 가지 방법으로 확인합니다.

| 폴더 | 누가 | 무엇을 |
|---|---|---|
| `ai_test/` | AI(Claude)가 작성한 자동 테스트 코드 | 정책 4단계 판정, 일정 계산, 할 일 저장, Agent 답변 검증, 지역말 사전, 캘린더·리포트, 이메일 동의 등 unittest 115개. 코드를 고칠 때마다 실행 |
| `team_self_test/` | 팀원(사람) | 배포 앱을 PC·휴대폰에서 직접 눌러 보는 대표 Test Case 6건과 10/3 최종 자체 테스트 체크리스트(md·pdf·docx) |
| `user_test/` | 실사용자 3명 | 앱을 써 본 뒤 응답하는 온라인 설문(링크·Apps Script)과 종이 평가지 |

## AI 자동 테스트 실행

저장소 맨 위 폴더에서 실행합니다.

```powershell
python -m unittest discover -s tests/ai_test -v
```

## 순서

1. 코드 수정 → `ai_test` 전부 통과 확인 → GitHub 업로드
2. 배포 앱에서 `team_self_test` 체크리스트로 팀 자체 테스트
3. 문제를 고친 뒤 `user_test` 설문 링크로 실사용자 테스트
