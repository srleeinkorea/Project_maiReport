import test from 'node:test';
import assert from 'node:assert/strict';
import { askMealTime, mealTimeOptions, estimateMealTime, formatKoTime, judgePostMealAction } from './diet-meal-time-v1.0.0.mjs';

const minutesOf = (start, n, steps) => Array.from({ length: n }, (_, i) => {
  const m = Number(start.slice(0, 2)) * 60 + Number(start.slice(3)) + i;
  return { time: `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`, steps };
});

test('식후 행동 판정(A안) · 5분 넘게 이어 걷기 · 300보 · 운동 기록 · 모름', () => {
  const win = ['12:00', '13:30'];
  assert.deepEqual(judgePostMealAction({ postMealWindow: win, stepsPerMinute: minutesOf('12:55', 10, 60) }), { action: 'COMPLETED', basis: 'STEP_STREAK' });
  assert.deepEqual(judgePostMealAction({ postMealWindow: win, stepsPerMinute: [...minutesOf('12:10', 4, 90), ...minutesOf('12:40', 86, 0)] }), { action: 'COMPLETED', basis: 'STEP_TOTAL' });
  assert.deepEqual(judgePostMealAction({ postMealWindow: win, stepsPerMinute: minutesOf('12:00', 90, 2) }), { action: 'NOT_COMPLETED', basis: 'BELOW_THRESHOLD' });
  assert.deepEqual(judgePostMealAction({ postMealWindow: win, stepsPerMinute: minutesOf('12:00', 90, 0), workoutStarts: ['12:40'] }), { action: 'COMPLETED', basis: 'WORKOUT' });
  assert.deepEqual(judgePostMealAction({ postMealWindow: win, stepsPerMinute: minutesOf('14:00', 30, 80) }), { action: 'UNKNOWN', basis: 'NO_STEP_DATA' });
  assert.deepEqual(judgePostMealAction({ postMealWindow: null, stepsPerMinute: minutesOf('12:00', 90, 80) }), { action: 'UNKNOWN', basis: 'NO_MEAL_TIME' });
  // 정확히 5분은 「넘게」가 아니므로 이어 걷기 기준 미달, 합계 100보라 미완료
  assert.equal(judgePostMealAction({ postMealWindow: win, stepsPerMinute: [...minutesOf('12:10', 5, 20), ...minutesOf('12:15', 60, 0)] }).action, 'NOT_COMPLETED');
});

const KST = 'Asia/Seoul';
const at = (time) => `2026-10-14T${time}:00+09:00`;
const labels = (r) => r.options.map(o => o.time_label || o.label);
const mains = (r) => r.options.map(o => o.label);
const subs = (r) => r.options.map(o => o.sub);

test('못 먹거나 거름 · 건강 앱 기록에는 시각을 묻지 않고, 어제 저녁은 고정 선택지로 묻는다', () => {
  assert.deepEqual(askMealTime({ mealType: 'DINNER', isYesterdayDinner: true, fixedOptionCode: 'usual' }), { ask: true, skipReason: null, question_id: 'DIET-Q-10', mealKey: 'YESTERDAY_DINNER' });
  const y = mealTimeOptions(at('08:20'), KST, 'YESTERDAY_DINNER');
  assert.equal(y.text, '어제 저녁은 몇 시쯤 드셨어요?');
  assert.deepEqual(y.options.map(o => o.label), ['7시 이전', '7시~9시', '9시 이후']);
  assert.deepEqual(y.options.map(o => [o.window_start, o.window_end]), [['17:00', '19:00'], ['19:00', '21:00'], ['21:00', '23:00']]);
  assert.equal(estimateMealTime({ mealType: 'YESTERDAY_DINNER', option: y.options[0] }).estimated_time, '18:00');
  assert.equal(estimateMealTime({ mealType: 'YESTERDAY_DINNER', option: y.options[2] }).estimated_time, '21:00');   // 9시 이후는 9시로
  assert.equal(askMealTime({ mealType: 'LUNCH', fixedOptionCode: 'very_little_or_skipped' }).skipReason, 'MEAL_SKIPPED');
  assert.equal(askMealTime({ mealType: 'LUNCH', fixedOptionCode: 'usual', hasHealthAppRecord: true }).skipReason, 'HEALTH_APP_RECORD');
  assert.deepEqual(askMealTime({ mealType: 'LUNCH', fixedOptionCode: 'less' }), { ask: true, skipReason: null, question_id: 'DIET-Q-08', mealKey: 'LUNCH' });
  assert.equal(askMealTime({ mealType: 'BREAKFAST', fixedOptionCode: 'usual' }).question_id, 'DIET-Q-09');
});

test('점심 · 답한 시각에서 1시간씩 거꾸로 세고 10분 단위로 내린다', () => {
  const r = mealTimeOptions(at('13:20'), KST, 'LUNCH');
  assert.equal(r.text, '점심은 언제쯤 드셨어요?');
  assert.deepEqual(labels(r), ['오후 12:20 이후', '오전~오후 11:20~12:20', '오전 11:20 이전']);
  assert.deepEqual(mains(r), ['1시간 이내', '1~2시간 전', '그보다 전']);
  assert.deepEqual(subs(r), ['', '', '']);   // 작은 글씨 없음
  assert.deepEqual(labels(mealTimeOptions(at('13:47'), KST, 'LUNCH')), ['오후 12:40 이후', '오전~오후 11:40~12:40', '오전 11:40 이전']);
  assert.equal(r.options[0].window_end, '13:20');
  assert.equal(mealTimeOptions(at('14:10'), KST, 'LUNCH').options[0].window_end, '14:00');   // 끼니 끝 기본값에서 자름
});

test('점심 · 12시대에는 12시 아래로 내려가지 않고, 오후 2시가 지나면 정각에서 멈춘다', () => {
  const early = mealTimeOptions(at('12:20'), KST, 'LUNCH');
  assert.deepEqual(labels(early), ['오후 12:00 이후', '오전~오후 11:00~12:00', '오전 11:00 이전']);
  assert.deepEqual(mains(early), ['오후 12:00 이후', '오전~오후 11:00~12:00', '오전 11:00 이전']);   // 하한에 걸리면 시각 글자를 크게
  assert.deepEqual(subs(early), ['', '', '']);
  const noon1 = mealTimeOptions(at('13:00'), KST, 'LUNCH');
  assert.deepEqual(labels(noon1), ['오후 12:00 이후', '오전~오후 11:00~12:00', '오전 11:00 이전']);
  assert.equal(noon1.stopped, false);
  for (const t of ['14:10', '16:30']) {
    const r = mealTimeOptions(at(t), KST, 'LUNCH');
    assert.deepEqual(labels(r), ['오후 1:00 이후', '오후 12:00~1:00', '오후 12:00 이전'], t);
    assert.deepEqual(mains(r), ['오후 1:00 이후', '오후 12:00~1:00', '오후 12:00 이전'], t);   // 상한에 걸리면 「1시간 이내」 대신 시각
    assert.equal(r.stopped, true, t);
  }
});

test('저녁 · 오후 9시까지는 1시간 칸(하한 4시), 9시가 지나면 고정 선택지 「7시 이전 / 7시~9시 / 9시 이후」', () => {
  assert.deepEqual(labels(mealTimeOptions(at('19:30'), KST, 'DINNER')), ['오후 6:30 이후', '오후 5:30~6:30', '오후 5:30 이전']);
  assert.deepEqual(mains(mealTimeOptions(at('19:30'), KST, 'DINNER')), ['1시간 이내', '1~2시간 전', '그보다 전']);
  assert.deepEqual(labels(mealTimeOptions(at('20:40'), KST, 'DINNER')), ['오후 7:40 이후', '오후 6:40~7:40', '오후 6:40 이전']);
  // 하한 4시: 5시 40분에 답하면 「1~2시간 전」이 3:40~4:40이라 4시 반 식사가 들어간다(범위는 4시부터 잘라 4:00~4:40 → 4:20)
  const five = mealTimeOptions(at('17:40'), KST, 'DINNER');
  assert.deepEqual(labels(five), ['오후 4:40 이후', '오후 3:40~4:40', '오후 3:40 이전']);
  assert.equal(estimateMealTime({ mealType: 'DINNER', option: five.options[1] }).estimated_time, '16:20');
  const nine = mealTimeOptions(at('21:00'), KST, 'DINNER');
  assert.deepEqual(labels(nine), ['오후 8:00 이후', '오후 7:00~8:00', '오후 7:00 이전']);
  for (const t of ['21:10', '23:30', '23:55']) {
    const r = mealTimeOptions(at(t), KST, 'DINNER');
    assert.equal(r.question_id, 'DIET-Q-11', t);
    assert.equal(r.text, '저녁은 몇 시쯤 드셨어요?', t);
    assert.deepEqual(mains(r), ['7시 이전', '7시~9시', '9시 이후'], t);
    assert.deepEqual(r.options.map(o => [o.window_start, o.window_end]), [['17:00', '19:00'], ['19:00', '21:00'], ['21:00', '23:00']], t);
  }
  assert.equal(askMealTime({ mealType: 'DINNER', fixedOptionCode: 'usual', answeredAtMinutes: 23 * 60 + 30 }).question_id, 'DIET-Q-11');
  assert.equal(askMealTime({ mealType: 'DINNER', fixedOptionCode: 'usual', answeredAtMinutes: 20 * 60 }).question_id, 'DIET-Q-08');
  const lateOpt = mealTimeOptions(at('23:30'), KST, 'DINNER').options;
  assert.equal(estimateMealTime({ mealType: 'LATE_DINNER', option: lateOpt[0] }).estimated_time, '18:00');
  assert.equal(estimateMealTime({ mealType: 'LATE_DINNER', option: lateOpt[2] }).estimated_time, '21:00');
});

test('아침 · 7시 · 8시 정각으로 고정', () => {
  const r = mealTimeOptions(at('10:20'), KST, 'BREAKFAST');
  assert.equal(r.text, '아침은 몇 시쯤 드셨어요?');
  assert.deepEqual(labels(r), ['7시 이전', '7시~8시', '8시 이후']);
  assert.deepEqual(labels(mealTimeOptions(at('11:40'), KST, 'BREAKFAST')), ['7시 이전', '7시~8시', '8시 이후']);
  assert.deepEqual(r.options.map(o => [o.window_start, o.window_end]), [['06:00', '07:00'], ['07:00', '08:00'], ['08:00', '10:00']]);
});

test('추정 · 건강 앱 기록이 있으면 그 시각, 없으면 선택지 범위의 가운데', () => {
  const lunch1300 = mealTimeOptions(at('13:00'), KST, 'LUNCH').options[0];   // 12:00~13:00
  const mid = estimateMealTime({ mealType: 'LUNCH', option: lunch1300 });
  assert.deepEqual([mid.estimated_time, mid.estimate_method, mid.confidence, mid.post_meal_window], ['12:30', 'WINDOW_MIDPOINT', 'MEDIUM', ['12:00', '13:30']]);
  const app = estimateMealTime({ mealType: 'LUNCH', option: lunch1300, healthAppTime: '12:35' });
  assert.deepEqual([app.estimated_time, app.estimate_method, app.confidence, app.post_meal_window], ['12:35', 'HEALTH_APP', 'HIGH', ['12:35', '13:05']]);
  const l1347 = estimateMealTime({ mealType: 'LUNCH', option: mealTimeOptions(at('13:47'), KST, 'LUNCH').options[0] });
  assert.equal(l1347.estimated_time, '13:10');
  // 「…이후」 칸은 끼니 끝 기본값까지: 오후 4:30 점심 「1:00 이후」 = 13:00~14:00 → 13:30
  const late = mealTimeOptions(at('16:30'), KST, 'LUNCH').options[0];
  assert.deepEqual([late.window_start, late.window_end], ['13:00', '14:00']);
  assert.deepEqual([estimateMealTime({ mealType: 'LUNCH', option: late }).estimated_time, estimateMealTime({ mealType: 'LUNCH', option: late }).post_meal_window], ['13:30', ['13:00', '14:30']]);
  // 아침 「8시 이후」 = 08:00~10:00 → 09:00, 「7시 이전」 = 06:00~07:00 → 06:30
  const bf = mealTimeOptions(at('11:40'), KST, 'BREAKFAST').options;
  assert.equal(estimateMealTime({ mealType: 'BREAKFAST', option: bf[2] }).estimated_time, '09:00');
  assert.equal(estimateMealTime({ mealType: 'BREAKFAST', option: bf[0] }).estimated_time, '06:30');
  // 「…이전」은 끼니 시작 기본값부터: 점심 11:00~11:20 → 11:10
  const before = mealTimeOptions(at('13:20'), KST, 'LUNCH').options[2];
  assert.deepEqual([estimateMealTime({ mealType: 'LUNCH', option: before }).window, estimateMealTime({ mealType: 'LUNCH', option: before }).estimated_time], [['11:00', '11:20'], '11:10']);
  // 범위가 비면 모름
  assert.equal(estimateMealTime({ mealType: 'LUNCH', option: { option_code: 'x', window_start: '12:00', window_end: '12:00' } }).confidence, 'UNKNOWN');
});

test('표기 · 오전 · 오후와 12시 처리', () => {
  assert.equal(formatKoTime(0).text, '오전 12:00');
  assert.equal(formatKoTime(12 * 60 + 5).text, '오후 12:05');
  assert.equal(formatKoTime(23 * 60 + 50).text, '오후 11:50');
});
