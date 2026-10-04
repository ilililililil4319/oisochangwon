/**
 * 오이소창원(AI 기반 창원 정착 지원 Agent) — 실사용자 테스트 설문 + 분석 + 리포트 시스템
 * ------------------------------------------------------------------
 * 무엇을 하는 스크립트인가?
 *   1) setupSurveySystem() 을 실행하면
 *      - 종이 평가지(오이소창원_사용자테스트_평가지_20261003.pdf)와 같은 문항의 구글 설문지를 만들고
 *      - 응답이 쌓일 구글 스프레드시트를 만들어 설문지와 연결하고
 *      - 그 스프레드시트 안에 "분석" 탭(평균 점수, 기기별 완료 현황, 응답자 구성,
 *        기능 선호, 차트, 자유 의견 모음)을 만들어 둡니다.
 *   2) 설문 응답이 들어올 때마다 "분석" 탭이 자동으로 다시 만들어집니다.
 *      (표가 깨졌다면 buildAnalysisDashboard() 를 다시 실행하면 됩니다.)
 *   3) buildReport() 를 실행하면 응답 데이터를 읽어
 *      "오이소창원 실사용자 테스트 결과 리포트" 구글 문서(초안)를 만들고,
 *      팀 엑셀(오이소창원_테스트_제출관리)에 옮겨 붙일 "팀엑셀_옮기기" 탭도 만듭니다.
 *   4) (선택) 응답이 새로 들어올 때마다 실행한 본인 계정 메일로 간단한 알림을 보냅니다.
 *      끄고 싶으면 아래 SEND_EMAIL_NOTIFICATIONS 를 false 로.
 *
 * 2026-10-03 앱 개편 반영(문항 수정)
 *   - 이미 만든 설문지(같은 링크)를 그대로 쓰려면 setupSurveySystem 이 아니라
 *     updateExistingForm() 을 실행하세요. 설문지 주소는 바뀌지 않고 문항만 새로 바뀝니다.
 *     (응답 시트에는 새 문항 열이 오른쪽에 추가되고, 분석은 가장 최근 열을 기준으로 합니다.)
 *   - 문항을 바꾸기 전에 받은 점검용 응답은 응답 탭에서 행 삭제 후 buildAnalysisDashboard() 실행.
 *
 * 사용 방법(처음 설치할 때)
 *   1. https://script.google.com 접속 → "새 프로젝트" (설문 담당자 본인 구글 계정)
 *   2. 기본으로 열려 있는 코드를 모두 지우고 이 파일 내용을 통째로 붙여넣기
 *   3. 상단 "저장"(디스크 아이콘) 클릭, 프로젝트 이름은 예: 오이소창원 설문
 *   4. 함수 선택 드롭다운에서 setupSurveySystem 선택 → "실행"
 *   5. 처음 실행하면 "이 앱은 Google에서 확인하지 않았습니다" 경고가 뜹니다.
 *      → "고급" → "(프로젝트 이름)(으)로 이동" → 권한 허용
 *      직접 만든 스크립트이므로 안전합니다.
 *   6. 실행 로그에 설문지 링크·편집 링크·스프레드시트 링크가 출력됩니다. 복사해 두세요.
 *   7. 설문지 링크를 실사용자에게 전달합니다(응답 순서대로 U01, U02 … 자동 번호).
 *   8. 응답이 들어오면 스프레드시트의 "분석" 탭에서 결과를 확인합니다.
 *   9. 응답이 모두 들어오면 buildReport() 를 실행해 리포트 초안(그래프 포함)을 만듭니다.
 *
 * 개인정보 원칙(오이소창원 기획안과 같음)
 *   - 이름·연락처·이메일은 받지 않습니다. 응답이 들어온 순서대로 U01, U02, U03 번호를 자동으로 붙여 구분합니다.
 *   - 설문지의 이메일 수집 기능은 꺼 둡니다(setCollectEmail(false)).
 *   - 알림 메일은 응답자가 아니라 스크립트를 실행한 본인 계정으로만 갑니다.
 *
 * 주의
 *   - 이 스크립트는 실행하는 "본인의" 구글 계정에 설문지·시트·문서를 만듭니다.
 *   - 작성 환경(Claude)에서는 구글 API에 접속할 수 없어 실제로 실행해 검증하지는
 *     못했습니다(문법 검사만 함). 실행 후 테스트 응답을 1건 보내 정상 동작을 꼭 확인하세요.
 *   - 표본이 작아 평균·비율은 참고용입니다. 리포트에도 이 한계를 적어 둡니다.
 *
 * 2026-10-04 수정(리포트 빈칸 문제)
 *   - 원인: 예전 버전(과제 6개·'취업 상태'·기능 5개) 스크립트를 붙여 넣으면 지금 설문지 문항 제목과 달라
 *     열을 못 찾고 0 / 0 / 0, '-', (응답 없음)으로 채워집니다. 이 파일(과제 8개·'하는 일'·기능 6개)을 쓰세요.
 *   - 열을 못 찾으면 0 대신 "열 없음(스크립트 버전 확인)"으로 표시하고, 실행 로그에 못 찾은 문항을 적습니다.
 *   - 리포트에 분석 탭 그래프 2개(항목별 평균 막대, 다시 사용·추천 파이)를 이미지로 넣습니다.
 *   - 8장 개선 반영 계획을 빈 표 대신 IMPROVEMENT_PLAN 값으로 채웁니다(내용은 사람이 검수·수정).
 *   - 응답 수는 고정값(3명)이 아니라 실제 응답 수로 표시합니다.
 */

// ===================== 설정 =====================
// 이미 배포한 설문지(2026-10-03 새로 생성). updateExistingForm()이 이 설문지의 문항을 새로 바꿉니다.
// 공개 저장소에는 설문지 ID를 두지 않습니다. 스크립트 속성 FORM_ID가 없을 때만 아래에 설문지 편집 링크의 /d/ 뒤 ID를 넣으세요.
const EXISTING_FORM_ID = '';
const APP_URL = 'https://oisochangwon-4fuybothxlr78qnnaappqv.streamlit.app/';
const FORM_TITLE = '오이소창원 — 실사용자 테스트 설문';
const SPREADSHEET_TITLE = '오이소창원 — 설문 응답 및 분석';
const REPORT_TITLE = '오이소창원 실사용자 테스트 결과 리포트(초안)';
const SEND_EMAIL_NOTIFICATIONS = true;                 // 응답이 올 때마다 본인 계정으로 메일 알림
const NOTIFY_EMAIL = Session.getActiveUser().getEmail(); // 기본값: 실행한 본인 계정

const INTRO_TEXT =
  '안녕하세요. 오이소창원(AI 기반 창원 정착 지원 Agent)을 사용해 주셔서 감사합니다.\n' +
  '이 설문은 서비스를 개선하고 경진대회 결과보고서에 반영하기 위한 목적으로만 사용되며, ' +
  '이름·연락처·이메일 등 개인정보는 수집하지 않습니다.\n' +
  '소요 시간은 약 10~15분이며, 정답은 없으니 느끼신 그대로 편하게 답변해 주세요.\n' +
  '테스트 앱: ' + APP_URL + '\n' +
  '(앱의 이메일 알림은 선택 기능입니다. 테스트에서는 켜 보지 않아도 되고, 켜더라도 이 설문과는 관계없습니다.)';

const CONFIRMATION_TEXT =
  '소중한 시간을 내어 응답해 주셔서 감사합니다. 주신 의견은 서비스 개선에 반영하겠습니다. — 오이소창원 팀';

// 응답 번호는 묻지 않고, 응답이 들어온 순서(응답 시트의 행 순서)대로 U01, U02, U03…을 자동으로 붙입니다.
function autoId_(n) { return 'U' + (n < 10 ? '0' : '') + n; }

// 평가지(종이/PDF)와 동일한 문항
// 2026-10-03 앱 구성: 나의 조건 입력 → ①~④ 기능 + 오이소창원(코디네이터 Agent)에게 물어보기
const TASKS = [
  '나의 조건 입력(나이·전입일·하는 일·차량, 실명 없이)',
  '① 맞춤 혜택 확인(해당 가능·조건부·직접 확인)',
  '② 정착 할 일(1~6개월) 확인 → 체크하고 저장',
  '② 캘린더 파일(.ics)·정착 리포트 저장(이메일 알림은 원할 때만)',
  '② 창원 생활 정보 둘러보기(장소 카드·지도·이동 방법)',
  '③ 불편 사항 말하기 → 접수 창구 안내 받기',
  '④ 지역말 뜻 물어보기 → 뜻 설명 받기',
  '오이소창원(코디네이터 Agent)에게 물어보기 → 답변과 공식 안내 링크 확인',
];
const TASK_STATUS = ['완료', '부분완료', '미완료'];

const LIKERT_ITEMS = [
  '내 상황(전입일·하는 일 등)에 맞춘 안내라고 느꼈다',
  '출처·확인일이 있어 안내를 믿을 수 있었다',
  '언제 무엇을 해야 하는지(다음 행동)가 분명했다',
  '창원 생활 정보(가볼 곳·이동 방법) 안내가 유용했다',
  '캘린더·정착 리포트 저장이 일정 관리에 도움이 됐다',
  '오이소창원(코디네이터 Agent)의 답변이 이해하기 쉽고 공식 안내 링크가 도움이 됐다',
  '화면(모바일·PC)이 보기 편했다',
  '창원에 새로 온 청년의 정착에 실제로 도움이 될 것 같다',
];
// 휴대폰 화면에서 오른쪽 칸이 잘려 보이지 않는 문제 때문에 5점(매우 그렇다)을 맨 앞에 둡니다.
const LIKERT_COLUMNS = [
  '5 (매우 그렇다)', '4 (그렇다)', '3 (보통이다)', '2 (아니다)', '1 (전혀 아니다)',
];
// 전체 만족도도 같은 방향(5점이 맨 앞)으로 맞추기 위해 객관식으로 만듭니다.
const SAT_CHOICES = ['5 (매우 만족)', '4 (만족)', '3 (보통)', '2 (불만족)', '1 (전혀 만족하지 않음)'];

const FEATURE_CHOICES = [
  '① 창원 청년 맞춤형 혜택 알림',
  '② 정착 할 일·일정(캘린더·리포트)',
  '② 창원 생활 정보 둘러보기',
  '③ 불편사항 행정 접수안내',
  '④ 창원 지역말 번역',
  '오이소창원(코디네이터 Agent)에게 물어보기',
];
// 알림 방식 선호(이메일 알림은 사용자가 원할 때만 동의 후 제공)
const ALERT_TITLE = '정착 일정 알림은 어떤 방식이 좋으신가요?';
const ALERT_CHOICES = ['캘린더 파일(.ics)로 내 캘린더에', '이메일 알림(동의 후)', '둘 다', '알림은 필요 없음'];
const BEST_FEATURE_TITLE = '가장 유용했던 기능은 무엇인가요?';
const WORST_FEATURE_TITLE = '가장 개선이 필요한 기능은 무엇인가요?';

const OPEN_QUESTIONS = [
  '가장 도움이 되었던 점은 무엇인가요?',
  '가장 불편했거나 헷갈렸던 점은 무엇인가요?',
  '기타 의견이나 제안이 있다면 자유롭게 적어 주세요.',
];

// 8장 개선 반영 계획 — 사람이 작성·검수한 내용(근거 / 개선 내용 / 담당 / 반영 여부). 바뀌면 여기만 고치고 buildReport() 다시 실행
const IMPROVEMENT_PLAN = [
  ['타지역 거주기간을 왜 묻는지 모름(U01 기타 의견)', '조건 칸 설명을 칸 아래에 항상 표시, 기업노동자 전입지원금(타 시·군·구 1년 이상 주민등록) 조건 확인용이라고 이유 표시', 'B', '반영(10/3)'],
  ['화면 보기 편함이 가장 낮음, UI 디자인 더 다듬기(U01)', '첫 화면 정리(안내 문구·흐름 5단계·메뉴는 시작 후 표시), 한글 줄바꿈·여백·글자 대비, 카드 높이 통일 → 10/4 첫 화면 디자인 새로 정리', 'B', '반영(10/3~10/4)'],
  ['가장 개선 필요 기능: ② 생활 정보 둘러보기', '‘자세히 보기’ 안내, 상세 아래 ‘장소 목록으로 돌아가기’, 필터 변경 시 선택값·상세 일치, 차량 권장 장소가 없을 때 이유 안내', 'B·C', '반영(10/3)'],
  ['캘린더·리포트 저장 완료가 가장 적음(4단계)', '휴대폰에서 내려받은 파일 여는 방법 안내, 저장 버튼 아래 안내 정리', 'B', '반영(10/3)'],
  ['질문(입력) 문항이 많음(U04)', '앱 조건 입력 7칸마다 필요한 이유 표시. 설문 문항인지 앱 입력 칸인지 응답자 확인 후 줄일 칸 검토', 'B', '확인 필요'],
  ['모바일 미완료(1·2·6단계)', '조건 입력 버튼을 첫 화면 가운데 배치·입력 전 잠금 안내, 불편사항은 결과 위치로 자동 이동 — 막힌 지점 응답자 확인', 'B·C', '확인 필요'],
  ['화면을 닫으면 처음부터 다시 시작(U03)', '회원가입 없이 실명·연락처를 받지 않는 설계라 조건은 저장하지 않음. 같은 닉네임이면 체크한 할 일은 이어지고, 캘린더·정착 리포트로 기기에 저장하도록 안내', '—', '설계상 한계(안내 유지)'],
];
const MISSING = '열 없음(스크립트 버전 확인)';

// 응답자 정보 — 팀 엑셀 「사용자테스트_참여자」 시트 열과 같음
const AGE_TITLE = '연령대';
const AGE_CHOICES = ['19~24세', '25~29세', '30~34세', '35~39세'];
const LIVE_TITLE = '창원 거주·생활 경험';
const LIVE_CHOICES = ['창원 전입 6개월 이내', '6개월~1년', '1년 이상', '창원에 살지 않음'];
const MOVE_TITLE = '타지역에서 이주한 경험';
const MOVE_CHOICES = ['있음', '없음'];
const JOB_TITLE = '하는 일';
const JOB_CHOICES = ['직장인', '자영업', '학생', '기타(구직 중 등)'];
const AI_TITLE = 'AI 서비스 사용 경험';
const AI_CHOICES = ['자주 사용', '가끔 사용', '거의 없음'];
const PROFILE_ITEMS = [
  [AGE_TITLE, AGE_CHOICES, true],
  [LIVE_TITLE, LIVE_CHOICES, false],
  [MOVE_TITLE, MOVE_CHOICES, false],
  [JOB_TITLE, JOB_CHOICES, false],
  [AI_TITLE, AI_CHOICES, false],
];  // [제목, 보기, 기타 허용]

const REUSE_CHOICES = ['예', '아니오', '잘 모르겠음'];

// 그리드 문항의 제목(= 스프레드시트 헤더에 "제목 [행 이름]" 형태로 들어갑니다)
const GRID_TITLE_MOBILE = '[모바일] 각 단계의 테스트 결과를 표시해 주세요';
const GRID_TITLE_PC = '[PC·노트북] 각 단계의 테스트 결과를 표시해 주세요';
const GRID_TITLE_LIKERT = '아래 항목에 대해 동의하는 정도를 선택해 주세요';
const SCALE_TITLE = '전체 만족도';
const REUSE_TITLE = '다시 사용·추천 의향';

const COLOR_MAIN = '#063465';
const COLOR_SUB = '#EEF4FB';

// ===================== 메인 실행 함수 =====================

function setupSurveySystem() {
  const props = PropertiesService.getScriptProperties();
  const existingSsId = props.getProperty('SPREADSHEET_ID');
  const existingFormId = props.getProperty('FORM_ID');

  // 이미 만들어 둔 적이 있다면 새로 만들지 않고 기존 링크만 다시 보여 줍니다.
  // (실행 버튼을 두 번 눌러도 설문지가 중복 생성되지 않게 하기 위함입니다.)
  if (existingSsId && existingFormId) {
    try {
      const ss = SpreadsheetApp.openById(existingSsId);
      const form = FormApp.openById(existingFormId);
      Logger.log('이미 만들어진 설문 시스템이 있어 다시 만들지 않았습니다.');
      Logger.log('새로 시작하고 싶다면 resetSurveySystem()을 먼저 실행한 뒤 이 함수를 다시 실행하세요.');
      logLinks_(form, ss);
      return;
    } catch (e) {
      Logger.log('저장된 설문/시트를 열지 못해 새로 만듭니다. (사유: ' + e.message + ')');
    }
  }

  const form = buildForm_();
  const ss = linkResponseSpreadsheet_(form);

  props.setProperty('SPREADSHEET_ID', ss.getId());
  props.setProperty('FORM_ID', form.getId());
  installFormSubmitTrigger_(form);

  logLinks_(form, ss);
  Logger.log('응답이 쌓인 뒤 buildAnalysisDashboard() 를 다시 실행하면 분석 탭이 최신 문항 구성에 맞춰 다시 만들어집니다.');

  // 응답이 아직 없어도 헤더 행은 바로 생기므로 분석 탭도 함께 만들어 둡니다.
  try {
    Utilities.sleep(2000);
    buildAnalysisDashboard();
  } catch (e) {
    Logger.log('분석 탭은 첫 응답이 들어온 뒤 buildAnalysisDashboard() 를 다시 실행해 만들어 주세요. (사유: ' + e.message + ')');
  }
}

function logLinks_(form, ss) {
  Logger.log('====================================================');
  Logger.log('설문지(실사용자에게 보낼 링크): ' + form.getPublishedUrl());
  Logger.log('설문지 편집 화면(관리자용):      ' + form.getEditUrl());
  Logger.log('응답 스프레드시트:               ' + ss.getUrl());
  Logger.log('====================================================');
}

// ===================== 설문지 생성 =====================

function buildForm_() {
  const form = FormApp.create(FORM_TITLE);
  addFormItems_(form);
  return form;
}

// 이미 배포한 설문지의 링크는 그대로 두고 문항만 현재 앱에 맞게 다시 만듭니다.
function updateExistingForm() {
  const props = PropertiesService.getScriptProperties();
  const formId = props.getProperty('FORM_ID') || EXISTING_FORM_ID;
  if (!formId) throw new Error('설문지 ID가 없습니다. 코드 위쪽 EXISTING_FORM_ID에 설문지 편집 링크의 /d/ 뒤 ID를 넣어 주세요.');
  const form = FormApp.openById(formId);
  form.getItems().forEach(function (item) { form.deleteItem(item); });
  form.setTitle(FORM_TITLE);
  addFormItems_(form);
  props.setProperty('FORM_ID', form.getId());

  let ss = null;
  try {
    if (form.getDestinationType() === FormApp.DestinationType.SPREADSHEET) {
      ss = SpreadsheetApp.openById(form.getDestinationId());
    }
  } catch (e) { ss = null; }
  if (!ss) ss = linkResponseSpreadsheet_(form);
  props.setProperty('SPREADSHEET_ID', ss.getId());
  installFormSubmitTrigger_(form);
  // 문항을 지우고 다시 만들면 응답 탭에 같은 제목의 열이 또 생겨 "중복된 열 이름" 오류가 납니다.
  // 그래서 응답 탭을 지금 문항 기준으로 새로 만듭니다(설문지에 남아 있는 응답은 새 탭에 다시 들어갑니다).
  rebuildResponseSheet_(form, ss);
  logLinks_(form, ss);
  Logger.log('설문지 링크는 그대로이고 문항만 바뀌었습니다. 응답 탭도 새 문항 기준으로 다시 만들었습니다.');
}

// ===================== 응답 탭 다시 만들기("중복된 열 이름" 오류 해결) =====================

// 응답 탭(Form Responses 1)에 "잘못됨: 중복된 열 이름이 발견됨"이 뜰 때 실행하세요.
// 설문지에 저장된 응답은 지우지 않고, 응답 탭만 지금 문항 기준으로 새로 만듭니다.
function fixResponseSheet() {
  const ctx = openFormAndSheet_();
  rebuildResponseSheet_(ctx.form, ctx.ss);
}

// 실사용자에게 링크를 보내기 직전에 한 번 실행하세요(점검용 응답 정리).
// 설문지에 쌓인 응답을 모두 지우고 빈 응답 탭을 새로 만들어, 실사용자 번호가 U01부터 붙게 합니다.
function clearTestResponses() {
  const ctx = openFormAndSheet_();
  const n = ctx.form.getResponses().length;
  ctx.form.deleteAllResponses();
  Logger.log('설문지 응답 ' + n + '건을 지웠습니다.');
  rebuildResponseSheet_(ctx.form, ctx.ss);
}

function openFormAndSheet_() {
  const props = PropertiesService.getScriptProperties();
  const formId = props.getProperty('FORM_ID') || EXISTING_FORM_ID;
  if (!formId) throw new Error('설문지 ID가 없습니다. 코드 위쪽 EXISTING_FORM_ID에 설문지 편집 링크의 /d/ 뒤 ID를 넣어 주세요.');
  const form = FormApp.openById(formId);
  let ss = null;
  try { ss = SpreadsheetApp.openById(form.getDestinationId()); } catch (e) { ss = findExistingSpreadsheet_(); }
  if (!ss) throw new Error('응답 스프레드시트를 찾지 못했습니다.');
  props.setProperty('FORM_ID', form.getId());
  props.setProperty('SPREADSHEET_ID', ss.getId());
  return { form: form, ss: ss };
}

function rebuildResponseSheet_(form, ss) {
  // 1) 설문지와 연결된 기존 응답 탭(들)을 찾아 둡니다.
  const oldSheets = ss.getSheets().filter(function (sh) { return !!sh.getFormUrl(); });
  // 2) 연결을 끊었다가 같은 스프레드시트에 다시 연결하면, 지금 문항만으로 된 새 응답 탭이 생깁니다.
  form.removeDestination();
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());
  SpreadsheetApp.flush();
  Utilities.sleep(3000);
  ss = SpreadsheetApp.openById(ss.getId());
  const oldIds = oldSheets.map(function (sh) { return sh.getSheetId(); });
  const linked = ss.getSheets().filter(function (sh) {
    return !!sh.getFormUrl() && oldIds.indexOf(sh.getSheetId()) === -1;
  });
  if (!linked.length) throw new Error('새 응답 탭을 찾지 못했습니다. 잠시 뒤 fixResponseSheet()를 다시 실행해 주세요.');
  const fresh = linked[0];
  // 3) 열 이름이 겹치던 예전 탭은 지우고, 새 탭 이름을 Form Responses 1로 맞춥니다.
  oldSheets.forEach(function (sh) {
    try { ss.deleteSheet(ss.getSheetByName(sh.getName())); } catch (e) { Logger.log('예전 응답 탭 삭제 실패: ' + e.message); }
  });
  try { fresh.setName('Form Responses 1'); } catch (e) { Logger.log('탭 이름 변경 생략: ' + e.message); }
  Logger.log('응답 탭을 새로 만들었습니다: ' + fresh.getName() + ' (응답 ' + Math.max(0, fresh.getLastRow() - 1) + '건)');
  try {
    buildAnalysisDashboard();
  } catch (e) {
    Logger.log('분석 탭은 첫 응답 뒤 buildAnalysisDashboard()를 실행해 만들어 주세요. (사유: ' + e.message + ')');
  }
}

function addFormItems_(form) {
  form.setDescription(INTRO_TEXT);
  form.setCollectEmail(false);            // 이메일 수집 안 함(익명)
  form.setLimitOneResponsePerUser(false); // 로그인 요구 안 함
  form.setShowLinkToRespondAgain(false);
  form.setConfirmationMessage(CONFIRMATION_TEXT);
  form.setProgressBar(true);

  // ---- 0. 응답자 정보 ----
  form.addPageBreakItem()
    .setTitle('0. 응답자 정보')
    .setHelpText('간단한 구분을 위한 정보만 여쭙니다. 이름·연락처·이메일은 받지 않습니다.');

  PROFILE_ITEMS.forEach(function (p) {
    const item = form.addMultipleChoiceItem().setTitle(p[0]).setChoiceValues(p[1]).setRequired(true);
    if (p[2]) item.showOtherOption(true);
  });

  // ---- 1. 테스트 진행 ----
  form.addPageBreakItem()
    .setTitle('1. 테스트 진행')
    .setHelpText('테스트 앱(' + APP_URL + ')을 모바일(스마트폰)과 PC·노트북 두 기기 모두에서 아래 순서대로 사용해 보시고, ' +
      '각 단계마다 기기별로 표시해 주세요. 한 기기만 사용했다면 그 기기만 표시해도 됩니다.');

  form.addGridItem()
    .setTitle(GRID_TITLE_MOBILE)
    .setRows(TASKS)
    .setColumns(TASK_STATUS)
    .setRequired(false);

  form.addGridItem()
    .setTitle(GRID_TITLE_PC)
    .setRows(TASKS)
    .setColumns(TASK_STATUS)
    .setRequired(false);

  // ---- 2. 항목별 평가 ----
  form.addPageBreakItem()
    .setTitle('2. 항목별 평가')
    .setHelpText('5 = 매우 그렇다 · 4 = 그렇다 · 3 = 보통이다 · 2 = 아니다 · 1 = 전혀 아니다 (휴대폰에서는 옆으로 밀어 모든 칸을 볼 수 있어요)');

  form.addGridItem()
    .setTitle(GRID_TITLE_LIKERT)
    .setRows(LIKERT_ITEMS)
    .setColumns(LIKERT_COLUMNS)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle(BEST_FEATURE_TITLE)
    .setChoiceValues(FEATURE_CHOICES)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle(WORST_FEATURE_TITLE)
    .setChoiceValues(FEATURE_CHOICES)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle(ALERT_TITLE)
    .setHelpText('이메일 알림은 사용자가 직접 신청하고 개인정보 수집·이용과 수신에 동의한 경우에만 보내는 선택 기능입니다.')
    .setChoiceValues(ALERT_CHOICES)
    .setRequired(false);

  // ---- 3. 자유 의견 ----
  form.addPageBreakItem()
    .setTitle('3. 자유 의견')
    .setHelpText('편하게 자유롭게 적어 주세요. 이름·연락처 등 개인정보는 적지 말아 주세요.');

  OPEN_QUESTIONS.forEach(function (q) {
    form.addParagraphTextItem().setTitle(q).setRequired(false);
  });

  // ---- 4. 종합 ----
  form.addPageBreakItem().setTitle('4. 종합');

  form.addMultipleChoiceItem()
    .setTitle(SCALE_TITLE)
    .setChoiceValues(SAT_CHOICES)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle(REUSE_TITLE)
    .setChoiceValues(REUSE_CHOICES)
    .setRequired(true);
}

// ===================== 응답 스프레드시트 연결 =====================

function linkResponseSpreadsheet_(form) {
  const ss = SpreadsheetApp.create(SPREADSHEET_TITLE);
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());
  return ss;
}

// 이미 만들어 둔 응답 스프레드시트를 다시 찾는 보조 함수.
// 먼저 스크립트 속성(가장 확실한 방법)을 보고, 없으면 드라이브에서 이름으로 검색합니다.
function findExistingSpreadsheet_() {
  const savedId = PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID');
  if (savedId) {
    try {
      return SpreadsheetApp.openById(savedId);
    } catch (e) {
      Logger.log('저장된 스프레드시트 ID로 열지 못했습니다. 이름으로 다시 검색합니다.');
    }
  }
  const files = DriveApp.getFilesByName(SPREADSHEET_TITLE);
  if (files.hasNext()) {
    return SpreadsheetApp.openById(files.next().getId());
  }
  return null;
}

// 처음부터 다시 시작하고 싶을 때 실행하세요.
// 주의: 이미 만든 설문지·스프레드시트·리포트 문서를 삭제하지는 않습니다.
// (구글 드라이브에서 직접 지워야 완전히 삭제됩니다.) 이 함수는 "이미 만들었다"는
// 저장 기록과 응답 트리거만 지워서, setupSurveySystem()을 다시 실행할 수 있게 해 줍니다.
function resetSurveySystem() {
  const props = PropertiesService.getScriptProperties();
  props.deleteProperty('SPREADSHEET_ID');
  props.deleteProperty('FORM_ID');
  props.deleteProperty('REPORT_DOC_ID');
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'onSurveySubmit_') ScriptApp.deleteTrigger(t);
  });
  Logger.log('저장된 기록과 트리거를 지웠습니다. setupSurveySystem()을 다시 실행하면 새로 만들어집니다.');
}

// ===================== 응답 시트 찾기 =====================

// 실제 Google Forms 응답 시트를 찾는 함수(빈 "시트1"을 잘못 잡지 않도록)
function findResponseSheet_(ss) {
  // 0순위: 지금 설문지와 연결된 탭(getFormUrl이 있는 탭)
  const linkedSheets = ss.getSheets().filter(function (s) { return !!s.getFormUrl() && s.getLastColumn() > 0; });
  if (linkedSheets.length) return linkedSheets[linkedSheets.length - 1];
  const knownNames = ['Form Responses 1', '설문지 응답 시트1', 'Form Responses 2'];
  for (let i = 0; i < knownNames.length; i++) {
    const s = ss.getSheetByName(knownNames[i]);
    if (s && s.getLastColumn() > 0) return s;
  }
  const sheets = ss.getSheets();
  // 이름이 바뀐 경우: 1행 A열이 Timestamp/타임스탬프인 시트
  for (let i = 0; i < sheets.length; i++) {
    const s = sheets[i];
    if (isOwnSheet_(s.getName()) || s.getLastColumn() < 1) continue;
    const firstHeader = String(s.getRange(1, 1).getDisplayValue()).trim().toLowerCase();
    if (firstHeader.indexOf('timestamp') !== -1 || firstHeader.indexOf('타임스탬프') !== -1) return s;
  }
  // 마지막 보완: 2행 이상 데이터가 있는 시트
  for (let i = 0; i < sheets.length; i++) {
    const s = sheets[i];
    if (isOwnSheet_(s.getName())) continue;
    if (s.getLastRow() >= 2 && s.getLastColumn() >= 2) return s;
  }
  return null;
}

function isOwnSheet_(name) {
  return name === '분석' || name === '팀엑셀_옮기기';
}

function getResponseContext_() {
  const ss = findExistingSpreadsheet_();
  if (!ss) throw new Error('응답 스프레드시트를 찾을 수 없습니다. setupSurveySystem()을 먼저 실행해 주세요.');
  const respSheet = findResponseSheet_(ss);
  if (!respSheet) throw new Error('응답 시트를 찾지 못했습니다. 잠시 기다린 뒤 다시 실행해 주세요.');
  const lastCol = respSheet.getLastColumn();
  if (lastCol < 1) throw new Error('응답 시트에 헤더가 없습니다. 응답 탭을 확인해 주세요.');
  const headers = respSheet.getRange(1, 1, 1, lastCol).getValues()[0].map(String);
  return { ss: ss, respSheet: respSheet, respName: respSheet.getName(), headers: headers };
}

// 헤더에서 문항 제목이 들어 있는 열 번호(1부터). 못 찾으면 -1
function findCol_(headers, matchText) {
  // 1순위: 헤더가 문항 제목과 정확히 같은 열(예: '취업 상태'가 과제 문장 안에도 있어 오인하지 않도록)
  // 문항을 바꾸면 같은 제목의 새 열이 오른쪽에 생기므로 오른쪽(가장 최근) 열부터 찾습니다.
  for (let i = headers.length - 1; i >= 0; i--) {
    if (headers[i].trim() === matchText) return i + 1;
  }
  for (let i = headers.length - 1; i >= 0; i--) {
    if (headers[i].indexOf(matchText) !== -1) return i + 1;
  }
  return -1;
}

// 그리드 문항: "그리드 제목 [행 이름]" 헤더의 열 번호
function findGridCol_(headers, gridTitle, rowName) {
  const marker = '[' + rowName + ']';
  for (let i = headers.length - 1; i >= 0; i--) {
    if (headers[i].indexOf(gridTitle) !== -1 && headers[i].indexOf(marker) !== -1) return i + 1;
  }
  return -1;
}

function colLetter_(col) {
  let s = '', n = col;
  while (n > 0) {
    const m = (n - 1) % 26;
    s = String.fromCharCode(65 + m) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

// ===================== 분석 탭 생성/갱신 =====================

function buildAnalysisDashboard() {
  const ctx = getResponseContext_();
  const ss = ctx.ss, headers = ctx.headers, respName = ctx.respName;

  function rangeA1(col) {
    const L = colLetter_(col);
    return "'" + respName + "'!" + L + '2:' + L;
  }

  // 기존 분석 탭 삭제 후 새로 생성
  const old = ss.getSheetByName('분석');
  if (old) ss.deleteSheet(old);
  const sheet = ss.insertSheet('분석', 0);
  sheet.setTabColor(COLOR_MAIN);

  let row = 1;
  function title(text, span) {
    sheet.getRange(row, 1, 1, span || 8).merge().setValue(text).setFontWeight('bold')
      .setFontColor('#FFFFFF').setBackground(COLOR_MAIN).setFontSize(12);
    row += 1;
  }
  function subhead(text, span) {
    sheet.getRange(row, 1, 1, span || 8).merge().setValue(text).setFontWeight('bold')
      .setFontColor(COLOR_MAIN).setBackground(COLOR_SUB);
    row += 1;
  }
  function countRow(label, col, choices) {
    // 보기별 응답 수(가로로 나열)
    sheet.getRange(row, 1).setValue(label).setFontWeight('bold');
    sheet.getRange(row, 2, 1, choices.length).setValues([choices]).setFontWeight('bold');
    row += 1;
    if (col !== -1) {
      const rng = rangeA1(col);
      choices.forEach(function (c, i) {
        sheet.getRange(row, 2 + i).setFormula('=SUMPRODUCT(--(TRIM(' + rng + ')="' + c + '"))');
      });
    } else {
      sheet.getRange(row, 2).setValue('(응답 열을 찾지 못함)');
    }
    const r = row;
    row += 1;
    return r;
  }

  title('오이소창원 — 실사용자 테스트 설문 결과 분석', 8);
  sheet.getRange(row, 1).setValue('마지막 갱신: ' + new Date().toLocaleString('ko-KR'));
  row += 1;
  sheet.getRange(row, 1).setValue('총 응답 수');
  sheet.getRange(row, 2).setFormula("=COUNTIF('" + respName + "'!A2:A,\"<>\")");
  sheet.getRange(row, 3).setValue('※ 표본이 작아 평균·비율은 참고용(응답 순서 번호 U01~)');
  row += 2;

  // ---- 표 1: 항목별 평가 평균 ----
  subhead('1. 항목별 평가 — 평균 점수(5점 만점)', 4);
  sheet.getRange(row, 1, 1, 3).setValues([['문항', '평균', '응답 수']]).setFontWeight('bold');
  row += 1;
  const likertStartRow = row;
  LIKERT_ITEMS.forEach(function (q) {
    const c = findGridCol_(headers, GRID_TITLE_LIKERT, q);
    sheet.getRange(row, 1).setValue(q);
    if (c !== -1) {
      const rng = rangeA1(c);
      // 그리드 응답은 "4 (그렇다)" 같은 문자열이라 앞 숫자만 뽑아 평균을 냅니다.
      sheet.getRange(row, 2).setFormula(
        '=IFERROR(ROUND(AVERAGE(ARRAYFORMULA(IFERROR(VALUE(REGEXEXTRACT(' + rng + ',"^[1-5]")),""))),2),"")');
      sheet.getRange(row, 3).setFormula('=COUNTIF(' + rng + ',"<>")');
    } else {
      sheet.getRange(row, 2).setValue('열을 찾지 못함');
      sheet.getRange(row, 3).setValue(0);
    }
    row += 1;
  });
  const likertEndRow = row - 1;
  row += 1;

  // ---- 표 2: 테스트 진행 현황 ----
  subhead('2. 테스트 진행 현황 — 기기별 완료 상태 수', 8);
  sheet.getRange(row, 1, 1, 7).setValues([[
    '단계', '모바일 완료', '모바일 부분완료', '모바일 미완료', 'PC 완료', 'PC 부분완료', 'PC 미완료',
  ]]).setFontWeight('bold');
  row += 1;
  TASKS.forEach(function (task, idx) {
    const mCol = findGridCol_(headers, GRID_TITLE_MOBILE, task);
    const pCol = findGridCol_(headers, GRID_TITLE_PC, task);
    sheet.getRange(row, 1).setValue((idx + 1) + '. ' + task);
    [[mCol, 2], [pCol, 5]].forEach(function (pair) {
      if (pair[0] === -1) return;
      const rng = rangeA1(pair[0]);
      TASK_STATUS.forEach(function (st, i) {
        sheet.getRange(row, pair[1] + i).setFormula('=COUNTIF(' + rng + ',"' + st + '")');
      });
    });
    row += 1;
  });
  row += 1;

  // ---- 표 3: 응답자 구성 ----
  subhead('3. 응답자 구성(개인정보 없이 구분용)', 8);
  PROFILE_ITEMS.forEach(function (p) {
    countRow(p[0], findCol_(headers, p[0]), p[1]);
  });
  row += 1;

  // ---- 표 4: 기능 선호 ----
  subhead('4. 기능별 선호 — 가장 유용 / 가장 개선 필요', 8);
  sheet.getRange(row, 1, 1, 3).setValues([['기능', '가장 유용', '가장 개선 필요']]).setFontWeight('bold');
  row += 1;
  const bestCol = findCol_(headers, BEST_FEATURE_TITLE);
  const worstCol = findCol_(headers, WORST_FEATURE_TITLE);
  FEATURE_CHOICES.forEach(function (f) {
    sheet.getRange(row, 1).setValue(f);
    if (bestCol !== -1) sheet.getRange(row, 2).setFormula('=SUMPRODUCT(--(TRIM(' + rangeA1(bestCol) + ')="' + f + '"))');
    if (worstCol !== -1) sheet.getRange(row, 3).setFormula('=SUMPRODUCT(--(TRIM(' + rangeA1(worstCol) + ')="' + f + '"))');
    row += 1;
  });
  row += 1;
  countRow('알림 방식 선호', findCol_(headers, ALERT_TITLE), ALERT_CHOICES);
  row += 1;

  // ---- 표 5: 종합 ----
  subhead('5. 종합', 4);
  const satCol = findCol_(headers, SCALE_TITLE);
  const reuseCol = findCol_(headers, REUSE_TITLE);
  sheet.getRange(row, 1).setValue('전체 만족도 평균(5점 만점)');
  if (satCol !== -1) {
    // 응답이 "5 (매우 만족)" 같은 문자열이라 앞 숫자만 뽑아 평균을 냅니다.
    sheet.getRange(row, 2).setFormula(
      '=IFERROR(ROUND(AVERAGE(ARRAYFORMULA(IFERROR(VALUE(REGEXEXTRACT(' + rangeA1(satCol) + ',"^[1-5]")),""))),2),"")');
  }
  row += 1;
  const reuseCountRow = countRow(REUSE_TITLE, reuseCol, REUSE_CHOICES);
  row += 1;

  // ---- 표 6: 자유 의견 ----
  subhead('6. 자유 의견 모음(응답 번호와 함께)', 8);
  // 번호는 "빈 행을 건너뛴 응답 순서"로 붙입니다(행 내용만 지워 빈 행이 남아도 U01부터 다시 셈).
  // 분석 탭은 응답이 올 때마다 다시 만들어지므로 값으로 적어도 항상 최신입니다.
  const respRows = readResponses_().rows;
  OPEN_QUESTIONS.forEach(function (q) {
    sheet.getRange(row, 1).setValue(q).setFontWeight('bold');
    row += 1;
    const c = findCol_(headers, q);
    if (c !== -1) {
      const lines = [];
      respRows.forEach(function (r, i) {
        const v = String(r[c - 1]).trim();
        if (v) lines.push('• ' + autoId_(i + 1) + ': ' + v);
      });
      sheet.getRange(row, 1, 1, 8).merge()
        .setValue(lines.length ? lines.join('\n') : '(응답 없음)')
        .setWrap(true).setVerticalAlignment('top');
      sheet.setRowHeight(row, 80);
    } else {
      sheet.getRange(row, 1).setValue('(응답 열을 찾지 못함)');
    }
    row += 2;
  });

  // ---- 서식 ----
  sheet.setColumnWidth(1, 340);
  for (let c = 2; c <= 8; c++) sheet.setColumnWidth(c, 95);
  sheet.setFrozenRows(1);

  // ---- 차트 1: 항목별 평가 평균(막대) ----
  try {
    const chart1 = sheet.newChart()
      .setChartType(Charts.ChartType.BAR)
      .addRange(sheet.getRange(likertStartRow, 1, likertEndRow - likertStartRow + 1, 2))
      .setPosition(likertStartRow, 10, 0, 0)
      .setOption('title', '항목별 평가 평균(5점 만점)')
      .setOption('legend', { position: 'none' })
      .setOption('hAxis', { minValue: 0, maxValue: 5 })
      .setOption('colors', [COLOR_MAIN])
      .build();
    sheet.insertChart(chart1);
  } catch (e) {
    Logger.log('막대그래프 생성 실패: ' + e.message);
  }

  // ---- 차트 2: 다시 사용·추천 의향(파이) ----
  // PIE 차트는 "항목 1열 + 값 1열" 형태가 가장 안정적이라, 숨긴 Z:AA 열에 차트용 데이터를 둡니다.
  try {
    const helperStartRow = 1;
    sheet.getRange(helperStartRow, 26, 4, 2).setValues([
      ['응답', '수'], ['예', 0], ['아니오', 0], ['잘 모르겠음', 0],
    ]);
    sheet.getRange(helperStartRow + 1, 27).setFormula('=B' + reuseCountRow);
    sheet.getRange(helperStartRow + 2, 27).setFormula('=C' + reuseCountRow);
    sheet.getRange(helperStartRow + 3, 27).setFormula('=D' + reuseCountRow);
    sheet.hideColumns(26, 2);
    const chart2 = sheet.newChart()
      .setChartType(Charts.ChartType.PIE)
      .addRange(sheet.getRange(helperStartRow, 26, 4, 2))
      .setOption('title', REUSE_TITLE)
      .setOption('colors', [COLOR_MAIN, '#E07A5F', '#A8B2C1'])
      .setPosition(likertStartRow, 17, 0, 0)
      .build();
    sheet.insertChart(chart2);
  } catch (e) {
    Logger.log('파이차트 생성 실패: ' + e.message);
  }

  Logger.log('분석 탭을 다시 만들었습니다. 응답 시트: ' + respName + ' / ' + ss.getUrl());
}

// ===================== 응답 데이터 읽기(리포트용) =====================

function readResponses_() {
  const ctx = getResponseContext_();
  const lastRow = ctx.respSheet.getLastRow();
  if (lastRow < 2) return { ctx: ctx, rows: [], dates: [] };
  const rows = ctx.respSheet.getRange(2, 1, lastRow - 1, ctx.headers.length).getDisplayValues();
  const stamps = ctx.respSheet.getRange(2, 1, lastRow - 1, 1).getValues();
  const outRows = [], dates = [];
  rows.forEach(function (r, i) {
    if (String(r[0]).trim() === '') return;
    outRows.push(r);
    const t = stamps[i][0];
    dates.push(t instanceof Date ? Utilities.formatDate(t, 'Asia/Seoul', 'yyyy-MM-dd') : String(t));
  });
  return { ctx: ctx, rows: outRows, dates: dates };
}

function num_(v) {
  const m = String(v).match(/^\s*([1-5])/);
  return m ? Number(m[1]) : null;
}

function avg_(arr) {
  const a = arr.filter(function (x) { return x !== null; });
  if (!a.length) return null;
  return Math.round(a.reduce(function (s, x) { return s + x; }, 0) / a.length * 100) / 100;
}

function countBy_(values, choices) {
  const out = {};
  choices.forEach(function (c) { out[c] = 0; });
  let other = 0;
  values.forEach(function (v) {
    v = String(v).trim();
    if (!v) return;
    if (out.hasOwnProperty(v)) out[v] += 1; else other += 1;
  });
  if (other) out['기타'] = other;
  return out;
}

function fmtCounts_(obj) {
  return Object.keys(obj).filter(function (k) { return obj[k] > 0; })
    .map(function (k) { return k + ' ' + obj[k] + '명'; }).join(', ') || '(응답 없음)';
}

// ===================== 결과 리포트(구글 문서) =====================

function buildReport() {
  const data = readResponses_();
  const H = data.ctx.headers, R = data.rows, n = R.length;
  if (n === 0) throw new Error('응답이 아직 없습니다. 응답이 들어온 뒤 다시 실행해 주세요.');
  const col = function (t) { return findCol_(H, t) - 1; };
  const val = function (r, c) { return c >= 0 ? r[c] : ''; };
  const ids = R.map(function (r, i) { return autoId_(i + 1); });
  const missing = checkColumns_(H);
  if (missing.length) Logger.log('응답 시트에서 찾지 못한 문항(스크립트와 설문지 버전이 다를 수 있음):\n- ' + missing.join('\n- '));

  // 리포트 문서: 한 번 만든 문서를 재사용(내용만 새로 씀)
  const props = PropertiesService.getScriptProperties();
  let doc = null;
  const docId = props.getProperty('REPORT_DOC_ID');
  if (docId) { try { doc = DocumentApp.openById(docId); } catch (e) { doc = null; } }
  if (!doc) { doc = DocumentApp.create(REPORT_TITLE); props.setProperty('REPORT_DOC_ID', doc.getId()); }
  const body = doc.getBody();
  body.clear();

  const H1 = DocumentApp.ParagraphHeading.HEADING1, H2 = DocumentApp.ParagraphHeading.HEADING2;
  function p(text) { return body.appendParagraph(text); }
  function bullet(text) { return body.appendListItem(text).setGlyphType(DocumentApp.GlyphType.BULLET); }
  function table(rows) {
    const t = body.appendTable(rows);
    const hdr = t.getRow(0);
    for (let i = 0; i < hdr.getNumCells(); i++) {
      hdr.getCell(i).setBackgroundColor(COLOR_MAIN).editAsText().setForegroundColor('#FFFFFF').setBold(true);
    }
    return t;
  }

  body.insertParagraph(0, REPORT_TITLE).setHeading(DocumentApp.ParagraphHeading.TITLE);
  p('작성: 오이소창원 팀(조준수·이혜경·이미영) · 자동 생성일: ' +
    Utilities.formatDate(new Date(), 'Asia/Seoul', 'yyyy-MM-dd HH:mm') +
    ' · [AI 작성 예시 - 사람 검수 필요] 숫자는 설문 응답에서 자동 계산, 해석·개선 계획은 사람이 작성');

  // 1. 개요
  p('1. 테스트 개요').setHeading(H1);
  table([
    ['구분', '내용'],
    ['목적', '오이소창원 MVP가 창원 전입 청년에게 이해하기 쉽고 근거 있는 정착 안내를 주는지 확인'],
    ['방법', '실사용자가 모바일·PC에서 ' + TASKS.length + '개 과제를 직접 수행한 뒤 온라인 설문(구글 설문지) 응답'],
    ['참여자', '실사용자 ' + n + '명(응답 순서대로 자동 번호: ' + ids.join(', ') + ')'],
    ['개인정보', '이름·연락처·이메일 미수집. 응답 순서 번호(U01~)로만 구분'],
    ['기간', firstLastDate_(data.dates)],
  ]);

  // 2. 응답자 구성
  p('2. 응답자 구성').setHeading(H1);
  const prof = [['항목', '분포']];
  PROFILE_ITEMS.forEach(function (it) {
    const c = col(it[0]);
    prof.push([it[0], c < 0 ? MISSING : fmtCounts_(countBy_(R.map(function (r) { return val(r, c); }), it[1]))]);
  });
  table(prof);

  // 3. 과제 수행
  p('3. 과제 수행 결과(완료 / 부분완료 / 미완료)').setHeading(H1);
  const taskRows = [['단계', '모바일', 'PC·노트북']];
  const weakTasks = [];
  const rates = [];   // 단계별 완료율(두 기기 합산) — 완료가 가장 적은 단계를 고르기 위함
  const notDone = []; // 미완료가 있었던 단계
  TASKS.forEach(function (t, i) {
    const weakDev = [];
    const cells = [GRID_TITLE_MOBILE, GRID_TITLE_PC].map(function (g) {
      const c = findGridCol_(H, g, t) - 1;
      if (c < 0) return MISSING;
      const cnt = countBy_(R.map(function (r) { return val(r, c); }), TASK_STATUS);
      const answered = cnt['완료'] + cnt['부분완료'] + cnt['미완료'];
      if (answered === 0) return '-';
      if ((cnt['부분완료'] || 0) + (cnt['미완료'] || 0) > 0) weakDev.push(g === GRID_TITLE_MOBILE ? '모바일' : 'PC');
      if (cnt['미완료'] > 0) notDone.push((i + 1) + '단계 ' + (g === GRID_TITLE_MOBILE ? '모바일' : 'PC') + ' ' + cnt['미완료'] + '건');
      rates[i] = rates[i] || { done: 0, total: 0 };
      rates[i].done += cnt['완료']; rates[i].total += answered;
      return cnt['완료'] + ' / ' + cnt['부분완료'] + ' / ' + cnt['미완료'] + ' (' + answered + '명)';
    });
    if (weakDev.length) weakTasks.push((i + 1) + '단계(' + weakDev.join('·') + ')');
    taskRows.push([(i + 1) + '. ' + t, cells[0], cells[1]]);
  });
  table(taskRows);
  p('괄호 안은 그 기기로 수행한 응답자 수입니다. "-"는 그 기기로 수행한 응답자가 없음을 뜻합니다.');
  if (!weakTasks.length) {
    p('모든 단계를 응답자 전원이 완료했습니다.');
  } else {
    // 모든 단계에 부분완료가 섞이면 목록이 길기만 해서, 완료율이 가장 낮은 단계와 미완료만 짚습니다.
    const valid = rates.map(function (r, i) { return r && r.total ? { i: i, v: r.done / r.total, r: r } : null; })
      .filter(function (x) { return x; });
    const minV = Math.min.apply(null, valid.map(function (x) { return x.v; }));
    const lowest = valid.filter(function (x) { return x.v === minV; })
      .map(function (x) { return (x.i + 1) + '단계(완료 ' + x.r.done + '/' + x.r.total + ')'; });
    p('완료가 가장 적은 단계: ' + lowest.join(', ') + ' → 개선 우선 검토');
    p(notDone.length ? '미완료: ' + notDone.join(', ') + ' → 막힌 지점 확인' : '미완료는 없었습니다.');
  }

  // 4. 항목별 평가
  p('4. 항목별 평가(5점 만점)').setHeading(H1);
  const scores = LIKERT_ITEMS.map(function (q) {
    const c = findGridCol_(H, GRID_TITLE_LIKERT, q) - 1;
    return { q: q, a: avg_(R.map(function (r) { return num_(val(r, c)); })) };
  });
  const sc = [['문항', '평균']];
  scores.forEach(function (s) {
    const found = findGridCol_(H, GRID_TITLE_LIKERT, s.q) !== -1;
    sc.push([s.q, !found ? MISSING : (s.a === null ? '-' : s.a.toFixed(2))]);
  });
  table(sc);
  appendChartImage_(body, 0);
  const ranked = scores.filter(function (s) { return s.a !== null; }).sort(function (a, b) { return b.a - a.a; });
  if (ranked.length) {
    const top = ranked[0].a, bottom = ranked[ranked.length - 1].a;
    const names = function (v) { return ranked.filter(function (s) { return s.a === v; }).map(function (s) { return s.q; }).join(' · '); };
    bullet('가장 높은 항목: ' + names(top) + ' (' + top.toFixed(2) + '점)');
    bullet('가장 낮은 항목: ' + names(bottom) + ' (' + bottom.toFixed(2) + '점)');
    bullet('전체 문항 평균: ' + avg_(ranked.map(function (s) { return s.a; })).toFixed(2) + '점');
  }

  // 5. 기능 선호
  p('5. 기능별 선호').setHeading(H1);
  const bc = col(BEST_FEATURE_TITLE), wc = col(WORST_FEATURE_TITLE);
  const best = countBy_(R.map(function (r) { return val(r, bc); }), FEATURE_CHOICES);
  const worst = countBy_(R.map(function (r) { return val(r, wc); }), FEATURE_CHOICES);
  const fr = [['기능', '가장 유용', '가장 개선 필요']];
  FEATURE_CHOICES.forEach(function (f) {
    fr.push([f, bc < 0 ? MISSING : String(best[f] || 0), wc < 0 ? MISSING : String(worst[f] || 0)]);
  });
  table(fr);
  const alertCounts = countBy_(R.map(function (r) { return val(r, col(ALERT_TITLE)); }), ALERT_CHOICES);
  bullet('알림 방식 선호: ' + fmtCounts_(alertCounts) + ' (이메일 알림 기능 유지·보완 판단 근거)');

  // 6. 종합
  p('6. 종합 만족도').setHeading(H1);
  const satVals = R.map(function (r) { return num_(val(r, col(SCALE_TITLE))); });
  const sat = avg_(satVals);
  const satDist = countBy_(satVals.filter(function (x) { return x !== null; }).map(String), ['5', '4', '3', '2', '1']);
  const reuse = countBy_(R.map(function (r) { return val(r, col(REUSE_TITLE)); }), REUSE_CHOICES);
  bullet('전체 만족도 평균: ' + (sat === null ? '-' : sat.toFixed(2) + '점 / 5점') +
    ' (' + ['5', '4', '3', '2', '1'].filter(function (k) { return satDist[k]; })
      .map(function (k) { return k + '점 ' + satDist[k] + '명'; }).join(', ') + ')');
  bullet(REUSE_TITLE + ': ' + fmtCounts_(reuse));
  appendChartImage_(body, 1);

  // 7. 자유 의견
  p('7. 자유 의견').setHeading(H1);
  OPEN_QUESTIONS.forEach(function (q) {
    p(q).setHeading(H2);
    const c = col(q);
    let any = false;
    R.forEach(function (r, i) {
      const v = String(val(r, c)).trim();
      if (v) { bullet(ids[i] + ': ' + v); any = true; }
    });
    if (!any) p('(응답 없음)');
  });

  // 8. 개선 반영 계획(팀 작성)
  p('8. 개선 반영 계획 [직접 작성]').setHeading(H1);
  table([['발견한 문제(근거: 응답 번호·문항)', '개선 내용', '담당', '반영 여부']].concat(IMPROVEMENT_PLAN));

  // 9. 한계
  p('9. 해석 시 유의점').setHeading(H1);
  bullet('응답자가 ' + n + '명이라 통계적으로 일반화할 수 없습니다. 평균·비율은 경향을 보는 참고값입니다.');
  bullet('사용자가 만족했다고 해서 정책 자격·현재성이 검증된 것은 아닙니다(정책 정보는 공식 출처·확인일 기준).');
  bullet('사용성 결과를 지역말 뜻의 정확도로 해석하지 않습니다(지역말은 공식 사전·문헌 기준 뜻).');

  doc.saveAndClose();
  buildTeamExcelSheet_(data);
  Logger.log('리포트 초안: ' + doc.getUrl());
  Logger.log('팀 엑셀에 옮길 값: 응답 스프레드시트의 "팀엑셀_옮기기" 탭');
}

// 스크립트가 찾는 문항 제목이 응답 시트에 있는지 확인(없으면 목록으로 돌려줌)
function checkColumns_(H) {
  const miss = [];
  PROFILE_ITEMS.forEach(function (it) { if (findCol_(H, it[0]) === -1) miss.push(it[0]); });
  TASKS.forEach(function (t) {
    if (findGridCol_(H, GRID_TITLE_MOBILE, t) === -1) miss.push('[모바일] ' + t);
    if (findGridCol_(H, GRID_TITLE_PC, t) === -1) miss.push('[PC] ' + t);
  });
  LIKERT_ITEMS.forEach(function (q) { if (findGridCol_(H, GRID_TITLE_LIKERT, q) === -1) miss.push(q); });
  [BEST_FEATURE_TITLE, WORST_FEATURE_TITLE, ALERT_TITLE, SCALE_TITLE, REUSE_TITLE].concat(OPEN_QUESTIONS)
    .forEach(function (t) { if (findCol_(H, t) === -1) miss.push(t); });
  return miss;
}

// 분석 탭의 차트(0: 항목별 평균 막대, 1: 다시 사용·추천 파이)를 리포트에 그림으로 넣기. 실패해도 리포트는 계속 만듦
function appendChartImage_(body, index) {
  try {
    const ss = findExistingSpreadsheet_();
    if (!ss.getSheetByName('분석')) buildAnalysisDashboard();
    const sheet = ss.getSheetByName('분석');
    if (!sheet) return;
    const charts = sheet.getCharts();
    if (!charts[index]) return;
    const img = body.appendImage(charts[index].getAs('image/png'));
    const w = 440;
    img.setHeight(Math.round(img.getHeight() * w / img.getWidth())).setWidth(w);
  } catch (e) {
    Logger.log('리포트 그래프 넣기 실패(' + index + '): ' + e.message);
  }
}

function firstLastDate_(dates) {
  const ds = dates.filter(String).slice().sort();
  if (!ds.length) return '-';
  return ds[0] === ds[ds.length - 1] ? ds[0] : ds[0] + ' ~ ' + ds[ds.length - 1];
}

// 팀 엑셀(오이소창원_테스트_제출관리) 「사용자테스트_참여자」·「사용자테스트_설문」 시트 열 순서대로 정리
function buildTeamExcelSheet_(data) {
  const ss = data.ctx.ss, H = data.ctx.headers, R = data.rows;
  const col = function (t) { return findCol_(H, t) - 1; };
  const val = function (r, c) { return c >= 0 ? r[c] : ''; };
  const old = ss.getSheetByName('팀엑셀_옮기기');
  if (old) ss.deleteSheet(old);
  const sh = ss.insertSheet('팀엑셀_옮기기');
  const likertCols = LIKERT_ITEMS.map(function (q) { return findGridCol_(H, GRID_TITLE_LIKERT, q) - 1; });
  const trustIdx = LIKERT_ITEMS.indexOf('출처·확인일이 있어 안내를 믿을 수 있었다');

  const A = [['[사용자테스트_참여자] 참여자 코드', '연령대', '창원 거주/생활 경험', '타지역 이주 경험', '하는 일', 'AI 서비스 사용 경험', '테스트 날짜']];
  R.forEach(function (r, i) {
    A.push([autoId_(i + 1), val(r, col(AGE_TITLE)), val(r, col(LIVE_TITLE)), val(r, col(MOVE_TITLE)),
      val(r, col(JOB_TITLE)), val(r, col(AI_TITLE)), data.dates[i]]);
  });
  const B = [['[사용자테스트_설문] 참여자', '전체 만족도(1~5)', '다시 사용·추천 의향', '가장 유용한 기능', '가장 개선 필요한 기능',
    '출처/직접 확인 표시 도움(1~5)', '자유 의견', '설문 상태']];
  R.forEach(function (r, i) {
    const opin = OPEN_QUESTIONS.map(function (q) { return String(val(r, col(q))).trim(); }).filter(String).join(' / ');
    B.push([autoId_(i + 1), num_(val(r, col(SCALE_TITLE))) || '', val(r, col(REUSE_TITLE)),
      val(r, col(BEST_FEATURE_TITLE)), val(r, col(WORST_FEATURE_TITLE)),
      trustIdx >= 0 ? (num_(val(r, likertCols[trustIdx])) || '') : '', opin, '완료']);
  });
  sh.getRange(1, 1, A.length, A[0].length).setValues(A);
  sh.getRange(A.length + 2, 1, B.length, B[0].length).setValues(B);
  [1, A.length + 2].forEach(function (r0) {
    sh.getRange(r0, 1, 1, 8).setFontWeight('bold').setBackground(COLOR_SUB).setFontColor(COLOR_MAIN);
  });
  sh.setColumnWidth(1, 220);
  sh.setColumnWidth(7, 360);
}

// ===================== 응답 도착 시 처리 =====================

function installFormSubmitTrigger_(form) {
  // 분석 탭 자동 갱신을 위해 메일 알림 여부와 상관없이 트리거를 만듭니다(중복 생성 방지).
  const exists = ScriptApp.getProjectTriggers().some(function (t) {
    return t.getHandlerFunction() === 'onSurveySubmit_';
  });
  if (exists) return;
  ScriptApp.newTrigger('onSurveySubmit_').forForm(form).onFormSubmit().create();
}

function onSurveySubmit_(e) {
  try {
    // 응답 시트에 값이 반영된 직후 분석 탭을 다시 만듭니다(차트까지 확실히 갱신).
    Utilities.sleep(1500);
    SpreadsheetApp.flush();
    try {
      buildAnalysisDashboard();
    } catch (dashboardErr) {
      Logger.log('응답 후 분석 탭 자동 갱신 실패: ' + dashboardErr.message);
    }
    if (!SEND_EMAIL_NOTIFICATIONS || !NOTIFY_EMAIL) return;

    const answers = extractAnswers_(e);
    let id = '(번호 확인 불가)';
    try { id = autoId_(readResponses_().rows.length); } catch (idErr) {}  // 빈 행 제외한 응답 수
    const sat = answers[SCALE_TITLE] || '(미응답)';
    const reuse = answers[REUSE_TITLE] || '(미응답)';
    const subject = '[설문 응답 도착] 오이소창원 실사용자 테스트 — ' + id;
    const body =
      '새로운 테스트 응답이 도착했습니다.\n\n' +
      '응답 번호: ' + id + '\n' +
      '전체 만족도: ' + sat + '\n' +
      '다시 사용·추천 의향: ' + reuse + '\n\n' +
      '분석 탭이 자동으로 갱신되었습니다. 응답이 모두 오면 buildReport()를 실행해 리포트를 만드세요.';
    MailApp.sendEmail(NOTIFY_EMAIL, subject, body);
  } catch (err) {
    Logger.log('응답 처리 중 오류: ' + err.message);
  }
}

// 폼 제출 이벤트(e)에서 "문항 제목 → 응답값"을 뽑아내는 함수.
// 이 트리거는 forForm(form)으로 "설문지에" 연결되어 있어 e.response(FormResponse)가 들어옵니다.
// (e.namedValues는 트리거를 스프레드시트에 연결했을 때만 채워집니다.)
function extractAnswers_(e) {
  const out = {};
  if (e && e.response) {
    e.response.getItemResponses().forEach(function (ir) {
      out[ir.getItem().getTitle()] = ir.getResponse();
    });
  } else if (e && e.namedValues) {
    // 나중에 트리거를 스프레드시트 쪽으로 바꾸더라도 계속 동작하도록 남겨 둔 대비용 경로
    Object.keys(e.namedValues).forEach(function (key) {
      const v = e.namedValues[key];
      out[key] = Array.isArray(v) ? v[0] : v;
    });
  }
  return out;
}
