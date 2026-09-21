/* =========================================================================
   maiReport · 문서 보드 생성기
   JSON(제목 · 장 · 블록)을 읽어 Figma 오토 레이아웃 프레임으로 만든다.
   지원 블록: h3 · p · bullets · table · callout · formula · tiles · cards · steps
   모든 텍스트는 높이 자동(HEIGHT) · 가로 채움(FILL)이라 내용을 고치면 표와 카드가 따라 늘어난다.
   ========================================================================= */

const C = {
  bg:'#F5F7FB', card:'#FFFFFF', line:'#E6EAF2', ink1:'#1A2233', ink2:'#4B5468', ink3:'#8892A6',
  acc:'#2F66F5', accL:'#EAF0FF', accDeep:'#2A3A6B', thead:'#EEF2F8', zebra:'#FAFBFD',
  code:'#0F1830', codeTx:'#DBE6FF', codeCm:'#8FA3D6', risk:'#FDEEF1', riskTx:'#7A1C33', riskLine:'#E8365D',
  warn:'#FFF6E8', warnTx:'#6B4C0F', warnLine:'#D98A12', mini:'#FAFBFD'
};
const R = { page:0, hero:34, card:26, table:8, mini:14, tile:22, code:14, callout:12, step:14 };
const S = { pad:36, gap:22, blockGap:14, cardPad:36 };
let FONT = 'Noto Sans KR';
let MONO = 'Roboto Mono';
const WEIGHTS = { 400:'Regular', 500:'Medium', 700:'Bold', 800:'Black' };
let created = 0;

// ---------- 유틸 ----------
function rgb(hex){ const h=hex.replace('#',''); return { r:parseInt(h.slice(0,2),16)/255, g:parseInt(h.slice(2,4),16)/255, b:parseInt(h.slice(4,6),16)/255 }; }
const solid = hex => [{ type:'SOLID', color:rgb(hex) }];
function style(weight){ return { family:FONT, style:WEIGHTS[weight] || 'Regular' }; }

async function loadFonts(){
  const candidates = ['Noto Sans KR', 'Pretendard', 'Inter'];
  for(const family of candidates){
    try{
      for(const st of ['Regular','Medium','Bold','Black']) await figma.loadFontAsync({ family, style:st });
      FONT = family; break;
    }catch(e){ /* 다음 후보 */ }
  }
  if(FONT !== 'Noto Sans KR' && FONT !== 'Pretendard' && FONT !== 'Inter'){ await figma.loadFontAsync({ family:'Inter', style:'Regular' }); FONT='Inter'; }
  try{ await figma.loadFontAsync({ family:'Roboto Mono', style:'Regular' }); }catch(e){ MONO = FONT; }
}

function frame(name, dir, opts={}){
  const f = figma.createFrame(); created++;
  f.name = name;
  f.layoutMode = dir;                       // 'VERTICAL' | 'HORIZONTAL'
  f.primaryAxisSizingMode = 'AUTO';
  f.counterAxisSizingMode = 'AUTO';
  f.itemSpacing = opts.gap != null ? opts.gap : 0;
  f.paddingTop = f.paddingBottom = opts.py != null ? opts.py : 0;
  f.paddingLeft = f.paddingRight = opts.px != null ? opts.px : 0;
  f.fills = opts.fill ? solid(opts.fill) : [];
  if(opts.stroke){ f.strokes = solid(opts.stroke); f.strokeWeight = opts.sw || 1; }
  if(opts.radius){ f.cornerRadius = opts.radius; }
  f.clipsContent = false;
  if(opts.align) f.counterAxisAlignItems = opts.align;   // 'MIN' | 'CENTER' | 'MAX'
  return f;
}
function fill(node){ node.layoutSizingHorizontal = 'FILL'; }   // 부모 가로 채움(부모에 append 후 호출)
function hug(node){ node.layoutSizingHorizontal = 'HUG'; node.layoutSizingVertical = 'HUG'; }

function text(str, size, color, weight=400, opts={}){
  const t = figma.createText(); created++;
  t.fontName = style(weight);
  t.characters = String(str == null ? '' : str);
  t.fontSize = size;
  t.fills = solid(color);
  t.lineHeight = { value: (opts.lh || 1.6)*100, unit:'PERCENT' };
  t.textAutoResize = 'HEIGHT';
  if(opts.mono){ t.fontName = { family:MONO, style:'Regular' }; }
  if(opts.align) t.textAlignHorizontal = opts.align;
  return t;
}
function addText(parent, str, size, color, weight, opts){ const t = text(str,size,color,weight,opts); parent.appendChild(t); fill(t); return t; }

// ---------- 블록 ----------
function blockH3(parent, b){ const t = addText(parent, b.text, 17, C.ink1, 700, {lh:1.4}); t.name='h3'; }
function blockP(parent, b){ addText(parent, b.text, b.muted ? 13 : 14.5, b.muted ? C.ink3 : C.ink2, 400); }
function blockBullets(parent, b){
  const list = frame('bullets','VERTICAL',{gap:6}); parent.appendChild(list); fill(list);
  for(const it of b.items){
    const row = frame('bullet','HORIZONTAL',{gap:8, align:'MIN'}); list.appendChild(row); fill(row);
    const dot = text('•', 14, C.acc, 700); row.appendChild(dot); dot.textAutoResize='WIDTH_AND_HEIGHT';
    addText(row, it, 14, C.ink2, 400);
  }
}
function blockCallout(parent, b){
  const tone = b.tone==='risk' ? {bg:C.risk, tx:C.riskTx, line:C.riskLine} : b.tone==='warn' ? {bg:C.warn, tx:C.warnTx, line:C.warnLine} : {bg:C.accL, tx:C.accDeep, line:C.acc};
  const box = frame('callout','HORIZONTAL',{gap:0, fill:tone.bg, radius:R.callout}); parent.appendChild(box); fill(box);
  const bar = figma.createRectangle(); created++; bar.resize(4, 10); bar.fills = solid(tone.line); box.appendChild(bar); bar.layoutSizingVertical='FILL';
  const inner = frame('text','VERTICAL',{px:18, py:14}); box.appendChild(inner); fill(inner);
  addText(inner, b.text, 13.5, tone.tx, 500);
}
function blockFormula(parent, b){
  const box = frame('formula','VERTICAL',{gap:4, px:22, py:16, fill:C.code, radius:R.code}); parent.appendChild(box); fill(box);
  for(const ln of b.lines){
    const isCm = String(ln).trim().startsWith('//');
    addText(box, ln === '' ? ' ' : ln, 13.5, isCm ? C.codeCm : C.codeTx, 400, {mono:true, lh:1.7});
  }
}
function tableWidths(cols, contentWidth){
  // cols: 숫자(px 고정) | null(남는 폭을 균등 분배) | 전부 숫자면 비율로 해석
  const n = cols.length;
  const allNum = cols.every(c => typeof c === 'number');
  if(allNum){
    const sum = cols.reduce((a,c)=>a+c,0);
    // px 합이 콘텐츠 폭보다 작으면 비율로 늘리고, 크면 줄인다 → 항상 카드 안에 맞춘다
    return cols.map(c => Math.floor(contentWidth * c / sum));
  }
  const fixed = cols.filter(c => typeof c === 'number').reduce((a,c)=>a+c,0);
  const flexN = cols.filter(c => c == null).length;
  let scale = 1;
  if(fixed > contentWidth * 0.7){ scale = (contentWidth * 0.7) / fixed; }     // 고정 열이 너무 넓으면 축소해 유동 열 자리를 남긴다
  const fixedScaled = fixed * scale;
  const flexW = Math.max(120, Math.floor((contentWidth - fixedScaled) / Math.max(1, flexN)));
  const w = cols.map(c => c == null ? flexW : Math.floor(c * scale));
  // 반올림 오차는 마지막 열에서 흡수
  const diff = contentWidth - w.reduce((a,c)=>a+c,0); w[n-1] += diff;
  return w;
}
function cellText(cell){ return (cell && typeof cell === 'object') ? cell.text : cell; }
function cellSpan(cell){ return (cell && typeof cell === 'object' && cell.span) ? cell.span : 1; }

function blockTable(parent, b, contentWidth){
  const ncol = Math.max(...b.rows.map(r => r.reduce((a,c)=>a+cellSpan(c),0)));
  let cols = (b.cols && b.cols.length) ? b.cols.slice() : Array(ncol).fill(null);
  while(cols.length < ncol) cols.push(null);
  const widths = tableWidths(cols, contentWidth);
  const tbl = frame('table','VERTICAL',{gap:0, radius:R.table}); parent.appendChild(tbl); fill(tbl);
  tbl.clipsContent = true;
  tbl.strokes = solid(C.line); tbl.strokeWeight = 1; tbl.strokeAlign = 'INSIDE';
  b.rows.forEach((row, ri) => {
    const isHead = ri===0;
    // 행: 가로 오토 레이아웃. 셀은 세로 방향 FILL로 행 높이만큼 늘어나 배경·세로선이 끊기지 않는다
    const tr = frame(isHead ? 'thead' : `row ${ri}`, 'HORIZONTAL', {gap:0, align:'MIN', fill: isHead ? C.thead : (ri%2===0 ? C.zebra : C.card)});
    tbl.appendChild(tr); fill(tr);
    if(ri > 0){ tr.strokes = solid(C.line); tr.strokeWeight = 1; tr.strokeAlign='INSIDE'; tr.strokeTopWeight = 1; tr.strokeBottomWeight = 0; tr.strokeLeftWeight = 0; tr.strokeRightWeight = 0; }
    let col = 0;
    row.forEach((cell) => {
      const span = cellSpan(cell);
      const w = widths.slice(col, col+span).reduce((a,c)=>a+c,0);
      const td = frame('cell','VERTICAL',{px:10, py:9}); tr.appendChild(td);
      td.layoutSizingHorizontal = 'FIXED'; td.resize(Math.max(40, w), 10);
      if(col > 0){ td.strokes = solid(C.line); td.strokeWeight = 1; td.strokeAlign='INSIDE'; td.strokeLeftWeight = 1; td.strokeTopWeight = 0; td.strokeBottomWeight = 0; td.strokeRightWeight = 0; }
      const color = isHead ? C.ink3 : (col===0 ? C.ink1 : C.ink2);
      const weight = (isHead || col===0) ? 700 : 400;
      addText(td, cellText(cell), 13, color, weight, {lh:1.5});
      try { td.layoutSizingVertical = 'FILL'; } catch(e){ td.layoutSizingVertical = 'HUG'; }
      col += span;
    });
  });
}
function blockTiles(parent, b, contentWidth){
  const n = b.items.length; const gap = 16; const w = Math.floor((contentWidth - gap*(n-1)) / n);
  const row = frame('tiles','HORIZONTAL',{gap, align:'MIN'}); parent.appendChild(row); fill(row);
  for(const it of b.items){
    const tile = frame(it.name || 'tile','VERTICAL',{gap:8, px:26, py:26, fill:it.fill || C.mini, stroke:it.stroke || C.line, radius:R.tile});
    row.appendChild(tile); tile.layoutSizingHorizontal='FIXED'; tile.resize(w, 10); tile.layoutSizingVertical='HUG';
    if(it.tag) addText(tile, it.tag, 12.5, it.tagColor || C.acc, 700);
    if(it.name) addText(tile, it.name, 24, it.nameColor || C.ink1, 800, {lh:1.3});
    if(it.q) addText(tile, it.q, 15, C.ink2, 400);
    if(it.small) addText(tile, it.small, 13, C.ink3, 400);
  }
}
function blockCards(parent, b, contentWidth){      // 2열 미니카드(라벨 + 본문)
  const cols = b.columns || 2; const gap = 16; const w = Math.floor((contentWidth - gap*(cols-1)) / cols);
  let row = null; let rowCards = []; const rows = [];
  b.items.forEach((it, i) => {
    if(i % cols === 0){ row = frame('cards row','HORIZONTAL',{gap, align:'MIN'}); parent.appendChild(row); fill(row); rowCards = []; rows.push(rowCards); }
    const card = frame(it.label || 'card','VERTICAL',{gap:6, px:18, py:16, fill:C.mini, stroke:C.line, radius:R.mini});
    row.appendChild(card); card.layoutSizingHorizontal='FIXED'; card.resize(w, 10); card.layoutSizingVertical='HUG';
    if(it.label) addText(card, it.label, 12.5, C.acc, 700);
    addText(card, it.text, 13.5, C.ink2, 400);
    rowCards.push(card);
  });
  for(const rc of rows) equalizeHeights(rc, w);
}
function blockSteps(parent, b, contentWidth){      // 가로 흐름(번호 · 제목 · 설명)
  const n = b.items.length; const gap = 14; const w = Math.floor((contentWidth - gap*(n-1)) / n);
  const row = frame('steps','HORIZONTAL',{gap, align:'MIN'}); parent.appendChild(row); fill(row);
  const cards = [];
  b.items.forEach((it, i) => {
    const st = frame(it.title || `step ${i+1}`,'VERTICAL',{gap:4, px:16, py:14, fill:C.mini, stroke:C.line, radius:R.step});
    row.appendChild(st); st.layoutSizingHorizontal='FIXED'; st.resize(w, 10); st.layoutSizingVertical='HUG';
    if(it.num) addText(st, it.num, 11, C.acc, 800);
    if(it.title) addText(st, it.title, 15, C.ink1, 700, {lh:1.4});
    if(it.text) addText(st, it.text, 12.5, C.ink3, 400, {lh:1.5});
    cards.push(st);
  });
  equalizeHeights(cards, w);
}
// 가로로 늘어선 카드들의 높이를 가장 높은 것에 맞춘다(HUG로 두면 글 길이만큼만 커져 아래가 들쭉날쭉해진다)
function equalizeHeights(cards, w){
  if(cards.length < 2) return;
  let h = 0; for(const c of cards) if(c.height > h) h = c.height;
  for(const c of cards){ c.layoutSizingVertical='FIXED'; c.resize(w, h); }
}

function blockSample(parent, b, width){            // 예시 화면 카드(모바일 폭 380)
  const W = width || 380;
  const card = frame('sample','VERTICAL',{gap:10, px:18, py:18, fill:C.card, stroke:C.line, radius:18});
  parent.appendChild(card); card.layoutSizingHorizontal='FIXED'; card.resize(W, 10); card.layoutSizingVertical='HUG';
  const inner = W - 36;
  for(const it of b.items){
    if(it.kind==='label'){ addText(card, it.text, 11, C.ink3, 700, {lh:1.3}); }
    else if(it.kind==='comment'){
      const box = frame('comment','VERTICAL',{gap:4, px:14, py:12, fill:it.tint, radius:12}); card.appendChild(box); fill(box);
      if(it.title) addText(box, it.title, 11, it.color, 800, {lh:1.4});
      if(it.body) addText(box, it.body, 13, C.ink1, 500, {lh:1.6});
      if(it.button){ const bt = frame('button','VERTICAL',{px:14, py:8, fill:C.acc, radius:10}); box.appendChild(bt); const t = text(it.button, 12, '#FFFFFF', 700, {lh:1.2}); bt.appendChild(t); t.textAutoResize='WIDTH_AND_HEIGHT'; }
    }
    else if(it.kind==='lead'){ addText(card, it.text, 13.5, C.ink1, 500); }
    else if(it.kind==='p'){ addText(card, it.text, 13, C.ink2, 400); }
    else if(it.kind==='head'){
      const row = frame('head','HORIZONTAL',{gap:8, align:'CENTER'}); card.appendChild(row); fill(row);
      const t = text(it.text, 16, C.ink1, 800, {lh:1.3}); row.appendChild(t); fill(t);
      if(it.badge){ const bd = frame('badge','VERTICAL',{px:12, py:5, fill:'#E7F7ED', radius:999}); row.appendChild(bd); const bt = text(it.badge, 12, it.badgeColor || C.acc, 800, {lh:1.2}); bd.appendChild(bt); bt.textAutoResize='WIDTH_AND_HEIGHT'; }
    }
    else if(it.kind==='kv'){
      const row = frame('row','HORIZONTAL',{gap:8, px:10, py:8, stroke:C.line, radius:0}); card.appendChild(row); fill(row);
      const k = text(it.k, 12.5, C.ink2, 400); row.appendChild(k); fill(k);
      const v = text(it.v, 12.5, C.ink1, 700, {align:'RIGHT'}); row.appendChild(v); v.textAutoResize='WIDTH_AND_HEIGHT';
    }
    else if(it.kind==='tiles'){
      const n = it.items.length, gap=8, w = Math.floor((inner - gap*(n-1))/n);
      const row = frame('tiles','HORIZONTAL',{gap, align:'MIN'}); card.appendChild(row); fill(row);
      for(const t of it.items){
        const tile = frame(t.label||'tile','VERTICAL',{gap:4, px:10, py:12, fill:C.card, stroke:C.line, radius:14}); row.appendChild(tile);
        tile.layoutSizingHorizontal='FIXED'; tile.resize(w, 118); tile.layoutSizingVertical='FIXED';
        tile.primaryAxisAlignItems='MIN';
        if(t.label) addText(tile, t.label, 11, t.labelColor || C.acc, 700, {lh:1.3});
        addText(tile, t.text, t.lock ? 11.5 : 12.5, t.done ? C.ink3 : C.ink1, t.done ? 600 : 700, {lh:1.4});
        if(t.emoji){ const sp = frame('spacer','VERTICAL',{}); tile.appendChild(sp); sp.layoutSizingVertical='FILL'; sp.layoutSizingHorizontal='FILL';
          const e = text(t.emoji, 24, C.ink1, 400, {lh:1.1, align:'RIGHT'}); tile.appendChild(e); fill(e); }
      }
    }
    else if(it.kind==='streak'){
      const n = it.items.length, gap=8, w = Math.floor((inner - gap*(n-1))/n);
      const row = frame('streak','HORIZONTAL',{gap, align:'MIN'}); card.appendChild(row); fill(row);
      for(const t of it.items){
        const tile = frame(t.label||'tile','VERTICAL',{gap:2, px:8, py:12, fill:t.tint, radius:12}); row.appendChild(tile);
        tile.layoutSizingHorizontal='FIXED'; tile.resize(w, 84); tile.layoutSizingVertical='FIXED'; tile.primaryAxisAlignItems='CENTER'; tile.counterAxisAlignItems='CENTER';
        const a = text(t.label, 11, t.color, 700, {lh:1.3, align:'CENTER'}); tile.appendChild(a); fill(a);
        const bg = text(t.big, t.soft ? 13 : 18, t.soft ? C.ink2 : C.ink1, 800, {lh:1.2, align:'CENTER'}); tile.appendChild(bg); fill(bg);
        const s = text(t.sub, 10.5, C.ink3, 500, {lh:1.3, align:'CENTER'}); tile.appendChild(s); fill(s);
      }
    }
    else if(it.kind==='days'){
      const n = it.items.length, gap=5, w = Math.floor((inner - gap*(n-1))/n);
      const row = frame('days','HORIZONTAL',{gap, align:'MIN'}); card.appendChild(row); fill(row);
      for(const d of it.items){
        const cell = frame(d.label||'day','VERTICAL',{gap:4, px:0, py:7, fill:d.on ? '#EEF3FF' : '#F5F7FB', radius:10}); row.appendChild(cell);
        cell.layoutSizingHorizontal='FIXED'; cell.resize(w, 10); cell.layoutSizingVertical='HUG'; cell.counterAxisAlignItems='CENTER';
        const hex = figma.createPolygon(); created++; hex.pointCount = 6; hex.resize(22, 22); hex.fills = solid(d.on ? '#34C27A' : '#DDE3EC'); cell.appendChild(hex);
        const l = text(d.label, 11, d.on ? C.acc : C.ink3, d.on ? 800 : 600, {lh:1.2, align:'CENTER'}); cell.appendChild(l); fill(l);
      }
    }
  }
}

function blockExamples(parent, b, contentWidth){   // 상황별 예시 화면 2열 그리드
  const cols = 2, gap = 16, w = Math.floor((contentWidth - gap*(cols-1)) / cols);
  let row = null;
  b.items.forEach((it, i) => {
    if(i % cols === 0){ row = frame('examples row','HORIZONTAL',{gap, align:'MIN'}); parent.appendChild(row); fill(row); }
    const cell = frame(it.title || `예시 ${i+1}`,'VERTICAL',{gap:10, px:14, py:14, fill:C.mini, stroke:C.line, radius:16});
    row.appendChild(cell); cell.layoutSizingHorizontal='FIXED'; cell.resize(w, 10); cell.layoutSizingVertical='HUG';
    if(it.title) addText(cell, it.title, 12, C.ink3, 800, {lh:1.4});
    blockSample(cell, it.sample, w - 28);
    if(it.note) addText(cell, it.note, 11.5, C.ink3, 400, {lh:1.5});
  });
}

// ---------- 순서도 ----------
const FN = {
  start:{fill:C.acc, stroke:C.acc, tx:'#FFFFFF', w:800, r:999, sub:'#DDE5FF'},
  end:{fill:'#E8F8EE', stroke:'#BDE8CF', tx:C.ink1, w:800, r:999, sub:C.ink3},
  q:{fill:C.accL, stroke:C.acc, tx:C.ink1, w:800, r:12, sub:C.ink2},
  out:{fill:C.mini, stroke:'#C9D4E8', tx:C.ink2, w:500, r:12, sub:C.ink3},
  muted:{fill:'#F1F3F7', stroke:'#D3D8E2', tx:C.ink2, w:500, r:12, sub:C.ink3},
  node:{fill:C.card, stroke:'#C9D4E8', tx:C.ink1, w:600, r:12, sub:C.ink3}
};
function centerWrap(parent, name){   // 폭을 내용에 맞춘 요소를 가로 가운데에 놓기 위한 래퍼
  const w = frame(name || 'center','VERTICAL',{gap:0, align:'CENTER'}); parent.appendChild(w); fill(w); return w;
}
function fNode(parent, b, width){
  const st = FN[b.kind] || FN.node;
  const pill = (b.kind==='start' || b.kind==='end');
  const host = pill ? centerWrap(parent, `node · ${b.kind}`) : parent;
  const box = frame(`node · ${b.kind}`,'VERTICAL',{gap:2, px:16, py:12, fill:st.fill, stroke:st.stroke, sw:1.5, radius:st.r, align:'CENTER'});
  host.appendChild(box);
  if(pill){ box.layoutSizingHorizontal='HUG'; } else { fill(box); }
  const label = (b.kind==='q' ? '?  ' : '') + b.text;
  const t = text(label, 13.5, st.tx, st.w, {lh:1.5, align:'CENTER'}); box.appendChild(t);
  if(b.kind==='start' || b.kind==='end') t.textAutoResize='WIDTH_AND_HEIGHT'; else fill(t);
  if(b.sub){ const s = text(b.sub, 12, st.sub, 400, {lh:1.5, align:'CENTER'}); box.appendChild(s); if(b.kind==='start'||b.kind==='end') s.textAutoResize='WIDTH_AND_HEIGHT'; else fill(s); }
  box.layoutSizingVertical='HUG';
}
function fArrow(parent, b){
  const col = frame('arrow','VERTICAL',{gap:0, py:2, align:'CENTER'}); parent.appendChild(col); fill(col);
  const a = text('↓', 18, '#98A4B8', 400, {lh:1.1, align:'CENTER'}); col.appendChild(a); a.textAutoResize='WIDTH_AND_HEIGHT';
  if(b.label){ const l = text(b.label, 12, C.ink2, 700, {lh:1.3, align:'CENTER'}); col.appendChild(l); l.textAutoResize='WIDTH_AND_HEIGHT'; }
}
function fBlocks(parent, blocks, width){
  for(const b of blocks){
    switch(b.type){
      case 'fnode': fNode(parent, b, width); break;
      case 'farrow': fArrow(parent, b); break;
      case 'fsplit': fSplit(parent, b, width); break;
      case 'floop': fLoop(parent, b, width); break;
      case 'fchain': fChain(parent, b, width); break;
      case 'cards': blockCards(parent, b, width); break;
      case 'callout': blockCallout(parent, b); break;
      case 'h3': blockH3(parent, b); break;
      case 'p': blockP(parent, b); break;
    }
  }
}
function fSplit(parent, b, width){
  const n = b.branches.length, gap = 16, w = Math.floor((width - gap*(n-1)) / n);
  const row = frame('split','HORIZONTAL',{gap, align:'MIN'}); parent.appendChild(row); fill(row);
  for(const br of b.branches){
    const col = frame(br.tag || 'branch','VERTICAL',{gap:0, align:'CENTER'}); row.appendChild(col);
    col.layoutSizingHorizontal='FIXED'; col.resize(w, 10); col.layoutSizingVertical='HUG';
    if(br.tag){ const pill = frame('tag','VERTICAL',{px:12, py:3, fill: br.no ? '#F1F3F7' : C.accL, radius:999}); col.appendChild(pill); const t = text(br.tag, 12, br.no ? C.ink2 : C.acc, 800, {lh:1.4}); pill.appendChild(t); t.textAutoResize='WIDTH_AND_HEIGHT'; const sp = frame('gap','VERTICAL',{}); col.appendChild(sp); sp.resize(10,6); sp.layoutSizingHorizontal='FIXED'; sp.layoutSizingVertical='FIXED'; }
    fBlocks(col, br.blocks, w);
  }
}
function fLoop(parent, b, width){
  const box = frame('loop','VERTICAL',{gap:0, px:16, py:14, fill:C.card, stroke:'#C9D4E8', sw:1.5, radius:14, align:'CENTER'}); parent.appendChild(box); fill(box);
  box.dashPattern = [6,4];
  if(b.cap){ const c = text(b.cap, 12, C.ink3, 800, {lh:1.4, align:'CENTER'}); box.appendChild(c); c.textAutoResize='WIDTH_AND_HEIGHT'; }
  fBlocks(box, b.blocks, width - 32);
}
function fChain(parent, b, width){
  const qw = Math.floor(width*0.4), aw = 44, rw = width - qw - aw - 16;
  const list = frame('chain','VERTICAL',{gap:0}); parent.appendChild(list); fill(list);
  b.steps.forEach((s, i) => {
    if(s.noBefore){ const w = centerWrap(list, 'no-arrow'); const na = text('↓ 아니오', 12, C.ink2, 700, {lh:1.6, align:'CENTER'}); w.appendChild(na); na.textAutoResize='WIDTH_AND_HEIGHT'; }
    const row = frame(`step ${i+1}`,'HORIZONTAL',{gap:8, align:'CENTER'}); list.appendChild(row); fill(row);
    const q = frame('q','VERTICAL',{px:14, py:10, fill: s.qkind==='muted' ? '#F1F3F7' : C.accL, stroke: s.qkind==='muted' ? '#D3D8E2' : C.acc, sw:1.5, radius:12}); row.appendChild(q); q.layoutSizingHorizontal='FIXED'; q.resize(qw, 10); q.layoutSizingVertical='HUG';
    addText(q, (s.qkind==='muted' ? '' : '?  ') + s.q, 13, C.ink1, 800, {lh:1.45});
    const mid = frame('yes','VERTICAL',{gap:0, align:'CENTER'}); row.appendChild(mid); mid.layoutSizingHorizontal='FIXED'; mid.resize(aw, 10); mid.layoutSizingVertical='HUG';
    const y1 = text(s.yes || '→', 12, C.acc, 800, {lh:1.3, align:'CENTER'}); mid.appendChild(y1); fill(y1);
    const y2 = text('→', 16, '#98A4B8', 400, {lh:1.2, align:'CENTER'}); mid.appendChild(y2); fill(y2);
    const res = frame('result','VERTICAL',{gap:2, px:14, py:10, fill:C.mini, stroke:C.line, radius:12}); row.appendChild(res); res.layoutSizingHorizontal='FIXED'; res.resize(rw, 10); res.layoutSizingVertical='HUG';
    if(s.title) addText(res, s.title, 12, C.ink3, 700, {lh:1.4});
    if(s.body) addText(res, s.body, 13, C.ink1, 500, {lh:1.55});
  });
}

// ---------- 문서 ----------
function buildSection(sec, contentWidth){
  const card = frame(`${sec.num}. ${sec.title}`, 'VERTICAL', {gap:S.blockGap, px:S.cardPad, py:34, fill:C.card, stroke:C.line, radius:R.card});
  const head = frame('head','HORIZONTAL',{gap:12, align:'CENTER'}); card.appendChild(head); fill(head);
  const badge = frame('num','VERTICAL',{px:0, py:0, fill:C.accL, radius:9, align:'CENTER'}); head.appendChild(badge);
  badge.resize(30,30); badge.layoutSizingHorizontal='FIXED'; badge.layoutSizingVertical='FIXED'; badge.primaryAxisAlignItems='CENTER';
  const nb = text(sec.num, 14, C.acc, 800, {lh:1, align:'CENTER'}); badge.appendChild(nb); nb.textAutoResize='WIDTH_AND_HEIGHT';
  const ttl = text(sec.title, 24, C.ink1, 800, {lh:1.3}); head.appendChild(ttl); fill(ttl);
  if(sec.sub) addText(card, sec.sub, 14, C.ink3, 400);
  for(const b of sec.blocks || []){
    switch(b.type){
      case 'h3': blockH3(card,b); break;
      case 'p': blockP(card,b); break;
      case 'bullets': blockBullets(card,b); break;
      case 'table': blockTable(card,b,contentWidth - S.cardPad*2); break;
      case 'callout': blockCallout(card,b); break;
      case 'formula': blockFormula(card,b); break;
      case 'tiles': blockTiles(card,b,contentWidth - S.cardPad*2); break;
      case 'cards': blockCards(card,b,contentWidth - S.cardPad*2); break;
      case 'steps': blockSteps(card,b,contentWidth - S.cardPad*2); break;
      case 'sample': blockSample(card,b); break;
      case 'examples': blockExamples(card,b,contentWidth - S.cardPad*2); break;
      case 'fnode': case 'farrow': case 'fsplit': case 'floop': case 'fchain': fBlocks(card,[b],contentWidth - S.cardPad*2); break;
      default: blockP(card,{text:JSON.stringify(b)});
    }
  }
  return card;
}

function buildHero(doc){
  const hero = frame('hero','VERTICAL',{gap:14, px:40, py:44, fill:C.acc, radius:R.hero});
  const pill = frame('eyebrow','VERTICAL',{px:14, py:6, fill:'#4F7DFF', radius:18}); hero.appendChild(pill);
  const pt = text(doc.eyebrow || '마이리포트 v2 · 기획 문서', 13, '#FFFFFF', 700, {lh:1.2}); pill.appendChild(pt); pt.textAutoResize='WIDTH_AND_HEIGHT';
  addText(hero, doc.title, 44, '#FFFFFF', 800, {lh:1.25});
  if(doc.subtitle) addText(hero, doc.subtitle, 19, '#EDF2FF', 500, {lh:1.5});
  if(doc.meta) addText(hero, doc.meta, 14, '#DDE5FF', 400, {lh:1.5});
  return hero;
}

let fontsReady = false;
async function build(doc, width, replace){
  if(!fontsReady){ await loadFonts(); fontsReady = true; }
  const boardName = `[문서] ${doc.title}`;
  if(replace){
    for(const n of figma.currentPage.findChildren(n => n.name === boardName)){ try{ n.remove(); }catch(e){ /* 이미 제거됐거나 잠긴 노드 */ } }
  }
  const contentWidth = width - S.pad*2;
  const page = frame(boardName,'VERTICAL',{gap:S.gap, px:S.pad, py:60, fill:C.bg, radius:R.page});
  page.resize(width, 100);
  page.primaryAxisSizingMode = 'AUTO';     // 높이는 내용에 맞춰 늘어남 (resize가 FIXED로 바꿔 놓으므로 다시 지정)
  page.counterAxisSizingMode = 'FIXED';    // 폭만 고정
  page.clipsContent = false;
  const hero = buildHero(doc); page.appendChild(hero); fill(hero);
  let i = 0;
  const failed = [];
  for(const sec of doc.sections){
    figma.ui.postMessage({ type:'progress', message:`${++i}/${doc.sections.length} · ${sec.title}` });
    try{ const card = buildSection(sec, contentWidth); page.appendChild(card); fill(card); }
    catch(e){ failed.push(`${sec.num} ${sec.title}: ${e && e.message ? e.message : e}`); const err = text(`⚠ ${sec.num} ${sec.title} — 생성 실패: ${e && e.message ? e.message : e}`, 13, C.riskLine, 700); page.appendChild(err); fill(err); }
    await new Promise(r => setTimeout(r, 0));
  }
  if(failed.length) figma.ui.postMessage({ type:'progress', message:`일부 장 실패: ${failed.join(' / ')}` });
  const foot = text(doc.footer || `${doc.title} · ${doc.meta || ''}`, 12.5, C.ink3, 500, {align:'CENTER'}); page.appendChild(foot); fill(foot);
  // 최종 안전장치: 높이 자동이 풀려 있으면 자식 끝까지 늘린다
  if(page.primaryAxisSizingMode !== 'AUTO'){ const bottom = page.children.reduce((m,c)=>Math.max(m, c.y + c.height), 0); page.resize(width, bottom + 60); }
  // 위치: 현재 뷰포트 중앙 근처, 기존 보드와 겹치지 않게 오른쪽으로
  const others = figma.currentPage.findChildren(n => n.name.startsWith('[문서]') && n !== page);
  const maxX = others.reduce((m,n)=>Math.max(m, n.x + n.width), 0);
  page.x = others.length ? maxX + 120 : figma.viewport.center.x - width/2;
  page.y = others.length ? others[0].y : figma.viewport.center.y - 200;
  figma.currentPage.selection = [page];
  figma.viewport.scrollAndZoomIntoView([page]);
  return created;
}

figma.showUI(__html__, { width: 360, height: 420 });
let busy = false;
figma.ui.onmessage = async msg => {
  if(!msg || msg.type !== 'build') return;
  if(busy){ figma.ui.postMessage({ type:'progress', message:'이전 생성이 아직 진행 중이에요…' }); return; }
  busy = true; created = 0;
  try{ const n = await build(msg.doc, msg.width || 1200, msg.replace); figma.ui.postMessage({ type:'done', nodes:n }); }
  catch(e){ figma.ui.postMessage({ type:'error', message:'생성 실패: ' + (e && e.message ? e.message : e) + (e && e.stack ? ' · ' + String(e.stack).split('\n')[1] : '') }); }
  finally{ busy = false; }
};
