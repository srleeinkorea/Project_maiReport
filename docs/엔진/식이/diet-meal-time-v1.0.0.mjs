// 식이 데이터계약 v1.3.0 · 끼니별 식사 시각 단계(DIET-Q-08 · DIET-Q-09)의 참조 구현.
// 고정 질문(DIET-Q-00)에 답한 바로 뒤 같은 자리에서 「{끼니}은 언제쯤 드셨어요?」를 묻는다.
// 이 파일은 ① 물을지 말지(askMealTime) ② 버튼 3개 만들기(mealTimeOptions)
// ③ 고른 버튼으로 식사 시각 추정하기(estimateMealTime) 세 가지만 다룬다.
// 설정값은 데이터계약 「설정」 시트 CFG-072~CFG-082와 같다.

export const MEAL_TIME_CONFIG = Object.freeze({
  intervalMinutes: 60,                 // CFG-072 버튼 간격
  roundDownMinutes: 10,                // CFG-073 답한 시각 내림 단위
  stopAt: { BREAKFAST: 9 * 60, LUNCH: 14 * 60, DINNER: 21 * 60 },     // CFG-074~076 선택지 상한 시각
  questionStart: { BREAKFAST: 10 * 60, LUNCH: 12 * 60, DINNER: 16 * 60 }, // 선택지 하한 시각(점심 12시 · 저녁 4시, CFG-090)
  mealStart: { BREAKFAST: 6 * 60, LUNCH: 11 * 60, DINNER: 16 * 60, YESTERDAY_DINNER: 17 * 60, LATE_DINNER: 17 * 60 },  // CFG-077 끼니 시작 기본값(저녁 4시)
  breakfastBounds: [7 * 60, 8 * 60], breakfastEnd: 10 * 60,   // CFG-078 아침 고정 경계 · 「8시 이후」 범위 끝(아침 끝 기본값 10시)
  mealEnd: { BREAKFAST: 10 * 60, LUNCH: 14 * 60, DINNER: 23 * 60 },   // CFG-091 끼니를 늦어도 먹는 시각. 끝이 없는 「…이후」 칸은 여기까지로 본다
  dinnerFixedBounds: [19 * 60, 21 * 60], dinnerFixedEnd: 23 * 60,   // CFG-089 저녁 고정 선택지 경계(9시 뒤 답 · 어제 저녁)
  maxWindowMinutes: 120,               // CFG-081 범위 상한(안전장치)
  postMealMinutes: 30,                 // CFG-082 식후 걸음을 보는 시간
});

export const MEAL_TIME_QUESTION = Object.freeze({
  LUNCH: { question_id: 'DIET-Q-08', template: '{끼니}은 언제쯤 드셨어요?' },
  DINNER: { question_id: 'DIET-Q-08', template: '{끼니}은 언제쯤 드셨어요?' },
  LATE_DINNER: { question_id: 'DIET-Q-11', template: '저녁은 몇 시쯤 드셨어요?' },
  BREAKFAST: { question_id: 'DIET-Q-09', template: '아침은 몇 시쯤 드셨어요?' },
  YESTERDAY_DINNER: { question_id: 'DIET-Q-10', template: '어제 저녁은 몇 시쯤 드셨어요?' },
});

const MEAL_KO = { BREAKFAST: '아침', LUNCH: '점심', DINNER: '저녁', LATE_DINNER: '저녁', YESTERDAY_DINNER: '어제 저녁' };

const localMinutes = (instant, timeZone) => {
  const date = instant instanceof Date ? instant : new Date(instant);
  if (Number.isNaN(date.getTime())) throw new TypeError('유효한 시각이 필요합니다');
  const parts = new Intl.DateTimeFormat('en-US', { timeZone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
    .formatToParts(date);
  const v = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  return Number(v.hour) * 60 + Number(v.minute);
};

export const toHHMM = (m) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;

// 「오후 1:10」 표기. 자정은 「오전 12:00」, 정오는 「오후 12:00」.
export function formatKoTime(m) {
  const h = Math.floor(m / 60) % 24, mm = m % 60;
  const ap = h < 12 ? '오전' : '오후';
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return { ampm: ap, clock: `${h12}:${String(mm).padStart(2, '0')}`, text: `${ap} ${h12}:${String(mm).padStart(2, '0')}` };
}

/** ① 시각 단계를 물을지. 「못 먹거나 거름」 · 건강 앱 식사 기록이 있으면 묻지 않는다.
 *    어제 저녁(00~10시 진입)도 묻는다 — 일상안정이 최근 7일의 식후 행동을 합산하므로 어제 값도 쓰인다. 고정 선택지(DIET-Q-10). */
export function askMealTime({ mealType, isYesterdayDinner = false, fixedOptionCode, hasHealthAppRecord = false, answeredAtMinutes = null }, config = MEAL_TIME_CONFIG) {
  let key = isYesterdayDinner ? 'YESTERDAY_DINNER' : mealType;
  // 저녁은 오후 9시(선택지 상한)가 지나서 답하면 고정 선택지 질문(DIET-Q-11)으로 바꾼다 — 1시간 칸 3개로는 5시 식사와 10시 식사를 다 덮을 수 없어서
  if (key === 'DINNER' && answeredAtMinutes != null && (answeredAtMinutes - (answeredAtMinutes % config.roundDownMinutes)) > config.stopAt.DINNER) key = 'LATE_DINNER';
  if (fixedOptionCode === 'very_little_or_skipped') return { ask: false, skipReason: 'MEAL_SKIPPED' };
  if (hasHealthAppRecord) return { ask: false, skipReason: 'HEALTH_APP_RECORD' };
  if (!MEAL_TIME_QUESTION[key]) return { ask: false, skipReason: 'UNKNOWN_MEAL' };
  return { ask: true, skipReason: null, question_id: MEAL_TIME_QUESTION[key].question_id, mealKey: key };
}

/**
 * ② 버튼 3개. 점심·저녁은 답한 시각을 10분 단위로 내린 뒤 1시간씩 거꾸로 센다.
 *    끼니별 선택지 상한 시각(점심 14시 · 저녁 21시)을 넘으면 그 시각에 답한 것과 같은 선택지를 보여 주고,
 *    질문이 열리는 시각(점심 12시 · 저녁 17시) 아래로는 내려가지 않는다. 상한 · 하한에 걸린 동안은 작은 글씨(sub)를 뺀다.
 *    아침은 7시 · 8시, 어제 저녁은 저녁 7시 · 8시 정각으로 고정이다(mealType 'YESTERDAY_DINNER').
 *  반환: { question_id, text, options:[{option_code, label(큰 글자), sub(작은 글자), time_label, ampm, clock, window_start, window_end}], stopped }
 */
export function mealTimeOptions(instant, timeZone, mealType, config = MEAL_TIME_CONFIG) {
  const q = MEAL_TIME_QUESTION[mealType];
  if (!q) throw new RangeError(`시각 단계가 없는 끼니: ${mealType}`);
  const answeredAt = localMinutes(instant, timeZone);
  const text = q.template.replace('{끼니}', MEAL_KO[mealType]);

  // 저녁 9시 뒤에 답하거나 어제 저녁이면 고정 선택지 「7시 이전 / 7시~9시 / 9시 이후」
  const lateDinner = mealType === 'DINNER' && (answeredAt - (answeredAt % config.roundDownMinutes)) > config.stopAt.DINNER;
  if (mealType === 'YESTERDAY_DINNER' || mealType === 'LATE_DINNER' || lateDinner) {
    const qq = mealType === 'YESTERDAY_DINNER' ? q : MEAL_TIME_QUESTION.LATE_DINNER;
    const [b1, b2] = config.dinnerFixedBounds, end = config.dinnerFixedEnd;
    const h = (m) => `${m / 60 - 12}시`;
    return {
      question_id: qq.question_id, text: qq.template, stopped: true, fixed: true, answered_at: toHHMM(answeredAt),
      options: [
        { option_code: 'before_7', label: `${h(b1)} 이전`, sub: '', time_label: `${h(b1)} 이전`, ampm: '', clock: `${h(b1)} 이전`, window_start: toHHMM(config.mealStart.LATE_DINNER), window_end: toHHMM(b1) },
        { option_code: 'seven_to_nine', label: `${h(b1)}~${h(b2)}`, sub: '', time_label: `${h(b1)}~${h(b2)}`, ampm: '', clock: `${h(b1)}~${h(b2)}`, window_start: toHHMM(b1), window_end: toHHMM(b2) },
        { option_code: 'after_9', label: `${h(b2)} 이후`, sub: '', time_label: `${h(b2)} 이후`, ampm: '', clock: `${h(b2)} 이후`, window_start: toHHMM(b2), window_end: toHHMM(end), anchor_time: toHHMM(b2) },   // 「9시 이후」는 9시에 먹은 것으로 봄
      ],
    };
  }
  if (mealType === 'BREAKFAST') {
    const [b1, b2] = config.breakfastBounds;
    const h = (m) => `${m / 60}시`;
    return {
      question_id: q.question_id, text, stopped: true, answered_at: toHHMM(answeredAt),
      options: [
        { option_code: 'before_7', label: `${h(b1)} 이전`, sub: '', time_label: `${h(b1)} 이전`, ampm: '', clock: `${h(b1)} 이전`, window_start: toHHMM(config.mealStart.BREAKFAST), window_end: toHHMM(b1) },
        { option_code: 'seven_to_eight', label: `${h(b1)}~${h(b2)}`, sub: '', time_label: `${h(b1)}~${h(b2)}`, ampm: '', clock: `${h(b1)}~${h(b2)}`, window_start: toHHMM(b1), window_end: toHHMM(b2) },
        { option_code: 'after_8', label: `${h(b2)} 이후`, sub: '', time_label: `${h(b2)} 이후`, ampm: '', clock: `${h(b2)} 이후`, window_start: toHHMM(b2), window_end: toHHMM(config.breakfastEnd) },
      ],
    };
  }

  const step = config.intervalMinutes;
  const floored = answeredAt - (answeredAt % config.roundDownMinutes);
  const stop = config.stopAt[mealType], start = config.questionStart[mealType];
  let t0 = floored - step;                 // 1번 버튼 「t0 이후」
  let stopped = false;
  if (floored > stop) { t0 = stop - step; stopped = true; }   // 선택지 상한 시각을 넘으면 그 시각에 답한 것과 같은 선택지를 보여 줌
  if (t0 < start) { t0 = start; stopped = true; }              // 질문 시작 시각 아래로 내려가지 않음
  const t1 = t0 - step;
  const f0 = formatKoTime(t0), f1 = formatKoTime(t1);
  const rangeAmpm = f0.ampm === f1.ampm ? f0.ampm : `${f1.ampm}~${f0.ampm}`;
  const windowEnd1 = toHHMM(Math.min(answeredAt, config.mealEnd[mealType]));   // 1번 선택지의 끝은 답한 시각. 단 끼니를 늦어도 먹는 시각(CFG-091)을 넘지 않는다
  // 선택지 글자: 평소에는 「1시간 이내 / 1~2시간 전 / 그보다 전」만 보여 준다(작은 글씨 없음).
  // 상한 · 하한에 걸린 동안은 「1시간 이내」가 사실과 달라지므로 시각 글자(time_label)를 대신 보여 준다.
  const REL = ['1시간 이내', '1~2시간 전', '그보다 전'];
  const times = [`${f0.text} 이후`, `${rangeAmpm} ${f1.clock}~${f0.clock}`, `${f1.text} 이전`];
  // 상한 · 하한에 걸린 선택지는 늘 정각이라 「1시 이후 / 12시~1시 사이 / 12시 이전」처럼 시만 쓴다. 점심 시간대라 오전 · 오후는 붙이지 않는다
  const hr = (m) => (Math.floor(m / 60) % 12) || 12;
  const STOP = [`${hr(t0)}시 이후`, `${hr(t1)}시~${hr(t0)}시 사이`, `${hr(t1)}시 이전`];
  const lab = (i) => stopped ? STOP[i] : REL[i];
  const subOf = (i) => '';   // 작은 글씨는 쓰지 않는다. time_label은 저장·답변 보기용
  return {
    question_id: q.question_id, text, stopped, answered_at: toHHMM(answeredAt),
    options: [
      { option_code: 'within_1h', label: lab(0), sub: subOf(0), time_label: times[0], ampm: f0.ampm, clock: `${f0.clock} 이후`, window_start: toHHMM(t0), window_end: windowEnd1 },
      { option_code: 'one_to_two_h', label: lab(1), sub: subOf(1), time_label: times[1], ampm: rangeAmpm, clock: `${f1.clock}~${f0.clock}`, window_start: toHHMM(t1), window_end: toHHMM(t0) },
      { option_code: 'earlier', label: lab(2), sub: subOf(2), time_label: times[2], ampm: f1.ampm, clock: `${f1.clock} 이전`, window_start: toHHMM(config.mealStart[mealType]), window_end: toHHMM(t1) },
    ],
  };
}

const hhmmToMin = (s) => { const [h, m] = s.split(':').map(Number); return h * 60 + m; };

/**
 * ③ 추정 시각. 두 단계뿐이다.
 *    1) 그 끼니 시간대 안에 건강 앱 식사 기록이 있으면 그 시각(HIGH). 이때는 시각 단계를 묻지 않는다.
 *    2) 없으면 고른 선택지 범위의 가운데(MEDIUM). 범위는 끼니 시작 기본값보다 이른 부분을 잘라 내고,
 *       끝이 없는 「…이후」 칸은 끼니 끝 기본값(CFG-091)까지로 본다. 「9시 이후」처럼 기준 시각이 있는 칸은 그 시각.
 *    식후 걸음을 볼 시간: 건강 앱이면 그 시각부터 30분, 가운데값이면 범위 전체 + 30분.
 *    범위가 비어 있으면 모름(UNKNOWN) — 계산에서 빠질 뿐 점수를 깎지 않는다.
 *    (걸음 단서 · 지난 2주 평소 시각은 1차에서 쓰지 않는다. 끼니 구분이 안 되는 기록으로는 믿을 만한 값이 나오지 않아서다.)
 */
export function estimateMealTime({ mealType, option, healthAppTime = null }, config = MEAL_TIME_CONFIG) {
  if (healthAppTime) {
    const t = hhmmToMin(healthAppTime);
    return { estimated_time: toHHMM(t), estimate_method: 'HEALTH_APP', confidence: 'HIGH',
      post_meal_window: [toHHMM(t), toHHMM(t + config.postMealMinutes)], window: null };
  }
  if (!option) return { estimated_time: null, estimate_method: 'UNKNOWN', confidence: 'UNKNOWN', post_meal_window: null, window: null };
  const ws = Math.max(hhmmToMin(option.window_start), config.mealStart[mealType] ?? 0);
  let we = hhmmToMin(option.window_end);
  const window = [toHHMM(ws), toHHMM(we)];
  if (we - ws <= 0) return { estimated_time: null, estimate_method: 'UNKNOWN', confidence: 'UNKNOWN', post_meal_window: null, window };
  if (we - ws > config.maxWindowMinutes) we = ws + config.maxWindowMinutes;   // 안전장치. 끼니 끝 기본값 덕에 보통 걸리지 않는다
  const mid = option.anchor_time ? hhmmToMin(option.anchor_time) : ws + Math.round((we - ws) / 2 / 10) * 10;
  return { estimated_time: toHHMM(mid), estimate_method: 'WINDOW_MIDPOINT', confidence: 'MEDIUM',
    post_meal_window: [toHHMM(ws), toHHMM(we + config.postMealMinutes)], window };
}

/**
 * ④ 식후 행동 판정(계약 R-12 · CFG-086~088).
 *    계산식 전달 문서 v7.0은 「어떤 행동을 식후 행동으로 볼지는 서비스가 정하고, 계산기는 완료 · 미완료 · 모름만 받는다」고 한다.
 *    서비스는 걸음 기록으로 판정한다. 식후 관찰 시간 안에
 *      - 5분 넘게 이어 걸었거나(분당 20보 이상)      → COMPLETED (basis STEP_STREAK)
 *      - 합계 300보 이상이거나                         → COMPLETED (basis STEP_TOTAL)
 *      - 운동 기록이 시작됐으면                        → COMPLETED (basis WORKOUT)
 *    아니면 NOT_COMPLETED. 식사 시각이 모름이거나 관찰 시간에 걸음 기록이 비어 있으면 UNKNOWN.
 *  입력: postMealWindow ['HH:MM','HH:MM'] | null, stepsPerMinute [{time:'HH:MM', steps:n}], workoutStarts ['HH:MM']
 */
export const POST_MEAL_ACTION_CONFIG = Object.freeze({
  streakMinutes: 5, streakStepsPerMinute: 20, totalSteps: 300,
});
export function judgePostMealAction({ postMealWindow, stepsPerMinute = [], workoutStarts = [] }, config = POST_MEAL_ACTION_CONFIG) {
  if (!postMealWindow) return { action: 'UNKNOWN', basis: 'NO_MEAL_TIME' };
  const [ws, we] = postMealWindow.map(hhmmToMin);
  const inWindow = stepsPerMinute.filter((r) => { const t = hhmmToMin(r.time); return t >= ws && t < we; });
  if (workoutStarts.some((t) => { const m = hhmmToMin(t); return m >= ws && m < we; })) return { action: 'COMPLETED', basis: 'WORKOUT' };
  if (inWindow.length === 0) return { action: 'UNKNOWN', basis: 'NO_STEP_DATA' };
  let streak = 0, best = 0;
  for (const r of inWindow.slice().sort((a, b) => hhmmToMin(a.time) - hhmmToMin(b.time))) {
    streak = r.steps >= config.streakStepsPerMinute ? streak + 1 : 0;
    best = Math.max(best, streak);
  }
  if (best > config.streakMinutes) return { action: 'COMPLETED', basis: 'STEP_STREAK' };
  const total = inWindow.reduce((s, r) => s + r.steps, 0);
  if (total >= config.totalSteps) return { action: 'COMPLETED', basis: 'STEP_TOTAL' };
  return { action: 'NOT_COMPLETED', basis: 'BELOW_THRESHOLD' };
}

/** 진행 번호. 시각 단계도 질문 1개로 센다(식사 1/5 → 시각 2/5). */
export function questionCountWithMealTime(baseCount, asked) {
  return asked ? baseCount + 1 : baseCount;
}
