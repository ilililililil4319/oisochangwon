"""각 쪽(마지막 쪽 제외)의 아래쪽 빈 공간 비율을 잰다. 25%를 넘으면 표시."""
import sys, subprocess, tempfile, os
from PIL import Image
for pdf in sys.argv[1:]:
    d = tempfile.mkdtemp()
    subprocess.run(["pdftoppm", "-r", "30", "-png", pdf, f"{d}/p"], check=True)
    files = sorted(os.listdir(d)); out = []
    for k, fn in enumerate(files):
        im = Image.open(f"{d}/{fn}").convert("L"); W, H = im.size
        top, bottom = int(H * 14 / 297), int(H * (1 - 15 / 297))  # 본문 영역
        last = top
        for y in range(top, bottom):
            if min(im.getpixel((x, y)) for x in range(0, W, 2)) < 235: last = y
        blank = (bottom - last) / (bottom - top)
        out.append(f"{k+1}:{blank:.0%}" + ("!" if blank > .25 and k < len(files) - 1 else ""))
    print(os.path.basename(pdf), " ".join(out))
