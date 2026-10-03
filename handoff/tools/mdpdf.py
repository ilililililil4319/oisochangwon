import sys, os, asyncio, markdown
from playwright.async_api import async_playwright
md, pdf, footer = sys.argv[1], sys.argv[2], sys.argv[3]
landscape = len(sys.argv) > 4 and sys.argv[4] == 'landscape'
body = markdown.markdown(open(md, encoding='utf-8').read(), extensions=['tables'])
css = """body{font-family:'Noto Sans CJK KR',sans-serif;font-size:9.6pt;color:#1d2733;line-height:1.55}
h1{font-size:18pt;color:#063465;border-bottom:3px solid #FE6A01;padding-bottom:6px;margin:0 0 8px}
h2{font-size:12.5pt;color:#fff;background:#063465;padding:4px 10px;margin:16px 0 6px;break-after:avoid}
h3{font-size:11pt;color:#063465;border-left:4px solid #2E9E6B;padding-left:7px;margin:12px 0 5px;break-after:avoid}
table{border-collapse:collapse;width:100%;margin:4px 0 8px}th,td{border:1px solid #C9D3DF;padding:4px 7px;vertical-align:top}
th{background:#EEF4FB;color:#063465;text-align:left}tr{break-inside:avoid}p{margin:4px 0}ul,ol{padding-left:20px;margin:4px 0}
img{max-width:100%;display:block;margin:6px auto}code{font-size:.92em;background:#F3F5F8;padding:0 3px;border-radius:3px}a{color:#063465;word-break:break-all}"""
tmp = os.path.join(os.path.dirname(os.path.abspath(md)), '_tmp_render.html')
open(tmp, 'w', encoding='utf-8').write(f"<!doctype html><html lang=ko><meta charset=utf-8><style>{css}</style><body>{body}</body></html>")
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(); pg = await b.new_page()
        await pg.goto('file://' + tmp); await pg.wait_for_timeout(500)
        await pg.pdf(path=pdf, format='A4', landscape=landscape, print_background=True, display_header_footer=True,
            header_template='<span></span>',
            footer_template=f'<div style="font-size:7pt;color:#5b6775;width:100%;text-align:center">{footer} · <span class=pageNumber></span>/<span class=totalPages></span></div>',
            margin={'top':'14mm','bottom':'15mm','left':'13mm','right':'13mm'})
        await b.close()
asyncio.run(main()); os.remove(tmp)
