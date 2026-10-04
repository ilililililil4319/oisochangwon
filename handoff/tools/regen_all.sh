#!/bin/bash
# 모든 제출·공유 문서를 같은 규칙(표 정렬·쪽 번호·여백)으로 다시 만들기
cd "$(dirname "$0")/../.."
export NODE_PATH=$(npm root -g)
T=handoff/tools
while IFS='|' read -r md title docx; do
  [ -z "$md" ] && continue
  pdf="${md%.md}.pdf"
  (cd "$(dirname "$md")" && python3 "$OLDPWD/$T/mdpdf.py" "$(basename "$md")" "$(basename "$pdf")" "$title") >/dev/null 2>&1
  pages=$(python3 -c "from pypdf import PdfReader;print(len(PdfReader('$pdf').pages))")
  if [ "$docx" = "y" ]; then
    if [ "$pages" = "1" ]; then NOPAGE=1 node $T/md2docx3.js "$md" "${md%.md}.docx" "$title"; else node $T/md2docx3.js "$md" "${md%.md}.docx" "$title"; fi
  fi
  echo "$pages쪽  $pdf"
done <<'LIST'
docs/planning/오이소창원_기획안_최종본_20261004.md|오이소창원 기획안|y
deliverables/final_report/오이소창원_개발완료보고서_20261004.md|오이소창원 개발완료보고서|y
deliverables/submission/오이소창원_출처_AI활용_신고서_20261004.md|오이소창원 출처·AI 활용 신고서|y
deliverables/presentation/video/오이소창원_시연영상_스크립트_20261004.md|오이소창원 시연영상 스크립트|y
tests/team_self_test/오이소창원_체크리스트_서류양식.md|오이소창원 체크리스트 서류 양식|y
handoff/오이소창원_작업지시인계서_20261004.md|오이소창원 작업지시·인계서 20261004|n
LIST
