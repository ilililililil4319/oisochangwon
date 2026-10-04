const fs=require('fs');
const path=require('path');
const {ImageRun,Document,Packer,Paragraph,TextRun,Table,TableRow,TableCell,WidthType,ShadingType,HeadingLevel,AlignmentType,BorderStyle,ExternalHyperlink,Footer,PageNumber,HorizontalPositionRelativeFrom,HorizontalPositionAlign,VerticalPositionRelativeFrom,VerticalPositionAlign,TextWrappingType,TextWrappingSide}=require('docx');
// QR=그림 경로 → 제목 줄 오른쪽 위에 앱 QR을 띄워 넣음 (10/4)
const QR=process.env.QR?fs.readFileSync(process.env.QR):null;
let qrDone=false;
const md=fs.readFileSync(process.argv[2],'utf8').split('\n');
const FONT='Malgun Gothic', NAVY='063465', ORANGE='FE6A01';
const PAGEW=11906-2*851; // A4 width minus 15mm margins
function runs(text,opts={}){
  const out=[]; const re=/\*\*(.+?)\*\*|(https?:\/\/[^\s)|]+)/g; let last=0,m;
  while((m=re.exec(text))){ if(m.index>last) out.push(new TextRun({text:text.slice(last,m.index),font:FONT,...opts}));
    if(m[1]!==undefined) out.push(new TextRun({text:m[1],bold:true,font:FONT,...opts}));
    else out.push(new ExternalHyperlink({link:m[2],children:[new TextRun({text:m[2],style:'Hyperlink',font:FONT,...opts})]}));
    last=re.lastIndex;}
  if(last<text.length) out.push(new TextRun({text:text.slice(last).replace(/`/g,''),font:FONT,...opts}));
  return out.map(r=>r instanceof TextRun? r : r);
}
function clean(t){return t.replace(/`/g,'');}
const children=[];
let i=0;
// 짧은 칸(항목·숫자·영문, 14자 이하)은 글자 수만큼 폭을 주고 한 줄·가운데, 나머지 폭은 긴 칸이 나눠 씀
function shortCols(n,rows){const mx=Array(n).fill(0);rows.slice(1).forEach(r=>r.forEach((c,i)=>{mx[i]=Math.max(mx[i],clean(c).replace(/\*\*/g,'').length)}));return mx.map(m=>m<=14&&n>1);}
function widthsFor(n,rows){
  const sh=shortCols(n,rows); const CH=200, PAD=260; const w=Array(n).fill(0);
  rows.forEach(r=>r.forEach((c,i)=>{const len=clean(c).replace(/\*\*/g,'').length; if(sh[i]) w[i]=Math.max(w[i],len*CH+PAD);}));
  const fixed=w.reduce((a,b)=>a+b,0); const longIdx=[...Array(n).keys()].filter(i=>!sh[i]);
  if(!longIdx.length){const t=fixed;return w.map(x=>x/t);}
  const L=longIdx.map(i=>Math.sqrt(rows.reduce((a,r)=>a+Math.min((r[i]||'').length,120),0)/rows.length)+2);
  const rest=Math.max(PAGEW-fixed,PAGEW*0.35); const sL=L.reduce((a,b)=>a+b,0);
  longIdx.forEach((i,k)=>{w[i]=rest*L[k]/sL}); const tot=w.reduce((a,b)=>a+b,0); return w.map(x=>x/tot);
}
while(i<md.length){
  const line=md[i];
  if(line.startsWith('|')){
    const rows=[]; let al=[]; while(i<md.length&&md[i].startsWith('|')){ if(!/^\|[-|: ]+\|$/.test(md[i])) rows.push(md[i].slice(1,-1).split('|').map(c=>c.trim())); else al=md[i].slice(1,-1).split('|').map(c=>/^\s*:-+:\s*$/.test(c)); i++; }
    const n=rows[0].length; const sh=shortCols(n,rows); const w=widthsFor(n,rows).map(x=>Math.round(x*PAGEW)); w[n-1]=PAGEW-w.slice(0,n-1).reduce((a,b)=>a+b,0);
    const border={style:BorderStyle.SINGLE,size:4,color:'C9D3DF'};
    children.push(new Table({width:{size:PAGEW,type:WidthType.DXA},columnWidths:w,rows:rows.map((r,ri)=>new TableRow({tableHeader:ri===0,cantSplit:true,children:r.map((c,ci)=>new TableCell({width:{size:w[ci],type:WidthType.DXA},
      borders:{top:border,bottom:border,left:border,right:border},
      shading: ri===0?{type:ShadingType.CLEAR,color:'auto',fill:'EEF4FB'}:undefined,
      margins:{top:50,bottom:50,left:80,right:80},
      children:[new Paragraph({alignment:(ri===0||sh[ci]||al[ci]||(c===''))?AlignmentType.CENTER:AlignmentType.LEFT,children:runs(clean(c),{size:17,bold:ri===0||undefined,color:ri===0?NAVY:undefined})})]}))}))}));
    children.push(new Paragraph({spacing:{after:80},children:[]}));
    continue;
  }
  if(line.startsWith('```')){ i++; const code=[]; while(i<md.length && !md[i].startsWith('```')){code.push(md[i]); i++;} i++;
    code.forEach(c=>children.push(new Paragraph({spacing:{after:0},shading:{type:ShadingType.CLEAR,color:'auto',fill:'F3F5F8'},children:[new TextRun({text:c||' ',font:'Consolas',size:15})]})));
    children.push(new Paragraph({spacing:{after:80},children:[]})); continue; }
  const img=line.match(/^!\[[^\]]*\]\(([^)]+)\)/);
  if(img){ const fp=path.join(path.dirname(process.argv[2]),img[1]); const buf=fs.readFileSync(fp);
    const w=buf.readUInt32BE(16), h=buf.readUInt32BE(20); const W=640, H=Math.round(h*W/w);
    children.push(new Paragraph({alignment:AlignmentType.CENTER,children:[new ImageRun({type:'png',data:buf,transformation:{width:W,height:H}})]})); i++; continue; }
  if(line.startsWith('### ')) children.push(new Paragraph({heading:HeadingLevel.HEADING_2,spacing:{before:160,after:60},keepNext:true,children:[new TextRun({text:line.slice(4),bold:true,size:21,color:'2E9E6B',font:FONT})]}));
  else if(line.startsWith('# ')){ const kids=[new TextRun({text:line.slice(2),bold:true,size:34,color:NAVY,font:FONT})];
    if(QR&&!qrDone){ qrDone=true; const qw=QR.readUInt32BE(16), qh=QR.readUInt32BE(20); const QW=96;
      kids.push(new ImageRun({type:'png',data:QR,transformation:{width:QW,height:Math.round(qh*QW/qw)},floating:{
        horizontalPosition:{relative:HorizontalPositionRelativeFrom.MARGIN,align:HorizontalPositionAlign.RIGHT},
        verticalPosition:{relative:VerticalPositionRelativeFrom.MARGIN,align:VerticalPositionAlign.TOP},
        wrap:{type:TextWrappingType.SQUARE,side:TextWrappingSide.LEFT},margins:{left:114300}}}));}
    children.push(new Paragraph({heading:HeadingLevel.TITLE,spacing:{after:120},border:{bottom:{style:BorderStyle.SINGLE,size:12,color:ORANGE,space:4}},children:kids})); }
  else if(line.startsWith('## ')) children.push(new Paragraph({heading:HeadingLevel.HEADING_1,spacing:{before:220,after:80},keepNext:true,children:[new TextRun({text:line.slice(3),bold:true,size:24,color:NAVY,font:FONT})]}));
  else if(line.startsWith('- ')) children.push(new Paragraph({numbering:{reference:'b',level:0},spacing:{after:40},children:runs(clean(line.slice(2)),{size:19})}));
  else if(line.trim()==='---') children.push(new Paragraph({border:{bottom:{style:BorderStyle.SINGLE,size:6,color:'D5DDE7',space:1}},spacing:{after:100},children:[]}));
  else if(line.trim()) children.push(new Paragraph({spacing:{after:60},children:runs(clean(line),{size:19})}));
  i++;
}
// wordWrap: 한글을 글자 단위가 아니라 어절(띄어쓰기) 단위로 줄바꿈 — 낱말 중간 끊김 방지 (10/4)
const doc=new Document({styles:{default:{document:{run:{font:FONT,size:19},paragraph:{wordWrap:true}}}},
  numbering:{config:[{reference:'b',levels:[{level:0,format:'bullet',text:'•',alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:360,hanging:240}}}}]}]},
  sections:[{properties:{page:{margin:{top:851,bottom:851,left:851,right:851}}},
    footers:{default:new Footer({children:[new Paragraph({alignment:AlignmentType.CENTER,children:[...(process.env.NOPAGE?[]:[new TextRun({text:(process.argv[4]||'')+' · ',size:16,color:'5B6775',font:FONT}),new TextRun({children:[PageNumber.CURRENT,' / ',PageNumber.TOTAL_PAGES],size:16,color:'5B6775'})])]})]})},
    children}]});
Packer.toBuffer(doc).then(b=>fs.writeFileSync(process.argv[3],b));
