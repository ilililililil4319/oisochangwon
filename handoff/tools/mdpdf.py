"""md → A4 PDF. 표: 짧은 칸(항목·숫자·영문)은 가운데·한 줄, 긴 내용은 왼쪽. 2쪽 이상일 때만 쪽 번호."""
import sys, os, asyncio, markdown
from playwright.async_api import async_playwright
md, pdf, footer = sys.argv[1], sys.argv[2], sys.argv[3]
landscape = len(sys.argv) > 4 and sys.argv[4] == 'landscape'
body = markdown.markdown(open(md, encoding='utf-8').read(), extensions=['tables'])
css = """body{font-family:'Noto Sans CJK KR',sans-serif;font-size:9.6pt;color:#1d2733;line-height:1.55;word-break:keep-all;overflow-wrap:break-word}
h1{font-size:18pt;color:#063465;border-bottom:3px solid #FE6A01;padding-bottom:6px;margin:0 0 8px}
h2{font-size:12.5pt;color:#fff;background:#063465;padding:4px 10px;margin:14px 0 6px;break-after:avoid}
h3{font-size:11pt;color:#063465;border-left:4px solid #2E9E6B;padding-left:7px;margin:10px 0 5px;break-after:avoid}
table{border-collapse:collapse;width:100%;margin:4px 0 8px;table-layout:auto}th,td{border:1px solid #C9D3DF;padding:4px 7px;vertical-align:middle;word-break:keep-all}
th{background:#EEF4FB;color:#063465;text-align:center !important;white-space:nowrap}
td.short{text-align:center !important;white-space:nowrap}td.long{text-align:left !important}
tr{break-inside:avoid}p{margin:4px 0}ul,ol{padding-left:20px;margin:4px 0}
img{max-width:100%;display:block;margin:6px auto;break-inside:avoid}code{font-size:.92em;background:#F3F5F8;padding:0 3px;border-radius:3px}a{color:#063465;word-break:break-all}"""
script = """<script>
document.querySelectorAll('table').forEach(t=>{const rows=[...t.rows];if(!rows.length)return;
 const n=rows[0].cells.length;for(let c=0;c<n;c++){let mx=0;rows.slice(1).forEach(r=>{const x=r.cells[c];if(x)mx=Math.max(mx,x.innerText.trim().length)});
  const head=(rows[0].cells[c]||{innerText:''}).innerText.trim().length;
  rows.slice(1).forEach(r=>{const x=r.cells[c];if(!x)return;x.classList.add((mx<=14&&n>1)?'short':'long')});}});
</script>"""
# QR=그림 경로 → 첫 쪽 오른쪽 위에 앱 QR(심사 중 바로 접속) (10/4)
qr = os.environ.get('QR')
if qr:
    import base64
    data = base64.b64encode(open(qr, 'rb').read()).decode()
    css += ("body{position:relative}.qr{position:absolute;top:0;right:0;width:26mm}.qr img{width:26mm;margin:0}"
            "h1:first-of-type{padding-right:30mm}h1:first-of-type+p{padding-right:30mm;min-height:20mm}")
    body = f'<div class="qr"><img src="data:image/png;base64,{data}" alt="앱 QR"></div>' + body
tmp = os.path.join(os.path.dirname(os.path.abspath(md)), '_tmp_render.html')
open(tmp, 'w', encoding='utf-8').write(f"<!doctype html><html lang=ko><meta charset=utf-8><style>{css}</style><body>{body}{script}</body></html>")
MARGIN = {'top': '14mm', 'bottom': '15mm', 'left': '13mm', 'right': '13mm'}
async def render(pg, with_number, scale=1.0):
    foot = (f'<div style="font-size:7pt;color:#5b6775;width:100%;text-align:center">{footer} · '
            '<span class=pageNumber></span> / <span class=totalPages></span></div>') if with_number else '<span></span>'
    await pg.pdf(path=pdf, format='A4', landscape=landscape, print_background=True, display_header_footer=True,
                 header_template='<span></span>', footer_template=foot, margin=MARGIN, scale=scale)
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page()
        await pg.goto('file://' + tmp); await pg.wait_for_timeout(500)
        from pypdf import PdfReader
        count = lambda: len(PdfReader(pdf).pages)
        await render(pg, True); n = count(); best = 1.0
        # 마지막 쪽에 몇 줄만 남아 빈 공간이 커지면 글자를 조금(최대 11%) 줄여 한 쪽을 줄여 봄
        for s in (0.96, 0.92, 0.89):
            await render(pg, True, s)
            if count() < n: best = s; break
        await render(pg, True, best)
        if count() == 1:  # 1장짜리는 쪽 번호 없이
            await render(pg, False, best)
        await b.close()
asyncio.run(main()); os.remove(tmp)
