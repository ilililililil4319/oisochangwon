# 오이소창원

창원 전입 청년의 P01 정책 조건과 180일 정착 계획을 확인하는 Streamlit 앱입니다.

## 실행 방법

PowerShell에서 프로젝트 폴더로 이동한 뒤 가상환경을 만들고 의존성을 설치합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## 테스트

```powershell
python -m unittest discover -s tests -v
```

## 날짜 계산

정착 계획은 전입일로부터 0, 7, 30, 90, 180일 경과 시점을 표시합니다. P01의 6개월 거주 조건은 180일 고정이 아니라 달력 기준 6개월로 계산하므로 두 날짜가 다를 수 있습니다.

## 미션 데이터

`data/missions.json`은 `oisochangwon_handoff_20261001.zip`의 `handoff_20261001/data/missions.json` 원본을 그대로 복사한 파일입니다. 26개 항목은 `ID`, `개월`, `월별 테마`, `미션`, `난이도(쉬움/보통)`, `연결 기능`, `완료 기준`, `메모`, `is_service_idea`, `서비스 목표` 필드를 가집니다.

`mission_manager.py`가 JSON 구조, 선언된 건수, 필수 필드, ID 중복 및 월별 테마 일관성을 확인합니다. 앱은 원본 ID를 진행 상태 키로 사용하고, 미션을 `개월`과 `월별 테마` 기준으로 접힌 월별 그룹에 표시합니다. JSON에 일 단위 마감일은 없으므로 미션에 임의 날짜를 부여하지 않습니다. `연결 기능`은 데이터의 분류 정보이며 외부 기능을 실행하지 않습니다.

## 미션 진행 상태

미션 체크 상태는 `storage/progress.sqlite3`에 로컬로 저장됩니다. 저장 폴더와 SQLite 파일은 앱 사용 시 자동으로 생성됩니다. `mission_progress` 테이블은 `nickname`, `mission_id`, `completed`, `updated_at`을 저장하고 `(nickname, mission_id)`를 복합 기본키로 사용합니다. 닉네임 앞뒤 공백은 제거해 사용자 키로 사용하며, 같은 닉네임으로 다시 열면 저장된 상태를 불러옵니다. 닉네임은 인증 수단이 아니므로 이 저장 기능은 단일 로컬 사용자 환경을 위한 것입니다.

기존 임시 미션 ID로 저장된 행은 삭제하거나 새 ID에 임의 연결하지 않습니다. 새 미션은 JSON의 `ID`를 사용합니다.

## 전체 E2E 흐름

프로필 입력 → Python 규칙 기반 P01 판정 → D+0/7/30/90/180 경과일 표시 → 원본 월별 미션 및 완료 기준 표시 → 체크 상태를 SQLite에 저장 → 같은 닉네임으로 다시 열어 상태 복원.

P01의 6개월 조건은 달력 기준 `relativedelta(months=6)`이며, JSON의 월별 미션 단계와 D+180 경과일을 서로 임의 변환하지 않습니다.
