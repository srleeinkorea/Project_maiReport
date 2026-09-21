/* =========================================================================
   maiReport · LIFE-001 목표 분석 — 실천 기록 화면 생성기
   Figma 플러그인. 실행하면 오토레이아웃이 잡힌 프레임 한 장을 만든다.
   ========================================================================= */

// ---------- 토큰 ----------
const C = {
  ground:      '#F4F6FA',
  surface:     '#FFFFFF',
  ink:         '#16202F',
  sub:         '#7A879A',
  quiet:       '#66748A',
  caption:     '#6E7C90',
  captionOff:  '#95A0B0',
  divider:     '#EDF0F5',
  cardLine:    '#F0F3F8',
  primary:     '#2F6BFF',
  primaryBg:   '#EDF3FF',
  primaryLine: '#CFDEFF',
  chipLine:    '#DFE4EC',
  future:      '#C3CCD9',
  arrow:       '#B9C3D1',
  tabOff:      '#9AA6B6',
  iconOff:     '#DDE3EC',
  todayLabel:  '#DCE7FF',

  diet:        '#E0803A', dietBg:     '#FCEBD8', dietStrong:     '#B4611F',
  activity:    '#E0567B', activityBg: '#FBDDE6', activityStrong: '#B93E5F',
  sleep:       '#6B72D8', sleepBg:    '#DFE2FA', sleepStrong:    '#4A51BC',
  commentInk:  '#3C4460', commentHi:  '#4046B8', commentTitle:   '#5159CC'
};

const R = { block: 17, card: 13, art: 9, button: 8, chip: 11 };
const S = { screenX: 18, blockPad: 16, blockGap: 13, cardGap: 8 };

let FONT = 'Inter';
const WEIGHT = { 400: 'Regular', 500: 'Medium', 700: 'Bold', 800: 'Bold', 900: 'Black' };

// ---------- 유틸 ----------
function rgb(hex) {
  const h = hex.replace('#', '');
  return {
    r: parseInt(h.slice(0, 2), 16) / 255,
    g: parseInt(h.slice(2, 4), 16) / 255,
    b: parseInt(h.slice(4, 6), 16) / 255
  };
}
const solid = (hex) => [{ type: 'SOLID', color: rgb(hex) }];

async function loadFonts() {
  const families = ['Noto Sans KR', 'Pretendard', 'Inter'];
  const styles = ['Regular', 'Medium', 'Bold', 'Black'];
  for (const family of families) {
    try {
      for (const style of styles) await figma.loadFontAsync({ family, style });
      FONT = family;
      return;
    } catch (e) { /* 다음 후보 */ }
  }
  await figma.loadFontAsync({ family: 'Inter', style: 'Regular' });
  FONT = 'Inter';
}

/** 오토레이아웃 프레임 */
function box(name, opts) {
  const o = opts || {};
  const f = figma.createFrame();
  f.name = name;
  f.layoutMode = o.dir === 'h' ? 'HORIZONTAL' : 'VERTICAL';
  f.primaryAxisSizingMode = o.mainFixed ? 'FIXED' : 'AUTO';
  f.counterAxisSizingMode = o.crossFixed ? 'FIXED' : 'AUTO';
  f.itemSpacing = o.gap || 0;
  const p = o.pad || [0, 0, 0, 0];
  f.paddingTop = p[0]; f.paddingRight = p[1]; f.paddingBottom = p[2]; f.paddingLeft = p[3];
  f.primaryAxisAlignItems = o.main || 'MIN';
  f.counterAxisAlignItems = o.cross || 'MIN';
  f.cornerRadius = o.radius || 0;
  f.fills = o.fill ? solid(o.fill) : [];
  if (o.stroke) { f.strokes = solid(o.stroke); f.strokeWeight = 1; }
  if (o.width) f.resize(o.width, f.height);
  if (o.height) { f.counterAxisSizingMode = 'FIXED'; f.resize(f.width, o.height); }
  return f;
}

/** 텍스트 */
function text(content, opts) {
  const o = opts || {};
  const t = figma.createText();
  t.fontName = { family: FONT, style: WEIGHT[o.weight || 400] };
  t.characters = content;
  t.fontSize = o.size || 12;
  t.fills = solid(o.color || C.ink);
  if (o.tracking) t.letterSpacing = { unit: 'PIXELS', value: o.tracking };
  if (o.lineHeight) t.lineHeight = { unit: 'PIXELS', value: o.lineHeight };
  t.textAlignHorizontal = o.align || 'LEFT';
  t.textAutoResize = o.wrap ? 'HEIGHT' : 'WIDTH_AND_HEIGHT';
  return t;
}

const stretch = (n) => { n.layoutAlign = 'STRETCH'; return n; };
const grow = (n) => { n.layoutGrow = 1; return n; };

function rect(w, h, fill, radius) {
  const r = figma.createRectangle();
  r.resize(w, h);
  r.fills = solid(fill);
  r.cornerRadius = radius || 0;
  return r;
}

// ---------- 블록 조립 ----------
function header() {
  const f = box('Header', { dir: 'h', pad: [20, S.screenX, 0, S.screenX], main: 'SPACE_BETWEEN' });
  const left = box('Title', { gap: 3 });
  left.appendChild(text('생활', { size: 20, weight: 900, tracking: -0.8 }));
  left.appendChild(text('8월 4주차', { size: 11, color: C.sub }));
  const btn = box('Button / 오늘', {
    dir: 'h', pad: [7, 15, 7, 15], radius: 15, fill: C.surface, stroke: C.chipLine
  });
  btn.appendChild(text('오늘', { size: 11, weight: 700 }));
  f.appendChild(left); f.appendChild(btn);
  return f;
}

function dateChip(day, num, state) {
  const c = box('Nav/DateChip · ' + state, {
    pad: [4, 0, 6, 0], gap: 2, radius: R.chip, cross: 'CENTER',
    fill: state === '오늘' ? C.primary : undefined
  });
  const labelColor = state === '오늘' ? C.todayLabel : state === '미래' ? C.future : C.sub;
  const numColor   = state === '오늘' ? C.surface   : state === '미래' ? C.future : C.ink;
  c.appendChild(text(day, { size: 9.5, color: labelColor, align: 'CENTER' }));
  c.appendChild(text(num, { size: 13.5, weight: 700, color: numColor, align: 'CENTER' }));
  return grow(c);
}

function dateStrip() {
  const f = box('DateStrip', { dir: 'h', gap: 2, pad: [16, 20, 0, 20], cross: 'CENTER' });
  f.appendChild(text('‹', { size: 14, color: C.arrow }));
  const days = [['월', '17', '기본'], ['화', '18', '기본'], ['수', '19', '기본'],
                ['오늘', '20', '오늘'], ['금', '21', '미래'], ['토', '22', '미래'], ['일', '23', '미래']];
  days.forEach(([d, n, s]) => f.appendChild(dateChip(d, n, s)));
  f.appendChild(text('›', { size: 14, color: C.arrow }));
  return f;
}

function tabs() {
  const wrap = box('Tabs', { gap: 0 });
  const row = box('TabRow', { dir: 'h', gap: 15, pad: [11, S.screenX, 0, S.screenX] });
  [['목표 분석', true], ['지표별 분석', false], ['생활 분석', false], ['AI 인사이트', false]]
    .forEach(([label, on]) => {
      const item = box('Nav/TabItem · ' + (on ? '활성' : '비활성'), { gap: 7, cross: 'CENTER' });
      item.appendChild(text(label, { size: 12, weight: 700, color: on ? C.primary : C.tabOff }));
      const underline = rect(56, 2, on ? C.primary : C.divider, 0);
      item.appendChild(underline);
      underline.layoutAlign = 'STRETCH';
      if (!on) underline.opacity = 0;
      row.appendChild(item);
    });
  wrap.appendChild(row);
  wrap.appendChild(stretch(rect(390, 1, C.divider)));
  return wrap;
}

function goalCard(cat, line1, line2, color, bg) {
  const card = box('Goal/Card · ' + cat, {
    pad: [11, 10, 10, 10], gap: 7, radius: R.card, fill: C.surface, stroke: C.cardLine
  });
  card.appendChild(text(cat, { size: 10.5, weight: 800, color }));
  const title = text(line1 + '\n' + line2, { size: 12, weight: 700, lineHeight: 17, wrap: true });
  card.appendChild(stretch(title));
  card.appendChild(stretch(rect(82, 36, bg, R.art)));
  const btn = box('Button/Complete · 기본', {
    pad: [6, 0, 6, 0], radius: R.button, fill: C.primaryBg, stroke: C.primaryLine, cross: 'CENTER'
  });
  btn.appendChild(text('완료', { size: 10.5, weight: 700, color: C.primary, align: 'CENTER' }));
  card.appendChild(stretch(btn));
  return grow(card);
}

function blockGoals() {
  const b = box('Block / 오늘의목표', {
    gap: S.blockGap, pad: [S.blockPad, S.blockPad, S.blockPad, S.blockPad],
    radius: R.block, fill: C.surface
  });
  const head = box('BlockHeader', { dir: 'h', main: 'SPACE_BETWEEN', cross: 'CENTER' });
  head.appendChild(text('오늘의 목표', { size: 15, weight: 900, tracking: -0.6 }));
  head.appendChild(text('0/3 완료', { size: 11, color: C.sub }));
  b.appendChild(stretch(head));

  const row = box('Goals', { dir: 'h', gap: S.cardGap });
  row.appendChild(goalCard('식이', '저녁 균형', '식사', C.diet, C.dietBg));
  row.appendChild(goalCard('활동', '식후 10분', '걷기', C.activity, C.activityBg));
  row.appendChild(goalCard('수면', '23시 30분에', '눕기', C.sleep, C.sleepBg));
  b.appendChild(stretch(row));
  return stretch(b);
}

function streakTile(cat, state, value, unit, caption, strong, bg) {
  const t = box('Streak/Tile · ' + cat + ' · ' + state, {
    pad: [12, 9, 13, 9], gap: 5, radius: R.card, fill: bg, cross: 'CENTER'
  });
  t.appendChild(text(cat, { size: 11, weight: 800, color: strong, align: 'CENTER' }));

  if (unit) {
    const v = text(value + unit, { size: 18, weight: 900, tracking: -0.7, align: 'CENTER' });
    v.setRangeFontSize(value.length, value.length + unit.length, 12);
    t.appendChild(v);
  } else {
    t.appendChild(text(value, { size: 14, weight: 900, tracking: -0.4, color: C.quiet, align: 'CENTER' }));
  }

  const carried = state === '주넘김';
  t.appendChild(text(caption, {
    size: 10, weight: carried ? 800 : 400,
    color: carried ? strong : (unit ? C.caption : C.captionOff), align: 'CENTER'
  }));
  return grow(t);
}

function commentCard() {
  const c = box('Comment/Card · 수면', {
    pad: [12, 14, 13, 14], gap: 5, radius: R.card, fill: C.sleepBg
  });
  c.appendChild(text('가장 오래 이어가는 것', {
    size: 9.5, weight: 800, tracking: 0.5, color: C.commentTitle
  }));

  const l1 = text('수면을 10일째 이어가고 있어요.', { size: 12, color: C.commentInk, lineHeight: 20, wrap: true });
  l1.setRangeFontName(4, 8, { family: FONT, style: 'Black' });
  l1.setRangeFontSize(4, 8, 15);
  l1.setRangeFills(4, 8, solid(C.commentHi));
  c.appendChild(stretch(l1));

  const l2 = text('나흘만 더 하면 2주예요.', { size: 12, color: C.commentInk, lineHeight: 20, wrap: true });
  l2.setRangeFontName(0, 5, { family: FONT, style: 'Bold' });
  l2.setRangeFills(0, 5, solid(C.commentHi));
  c.appendChild(stretch(l2));
  return stretch(c);
}

function blockStreak() {
  const b = box('Block / 목표이어가기', {
    gap: S.blockGap, pad: [S.blockPad, S.blockPad, S.blockPad, S.blockPad],
    radius: R.block, fill: C.surface
  });
  b.appendChild(stretch(text('목표 이어가기', { size: 15, weight: 900, tracking: -0.6 })));

  const row = box('Tiles', { dir: 'h', gap: S.cardGap });
  row.appendChild(streakTile('식이', '끊김', '다시 시작', null, '오늘 하면 1일째', C.dietStrong, C.dietBg));
  row.appendChild(streakTile('활동', '이어가는중', '1', '일째', '이어가는 중', C.activityStrong, C.activityBg));
  row.appendChild(streakTile('수면', '주넘김', '10', '일째', '지난주부터', C.sleepStrong, C.sleepBg));
  b.appendChild(stretch(row));
  b.appendChild(commentCard());
  return stretch(b);
}

function tabBar() {
  const f = box('TabBar', { dir: 'h', pad: [9, 0, 12, 0], fill: C.surface, height: 56 });
  [['홈', false], ['생활', true], ['병원', false], ['더보기', false]].forEach(([label, on]) => {
    const item = box('Nav/BottomTab · ' + (on ? '활성' : '비활성'), { gap: 4, cross: 'CENTER' });
    item.appendChild(rect(18, 18, on ? C.ink : C.iconOff, 6));
    item.appendChild(text(label, { size: 9.5, weight: 700, color: on ? C.ink : C.tabOff, align: 'CENTER' }));
    f.appendChild(grow(item));
  });
  return stretch(f);
}

// ---------- 실행 ----------
async function main() {
  await loadFonts();

  const root = box('LIFE-001 / 목표 분석', { fill: C.ground, width: 390, crossFixed: true });
  root.appendChild(stretch(header()));
  root.appendChild(stretch(dateStrip()));
  root.appendChild(stretch(tabs()));

  const body = box('Body', { gap: S.blockGap, pad: [16, S.screenX, 20, S.screenX] });
  body.appendChild(blockGoals());
  body.appendChild(blockStreak());
  root.appendChild(stretch(body));

  root.appendChild(tabBar());

  figma.currentPage.appendChild(root);
  root.x = figma.viewport.center.x - 195;
  root.y = figma.viewport.center.y - 340;
  figma.currentPage.selection = [root];
  figma.viewport.scrollAndZoomIntoView([root]);

  figma.closePlugin('LIFE-001 화면을 만들었습니다 · 폰트 ' + FONT);
}

main();
