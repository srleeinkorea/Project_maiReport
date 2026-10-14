// 식이 데이터계약 v1.3.0 · 끼니별 식사 시각 단계(DIET-Q-08 · DIET-Q-09)의 참조 구현.
// 고정 질문(DIET-Q-00)에 답한 바로 뒤 같은 자리에서 「{끼니}은 언제쯤 드셨어요?」를 묻는다.
// 이 파일은 ① 물을지 말지(askMealTime) ② 버튼 3개 만들기(mealTimeOptions)
// ③ 고른 버튼으로 식사 시각 추정하기(estimateMealTime) 세 가지만 다룬다.
// 설정값은 데이터계약 「설정」 시트 CFG-072~CFG-082와 같다.

export const MEAL_TIME_CONFIG = Object.freeze({
  intervalMinutes: 60,                 // CFG-072 버튼 간격
  roundDownMinutes: 10,                // CFG-073 답한 시각 내림 단위
  stopAt: { BREAKFAST: 9 * 60, LUNCH: 14 * 60, DINNER: 21 * 60 },     // CFG-074~076 멈춤 시각
  questionStart: { BREAKFAST: 10 * 60, LUNCH: 12 * 60, DINNER: 17 * 60 }, // 끼니 질문이 열리는 시각(CFG-012~014)
  mealStart: { BREAKFAST: 6 * 60, LUNCH: 11 * 60, DINNER: 17 * 60 },  // CFG-077 끼니 시작 기본값
  breakfastBounds: [7 * 60, 8 * 60],   // CFG-078 아침 고정 경계
  stepPauseMinutes: 15,                // CFG-079 걷다가 멈춘 것으로 보는 최소 시간
  habitWindowDays: 14,                 // CFG-080 평소 식사 시각을 보는 기간
  maxWindowMinutes: 120,               // CFG-081 범위 상한(넘으면 걸음 단서 없을 때 모름)
  postMealMinutes: 30,                 // CFG-082 식후 걸음을 보는 시간
});

export const MEAL_TIME_QUESTION = Object.freeze({
  LUNCH: { question_id: 'DIET-Q-08', template: '{끼니}은 언제쯤 드셨어요?' },
  DINNER: { question_id: 'DIET-Q-08', template: '{끼니}은 언제쯤 드셨어요?' },
  BREAKFAST: { question_id: 'DIET-Q-09', template: '아침은 몇 시쯤 드셨어요?' },
});

const MEAL_KO = { BREAKFAST: '아침', LUNCH: '점심', DINNER: '저녁' };

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

/** ① 시각 단계를 물을지. 어제 저녁 · 「못 먹거나 거름」 · 건강 앱 식사 기록이 있으면 묻지 않는다. */
export function askMealTime({ mealType, isYesterdayDinner = false, fixedOptionCode, hasHealthAppRecord = false }) {
  if (isYesterdayDinner) return { ask: false, skipReason: 'YESTERDAY_DINNER' };
  if (fixedOptionCode === 'very_little_or_skipped') return { ask: false, skipReason: 'MEAL_SKIPPED' };
  if (hasHealthAppRecord) return { ask: false, skipReason: 'HEALTH_APP_RECORD' };
  if (!MEAL_TIME_QUESTION[mealType]) return { ask: false, skipReason: 'UNKNOWN_MEAL' };
  return { ask: true, skipReason: null, question_id: MEAL_TIME_QUESTION[mealType].question_id };
}

/**
 * ② 버튼 3개. 점심·저녁은 답한 시각을 10분 단위로 내린 뒤 1시간씩 거꾸로 센다.
 *    끼니별 멈춤 시각(점심 14시 · 저녁 21시)을 넘으면 그 시각에서 멈추고,
 *    질문이 열리는 시각(점심 12시 · 저녁 17시) 아래로는 내려가지 않는다. 멈추거나 받친 동안은 작은 글씨(sub)를 뺀다.
 *    아침은 항상 7시 · 8시 정각으로 고정이다.
 *  반환: { question_id, text, options:[{option_code, label, ampm, clock, sub, window_start, window_end}], stopped }
 */
export function mealTimeOptions(instant, timeZone, mealType, config = MEAL_TIME_CONFIG) {
  const q = MEAL_TIME_QUESTION[mealType];
  if (!q) throw new RangeError(`시각 단계가 없는 끼니: ${mealType}`);
  const answeredAt = localMinutes(instant, timeZone);
  const text = q.template.replace('{끼니}', MEAL_KO[mealType]);

  if (mealType === 'BREAKFAST') {
    const [b1, b2] = config.breakfastBounds;
    const h = (m) => `${m / 60}시`;
    return {
      question_id: q.question_id, text, stopped: true, answered_at: toHHMM(answeredAt),
      options: [
        { option_code: 'before_7', label: `${h(b1)} 이전`, ampm: '', clock: `${h(b1)} 이전`, sub: '', window_start: toHHMM(config.mealStart.BREAKFAST), window_end: toHHMM(b1) },
        { option_code: 'seven_to_eight', label: `${h(b1)}~${h(b2)}`, ampm: '', clock: `${h(b1)}~${h(b2)}`, sub: '', window_start: toHHMM(b1), window_end: toHHMM(b2) },
        { option_code: 'after_8', label: `${h(b2)} 이후`, ampm: '', clock: `${h(b2)} 이후`, sub: '', window_start: toHHMM(b2), window_end: toHHMM(answeredAt) },
      ],
    };
  }

  const step = config.intervalMinutes;
  const floored = answeredAt - (answeredAt % config.roundDownMinutes);
  const stop = config.stopAt[mealType], start = config.questionStart[mealType];
  let t0 = floored - step;                 // 1번 버튼 「t0 이후」
  let stopped = false;
  if (floored > stop) { t0 = stop - step; stopped = true; }   // 멈춤 시각을 넘으면 정각에서 멈춤
  if (t0 < start) { t0 = start; stopped = true; }              // 질문 시작 시각 아래로 내려가지 않음
  const t1 = t0 - step;
  const f0 = formatKoTime(t0), f1 = formatKoTime(t1);
  const rangeAmpm = f0.ampm === f1.ampm ? f0.ampm : `${f1.ampm}~${f0.ampm}`;
  const windowEnd1 = toHHMM(answeredAt);   // 1번 버튼의 끝은 항상 답한 시각. 멈춘 뒤 2시간을 넘으면 추정에서 모름이 된다
  return {
    question_id: q.question_id, text, stopped, answered_at: toHHMM(answeredAt),
    options: [
      { option_code: 'within_1h', label: `${f0.text} 이후`, ampm: f0.ampm, clock: `${f0.clock} 이후`, sub: stopped ? '' : '1시간 이내', window_start: toHHMM(t0), window_end: windowEnd1 },
      { option_code: 'one_to_two_h', label: `${rangeAmpm} ${f1.clock}~${f0.clock}`, ampm: rangeAmpm, clock: `${f1.clock}~${f0.clock}`, sub: stopped ? '' : '1~2시간 전', window_start: toHHMM(t1), window_end: toHHMM(t0) },
      { option_code: 'earlier', label: `${f1.text} 이전`, ampm: f1.ampm, clock: `${f1.clock} 이전`, sub: stopped ? '' : '그보다 전', window_start: toHHMM(config.mealStart[mealType]), window_end: toHHMM(t1) },
    ],
  };
}

const hhmmToMin = (s) => { const [h, m] = s.split(':').map(Number); return h * 60 + m; };

/**
 * ③ 추정 시각. 세 끼 모두 같은 순서다.
 *    0) 건강 앱 식사 기록이 있으면 그 시각(HIGH)
 *    1) 고른 버튼으로 범위를 정한다(끼니 시작 기본값보다 이른 부분은 잘라 낸다)
 *    2) 범위 안에 15분 넘게 멈춘 걸음 단서가 딱 하나면 그 시각(HIGH)
 *       범위가 2시간을 넘거나 비어 있으면 모름(UNKNOWN)
 *       지난 2주 평소 식사 시각이 범위 안에 있으면 그 시각(MEDIUM)
 *       둘 다 없으면 범위 가운데(MEDIUM)
 *    3) 식후 걸음을 볼 시간: 단서·평소 시각이면 추정 시각부터 30분, 가운데면 범위 전체 + 30분
 *  입력 시각은 모두 'HH:MM' 현지 시각 문자열. 반환의 estimated_time도 같다.
 */
export function estimateMealTime({
  mealType, option, healthAppTime = null, stepPauses = [], habitualTime = null,
}, config = MEAL_TIME_CONFIG) {
  if (healthAppTime) {
    const t = hhmmToMin(healthAppTime);
    return { estimated_time: toHHMM(t), estimate_method: 'HEALTH_APP', confidence: 'HIGH',
      post_meal_window: [toHHMM(t), toHHMM(t + config.postMealMinutes)], window: null };
  }
  if (!option) return { estimated_time: null, estimate_method: 'UNKNOWN', confidence: 'UNKNOWN', post_meal_window: null, window: null };
  let ws = Math.max(hhmmToMin(option.window_start), config.mealStart[mealType]);
  let we = hhmmToMin(option.window_end);
  const window = [toHHMM(ws), toHHMM(we)];
  const length = we - ws;

  const pauses = stepPauses.map(hhmmToMin).filter((t) => t >= ws && t <= we);
  if (pauses.length === 1) {
    return { estimated_time: toHHMM(pauses[0]), estimate_method: 'STEP_PAUSE', confidence: 'HIGH',
      post_meal_window: [toHHMM(pauses[0]), toHHMM(pauses[0] + config.postMealMinutes)], window };
  }
  if (length <= 0 || length > config.maxWindowMinutes) {
    return { estimated_time: null, estimate_method: 'UNKNOWN', confidence: 'UNKNOWN', post_meal_window: null, window };
  }
  if (habitualTime) {
    const h = hhmmToMin(habitualTime);
    if (h >= ws && h <= we) {
      return { estimated_time: toHHMM(h), estimate_method: 'HABIT', confidence: 'MEDIUM',
        post_meal_window: [toHHMM(h), toHHMM(h + config.postMealMinutes)], window };
    }
  }
  const mid = ws + Math.round(length / 2 / 10) * 10;   // 가운데를 10분 단위로
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
