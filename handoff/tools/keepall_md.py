"""GitHub README 한글 낱말 중간 끊김 방지 (10/4).
GitHub 화면은 한글을 글자 단위로 줄바꿈해서 '지정주/제'처럼 끊긴다. 붙어 있는 한글 글자 사이에
보이지 않는 단어 결합 문자(U+2060)를 넣어 띄어쓰기에서만 줄이 바뀌게 한다.
제목(#)·코드·링크 주소·HTML 태그·`파일명`에는 넣지 않는다(목차 링크·복사용 경로 유지).
사용: python keepall_md.py README.md ...        (넣기)
      python keepall_md.py --strip README.md ...  (빼기 — 문서를 고치기 전에)"""
import re, sys
WJ = "⁠"
HANGUL = "가-힣"
PAIR = re.compile(f"(?<=[{HANGUL}])(?=[{HANGUL}])")
# 건드리지 않을 부분: 인라인 코드, 링크/그림 주소, HTML 태그, URL
PROTECT = re.compile(r"(`[^`]*`|\]\([^)]*\)|<[^>]+>|https?://\S+)")

def join_line(line):
    parts = PROTECT.split(line)
    return "".join(p if i % 2 else PAIR.sub(WJ, p) for i, p in enumerate(parts))

def process(text):
    out, fence = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence; out.append(line); continue
        if fence or line.lstrip().startswith("#"):
            out.append(line); continue
        out.append(join_line(line))
    return "\n".join(out)

args = sys.argv[1:]
strip = args and args[0] == "--strip"
for path in args[1:] if strip else args:
    s = open(path, encoding="utf-8").read().replace(WJ, "")
    if not strip:
        s = process(s)
    open(path, "w", encoding="utf-8").write(s)
    print(("strip " if strip else "keep-all ") + path)
