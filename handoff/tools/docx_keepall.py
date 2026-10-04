"""이미 있는 .docx에 '한글 어절 단위 줄바꿈'(w:wordWrap=0)을 기본 문단 설정으로 넣어 낱말 중간 끊김을 막음 (10/4)."""
import sys, zipfile, shutil, re, os
for path in sys.argv[1:]:
    tmp = path + ".tmp"
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/styles.xml":
                xml = data.decode("utf-8")
                if "<w:wordWrap" not in xml.split("</w:docDefaults>")[0]:
                    if "<w:pPrDefault>" in xml and "<w:pPrDefault><w:pPr>" in xml:
                        xml = xml.replace("<w:pPrDefault><w:pPr>", '<w:pPrDefault><w:pPr><w:wordWrap w:val="0"/>', 1)
                    elif re.search(r"<w:pPrDefault>\s*<w:pPr>", xml):
                        xml = re.sub(r"(<w:pPrDefault>\s*<w:pPr>)", r'\1<w:wordWrap w:val="0"/>', xml, count=1)
                    elif "<w:pPrDefault/>" in xml:
                        xml = xml.replace("<w:pPrDefault/>", '<w:pPrDefault><w:pPr><w:wordWrap w:val="0"/></w:pPr></w:pPrDefault>', 1)
                    elif "</w:rPrDefault>" in xml:
                        xml = xml.replace("</w:rPrDefault>", '</w:rPrDefault><w:pPrDefault><w:pPr><w:wordWrap w:val="0"/></w:pPr></w:pPrDefault>', 1)
                # 문단마다 wordWrap을 켠(글자 단위) 설정이 있으면 없앰
                data = xml.encode("utf-8")
            if item.filename == "word/document.xml":
                xml = data.decode("utf-8")
                xml = re.sub(r'<w:wordWrap(?: w:val="(?:1|true|on)")?/>', "", xml)
                data = xml.encode("utf-8")
            zout.writestr(item, data)
    shutil.move(tmp, path)
    print("ok", path)
