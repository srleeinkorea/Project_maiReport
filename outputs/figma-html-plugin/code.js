/* =========================================================================
   maiReport · HTML → Figma (틀 유지)
   플러그인 창이 읽어 온 화면 설계도(JSON)를 같은 위치 · 크기 · 모양의 Figma 레이어로 만든다.
   - 상자(배경 · 테두리 · 모서리 · 그림자 · 잘림) → 프레임
   - 글자 → 텍스트 레이어(부분 굵기 · 색 · 밑줄 유지, Figma에서 바로 고칠 수 있음)
   - 이미지 → 이미지 채우기 사각형, SVG → 벡터
   위치는 부모 프레임 기준 절대 좌표다(오토 레이아웃으로 바꾸지 않는다 = 틀이 그대로 남는다).
   ========================================================================= */

/* 창 크기 — 기본은 작게, 오른쪽 아래 모서리를 끌어 바꾸면 그 크기를 기억한다 */
const UI_MIN = { w: 560, h: 420 }, UI_MAX = { w: 1800, h: 1200 };
figma.showUI(__html__, { width: 820, height: 600, themeColors: false });
figma.clientStorage.getAsync('uiSize').then(s => { if (s && s.w && s.h) figma.ui.resize(s.w, s.h); }).catch(() => {});
function resizeUI(w, h, save){
  w = Math.round(Math.max(UI_MIN.w, Math.min(UI_MAX.w, w)));
  h = Math.round(Math.max(UI_MIN.h, Math.min(UI_MAX.h, h)));
  figma.ui.resize(w, h);
  if (save) figma.clientStorage.setAsync('uiSize', { w, h }).catch(() => {});
}

const KO_FONT = /pretendard|noto sans (kr|cjk)|apple sd|malgun|nanum|spoqa|ibm plex sans kr|gothic a1|suit|wanted sans/i;
const FALLBACK = ['Pretendard', 'Pretendard Variable', 'Noto Sans KR', 'Inter'];
const MONO = ['Roboto Mono', 'JetBrains Mono', 'Source Code Pro'];
const GENERIC = new Set(['sans-serif','serif','monospace','system-ui','-apple-system','blinkmacsystemfont','ui-monospace','ui-sans-serif','ui-serif','cursive','fantasy','emoji','math']);

let avail = null;                 // family → [{style, w, it}]
const resolved = new Map();       // 'family|w|it|ko|mono' → FontName
const imageHash = new Map();      // base64 → hash
let made = 0;

/* ── 글꼴 ── */
function styleWeight(st){
  const s = st.toLowerCase().replace(/[\s_-]/g, '');
  if (/thin|hairline/.test(s)) return 100;
  if (/extralight|ultralight/.test(s)) return 200;
  if (/semibold|demibold/.test(s)) return 600;
  if (/extrabold|ultrabold/.test(s)) return 800;
  if (/light/.test(s)) return 300;
  if (/black|heavy/.test(s)) return 900;
  if (/bold/.test(s)) return 700;
  if (/medium/.test(s)) return 500;
  return 400;
}
async function loadAvail(){
  if (avail) return;
  avail = new Map();
  for (const f of await figma.listAvailableFontsAsync()){
    const fam = f.fontName.family, st = f.fontName.style;
    if (!avail.has(fam)) avail.set(fam, []);
    avail.get(fam).push({ style: st, w: styleWeight(st), it: /italic|oblique/i.test(st) });
  }
}
function pickStyle(list, w, it){
  let pool = list.filter(s => s.it === it); if (!pool.length) pool = list;
  pool = pool.slice().sort((a, b) => Math.abs(a.w - w) - Math.abs(b.w - w) || b.w - a.w);
  return pool[0].style;
}
function fontFor(st, ko){
  const key = [st.font, st.w, st.it, ko, st.mono].join('|');
  if (resolved.has(key)) return resolved.get(key);
  const fams = String(st.font || '').split(',').map(s => s.trim().replace(/^["']|["']$/g, '')).filter(Boolean);
  const cands = fams.filter(f => !GENERIC.has(f.toLowerCase()));
  if (st.mono) cands.push(...MONO);
  cands.push(...FALLBACK);
  let out = null;
  for (const f of cands){
    const list = avail.get(f); if (!list || !list.length) continue;
    if (ko && !KO_FONT.test(f) && !st.mono) continue;      // 한글이 있는데 한글 글꼴이 아니면 건너뜀
    out = { family: f, style: pickStyle(list, st.w, st.it) }; break;
  }
  if (!out) out = { family: 'Inter', style: pickStyle(avail.get('Inter') || [{ style: 'Regular', w: 400, it: false }], st.w, st.it) };
  resolved.set(key, out);
  return out;
}
function collectFonts(n, set){
  if (n.t === 'text' && n.chars){
    const ko = /[ᄀ-ᇿ㄰-㆏가-힯]/.test(n.chars);
    n._fonts = n.styles.map(st => fontFor(st, ko));
    n._fonts.forEach(f => set.set(f.family + '|' + f.style, f));
  }
  (n.children || []).forEach(c => collectFonts(c, set));
}

/* ── 모양 ── */
const clamp01 = v => Math.max(0, Math.min(1, v));
function solid(c){ return { type: 'SOLID', color: { r: c.r, g: c.g, b: c.b }, opacity: c.a == null ? 1 : clamp01(c.a) }; }
function hashOf(b64){
  if (!imageHash.has(b64)) imageHash.set(b64, figma.createImage(figma.base64Decode(b64)).hash);
  return imageHash.get(b64);
}
function fills(arr){
  return (arr || []).map(p => {
    if (p.type === 'SOLID') return solid(p.c);
    if (p.type === 'GRADIENT_LINEAR') return { type: 'GRADIENT_LINEAR', gradientTransform: p.m,
      gradientStops: p.stops.map(s => ({ position: clamp01(s.p), color: { r: s.c.r, g: s.c.g, b: s.c.b, a: clamp01(s.c.a) } })) };
    if (p.type === 'IMAGE' && p.b64) return { type: 'IMAGE', imageHash: hashOf(p.b64), scaleMode: p.scale || 'FILL' };
    return null;
  }).filter(Boolean);
}
function effects(arr){
  return (arr || []).map(s => ({ type: s.inset ? 'INNER_SHADOW' : 'DROP_SHADOW', color: { r: s.color.r, g: s.color.g, b: s.color.b, a: clamp01(s.color.a) },
    offset: { x: s.x, y: s.y }, radius: Math.max(0, s.blur), spread: s.spread || 0, visible: true, blendMode: 'NORMAL' }));
}
function stroke(node, s){
  if (!s) return;
  node.strokes = [solid(s.c)];
  node.strokeAlign = s.align || 'INSIDE';
  if (s.t === s.r && s.r === s.b && s.b === s.l) node.strokeWeight = s.t;
  else { node.strokeTopWeight = s.t; node.strokeRightWeight = s.r; node.strokeBottomWeight = s.b; node.strokeLeftWeight = s.l; }
  const w = Math.max(s.t, s.r, s.b, s.l) || 1;
  if (s.dash === 'dash') node.dashPattern = [w * 3, w * 2];
  if (s.dash === 'dot') node.dashPattern = [w, w];
}
function radius(node, r){
  if (!r) return;
  if (r[0] === r[1] && r[1] === r[2] && r[2] === r[3]) node.cornerRadius = r[0];
  else { node.topLeftRadius = r[0]; node.topRightRadius = r[1]; node.bottomRightRadius = r[2]; node.bottomLeftRadius = r[3]; }
}
const size = v => Math.max(0.01, v || 0);

/* ── 레이어 만들기 ── */
async function tick(){
  made++;
  if (made % 250 === 0){ figma.ui.postMessage({ type: 'progress', made }); await new Promise(r => setTimeout(r, 0)); }
}
async function build(n, parent, px, py){
  if (n.t === 'frame'){
    const f = figma.createFrame(); parent.appendChild(f);
    f.name = n.name || 'div';
    f.resize(size(n.w), size(n.h)); f.x = n.x - px; f.y = n.y - py;
    f.fills = fills(n.fills); stroke(f, n.stroke); radius(f, n.radius); f.effects = effects(n.effects);
    f.clipsContent = !!n.clip;
    if (n.opacity != null) f.opacity = n.opacity;
    await tick();
    for (const c of n.children || []) await build(c, f, n.x, n.y);
    return f;
  }
  if (n.t === 'text') return text(n, parent, px, py);
  if (n.t === 'image'){
    const r = figma.createRectangle(); parent.appendChild(r);
    r.name = n.name || 'image';
    r.resize(size(n.w), size(n.h)); r.x = n.x - px; r.y = n.y - py;
    r.fills = n.b64 ? [{ type: 'IMAGE', imageHash: hashOf(n.b64), scaleMode: n.scale || 'FILL' }] : [solid({ r: .9, g: .92, b: .95, a: 1 })];
    radius(r, n.radius); stroke(r, n.stroke); r.effects = effects(n.effects);
    if (n.opacity != null) r.opacity = n.opacity;
    await tick(); return r;
  }
  if (n.t === 'svg'){
    let v;
    try { v = figma.createNodeFromSvg(n.svg); }
    catch (e) { v = figma.createRectangle(); v.resize(size(n.w), size(n.h)); v.fills = [solid({ r: .9, g: .92, b: .95, a: 1 })]; }
    parent.appendChild(v);
    v.name = n.name || 'svg'; v.x = n.x - px; v.y = n.y - py;
    if (n.opacity != null) v.opacity = n.opacity;
    await tick(); return v;
  }
}
const ALIGN = { left: 'LEFT', start: 'LEFT', center: 'CENTER', right: 'RIGHT', end: 'RIGHT', justify: 'JUSTIFIED', '-webkit-center': 'CENTER', '-webkit-left': 'LEFT', '-webkit-right': 'RIGHT' };
async function text(n, parent, px, py){
  if (!n.chars) return;
  const t = figma.createText(); parent.appendChild(t);
  t.name = n.name || 'text';
  t.fontName = n._fonts[n.segs[0][2]];
  t.characters = n.chars;
  for (const [s, e, k] of n.segs){
    if (e <= s) continue;
    const st = n.styles[k];
    t.setRangeFontName(s, e, n._fonts[k]);
    t.setRangeFontSize(s, e, Math.max(1, st.size));
    t.setRangeFills(s, e, [solid(st.color)]);
    t.setRangeLetterSpacing(s, e, { unit: 'PIXELS', value: st.ls || 0 });
    t.setRangeLineHeight(s, e, st.lh ? { unit: 'PIXELS', value: st.lh } : { unit: 'AUTO' });
    const d = /underline/.test(st.deco) ? 'UNDERLINE' : /line-through/.test(st.deco) ? 'STRIKETHROUGH' : 'NONE';
    if (d !== 'NONE') t.setRangeTextDecoration(s, e, d);
  }
  const align = ALIGN[n.align] || 'LEFT';
  if (n.ellipsis){
    t.textAutoResize = 'NONE'; t.resize(size(n.cw || n.w), size(n.h));
    t.textAlignHorizontal = align;
    try { t.textTruncation = 'ENDING'; } catch (e) {}
    t.x = (n.cx != null ? n.cx : n.x) - px; t.y = n.y - py;
  } else if (n.single){
    t.textAutoResize = 'WIDTH_AND_HEIGHT'; t.textAlignHorizontal = 'LEFT';
    // 한 줄 글자는 브라우저에서 놓인 자리(왼쪽 · 가운데 · 오른쪽 기준)를 지킨다
    let x = n.x;
    if (align === 'CENTER') x = n.x + n.w / 2 - t.width / 2;
    else if (align === 'RIGHT') x = n.x + n.w - t.width;
    t.x = x - px; t.y = n.y - py;
  } else {
    t.textAutoResize = 'HEIGHT';
    t.resize(size((n.cw || n.w) + 2), size(n.h));     // 글꼴 폭 차이로 줄이 하나 더 생기지 않게 2px 여유
    t.textAlignHorizontal = align;
    t.x = (n.cx != null ? n.cx : n.x) - px; t.y = n.y - py;
  }
  await tick(); return t;
}

/* 배치 — 같은 화면(group)은 그 열 맨 아래에 세로로 쌓고, 다른 화면은 오른쪽에 새 열로 놓는다
   (이 플러그인이 만든 프레임은 이름이 아니라 숨은 표시로 구분) */
const GAP_X = 160, GAP_Y = 120;
function place(root, w, h, group){
  const prev = figma.currentPage.children.filter(c => c !== root && c.getPluginData && c.getPluginData('h2f') === '1');
  const same = group ? prev.filter(c => c.getPluginData('h2fGroup') === group) : [];
  if (same.length){
    const last = same.reduce((a, c) => (c.y + c.height > a.y + a.height ? c : a));
    root.x = last.x; root.y = last.y + last.height + GAP_Y;
  } else if (prev.length){
    root.x = Math.max(...prev.map(c => c.x + c.width)) + GAP_X;
    root.y = Math.min(...prev.map(c => c.y));
  } else {
    const c = figma.viewport.center; root.x = Math.round(c.x - w / 2); root.y = Math.round(c.y - h / 2);
  }
}

figma.ui.onmessage = async msg => {
  if (msg.type === 'resize'){ resizeUI(msg.w, msg.h, msg.save); return; }
  if (msg.type !== 'build') return;
  made = 0;
  try {
    const out = msg.out, r = out.root;
    await loadAvail();
    const need = new Map(); collectFonts(r, need);
    await Promise.all([...need.values()].map(f => figma.loadFontAsync(f)));
    const swapped = [...need.values()].map(f => f.family).filter((v, i, a) => a.indexOf(v) === i);

    const root = figma.createFrame();
    root.name = msg.label || out.title || '문서';
    root.setPluginData('h2f', '1');
    if (msg.group) root.setPluginData('h2fGroup', msg.group);
    root.resize(size(r.w), size(r.h));
    root.fills = fills(r.fills); stroke(root, r.stroke); radius(root, r.radius); root.effects = effects(r.effects);
    root.clipsContent = true;
    place(root, r.w, r.h, msg.group);
    figma.currentPage.appendChild(root);
    for (const c of r.children || []) await build(c, root, r.x, r.y);

    figma.currentPage.selection = [root];
    figma.viewport.scrollAndZoomIntoView([root]);
    figma.ui.postMessage({ type: 'done', made, name: root.name, fontNote: '사용한 글꼴: ' + swapped.join(', ') });
  } catch (e) {
    figma.ui.postMessage({ type: 'error', msg: String(e && e.message || e) });
  }
};
