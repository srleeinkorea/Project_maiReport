import test from 'node:test';
import assert from 'node:assert/strict';
import { askMealTime, mealTimeOptions, estimateMealTime, formatKoTime } from './diet-meal-time-v1.0.0.mjs';

const KST = 'Asia/Seoul';
const at = (time) => `2026-10-14T${time}:00+09:00`;
const labels = (r) => r.options.map(o => o.label);
const subs = (r) => r.options.map(o => o.sub);

test('어제 저녁 · 못 먹거나 거름 · 건강 앱 기록에는 시각을 묻지 않는다', () => {
  assert.equal(askMealTime({ mealType: 'DINNER', isYesterdayDinner: true, fixedOptionCode: 'usual' }).ask, false);
  assert.equal(askMealTime({ mealType: 'LUNCH', fixedOptionCode: 'very_little_or_skipped' }).skipReason, 'MEAL_SKIPPED');
  assert.equal(askMealTime({ mealType: 'LUNCH', fixedOptionCode: 'usual', hasHealthAppRecord: true }).skipReason, 'HEALTH_APP_RECORD');
  assert.deepEqual(askMealTime({ mealType: 'LUNCH', fixedOptionCode: 'less' }), { ask: true, skipReason: null, question_id: 'DIET-Q-08' });
  assert.equal(askMealTime({ mealType: 'BREAKFAST', fixedOptionCode: 'usual' }).question_id, 'DIET-Q-09');
});

test('점심 · 답한 시각에서 1시간씩 거꾸로 세고 10분 단위로 내린다', () => {
  const r = mealTimeOptions(at('13:20'), KST, 'LUNCH');
  assert.equal(r.text, '점심은 언제쯤 드셨어요?');
  assert.deepEqual(labels(r), ['오후 12:20 이후', '오전~오후 11:20~12:20', '오전 11:20 이전']);
  assert.deepEqual(subs(r), ['1시간 이내', '1~2시간 전', '그보다 전']);
  assert.deepEqual(labels(mealTimeOptions(at('13:47'), KST, 'LUNCH')), ['오후 12:40 이후', '오전~오후 11:40~12:40', '오전 11:40 이전']);
  assert.equal(r.options[0].window_end, '13:20');
});

test('점심 · 12시대에는 12시 아래로 내려가지 않고, 오후 2시가 지나면 정각에서 멈춘다', () => {
  const early = mealTimeOptions(at('12:20'), KST, 'LUNCH');
  assert.deepEqual(labels(early), ['오후 12:00 이후', '오전~오후 11:00~12:00', '오전 11:00 이전']);
  assert.deepEqual(subs(early), ['', '', '']);
  const noon1 = mealTimeOptions(at('13:00'), KST, 'LUNCH');
  assert.deepEqual(labels(noon1), ['오후 12:00 이후', '오전~오후 11:00~12:00', '오전 11:00 이전']);
  assert.equal(noon1.stopped, false);
  for (const t of ['14:10', '16:30']) {
    const r = mealTimeOptions(at(t), KST, 'LUNCH');
    assert.deepEqual(labels(r), ['오후 1:00 이후', '오후 12:00~1:00', '오후 12:00 이전'], t);
    assert.equal(r.stopped, true, t);
  }
});

test('저녁 · 오후 9시가 지나면 오후 8시 이후에서 멈추고 자정 직전도 내림으로 안전하다', () => {
  assert.deepEqual(labels(mealTimeOptions(at('19:30'), KST, 'DINNER')), ['오후 6:30 이후', '오후 5:30~6:30', '오후 5:30 이전']);
  assert.deepEqual(labels(mealTimeOptions(at('20:40'), KST, 'DINNER')), ['오후 7:40 이후', '오후 6:40~7:40', '오후 6:40 이전']);
  const nine = mealTimeOptions(at('21:00'), KST, 'DINNER');
  assert.deepEqual(labels(nine), ['오후 8:00 이후', '오후 7:00~8:00', '오후 7:00 이전']);
  assert.equal(nine.stopped, false);
  for (const t of ['23:30', '23:55']) {
    assert.deepEqual(labels(mealTimeOptions(at(t), KST, 'DINNER')), ['오후 8:00 이후', '오후 7:00~8:00', '오후 7:00 이전'], t);
  }
  const five = mealTimeOptions(at('17:40'), KST, 'DINNER');
  assert.deepEqual(labels(five), ['오후 5:00 이후', '오후 4:00~5:00', '오후 4:00 이전']);
});

test('아침 · 7시 · 8시 정각으로 고정', () => {
  const r = mealTimeOptions(at('10:20'), KST, 'BREAKFAST');
  assert.equal(r.text, '아침은 몇 시쯤 드셨어요?');
  assert.deepEqual(labels(r), ['7시 이전', '7시~8시', '8시 이후']);
  assert.deepEqual(labels(mealTimeOptions(at('11:40'), KST, 'BREAKFAST')), ['7시 이전', '7시~8시', '8시 이후']);
  assert.deepEqual(r.options.map(o => [o.window_start, o.window_end]), [['06:00', '07:00'], ['07:00', '08:00'], ['08:00', '10:20']]);
});

test('추정 · 범위 가운데 · 걸음 단서 · 평소 시각 · 건강 앱 순서', () => {
  const lunch1300 = mealTimeOptions(at('13:00'), KST, 'LUNCH').options[0];   // 12:00~13:00
  const mid = estimateMealTime({ mealType: 'LUNCH', option: lunch1300 });
  assert.deepEqual([mid.estimated_time, mid.estimate_method, mid.confidence, mid.post_meal_window], ['12:30', 'WINDOW_MIDPOINT', 'MEDIUM', ['12:00', '13:30']]);
  const pause = estimateMealTime({ mealType: 'LUNCH', option: lunch1300, stepPauses: ['12:15'] });
  assert.deepEqual([pause.estimated_time, pause.confidence, pause.post_meal_window], ['12:15', 'HIGH', ['12:15', '12:45']]);
  const habit = estimateMealTime({ mealType: 'LUNCH', option: lunch1300, habitualTime: '12:30' });
  assert.deepEqual([habit.estimated_time, habit.estimate_method], ['12:30', 'HABIT']);
  const app = estimateMealTime({ mealType: 'LUNCH', option: lunch1300, healthAppTime: '12:35' });
  assert.deepEqual([app.estimated_time, app.estimate_method, app.confidence], ['12:35', 'HEALTH_APP', 'HIGH']);
  const l1347 = estimateMealTime({ mealType: 'LUNCH', option: mealTimeOptions(at('13:47'), KST, 'LUNCH').options[0] });
  assert.equal(l1347.estimated_time, '13:10');
});

test('추정 · 범위가 2시간을 넘거나 비면 걸음 단서가 있을 때만 쓴다', () => {
  const late = mealTimeOptions(at('16:30'), KST, 'LUNCH').options[0];       // 13:00~16:30
  assert.equal(estimateMealTime({ mealType: 'LUNCH', option: late }).confidence, 'UNKNOWN');
  assert.equal(estimateMealTime({ mealType: 'LUNCH', option: late, stepPauses: ['14:00'] }).estimated_time, '14:00');
  const bf = mealTimeOptions(at('11:40'), KST, 'BREAKFAST').options[2];     // 08:00~11:40
  assert.equal(estimateMealTime({ mealType: 'BREAKFAST', option: bf }).confidence, 'UNKNOWN');
  assert.equal(estimateMealTime({ mealType: 'BREAKFAST', option: bf, stepPauses: ['09:30'] }).estimated_time, '09:30');
  const bf1020 = mealTimeOptions(at('10:20'), KST, 'BREAKFAST').options[2]; // 08:00~10:20 = 140분
  assert.equal(estimateMealTime({ mealType: 'BREAKFAST', option: bf1020 }).confidence, 'UNKNOWN');
  const early7 = mealTimeOptions(at('10:20'), KST, 'BREAKFAST').options[0];
  assert.equal(estimateMealTime({ mealType: 'BREAKFAST', option: early7 }).estimated_time, '06:30');
  // 오후 5시대 저녁: 2 · 3번 버튼은 끼니 시작(17시)보다 일러 범위가 비어 모름
  const five = mealTimeOptions(at('17:40'), KST, 'DINNER').options;
  assert.equal(estimateMealTime({ mealType: 'DINNER', option: five[1] }).confidence, 'UNKNOWN');
  assert.equal(estimateMealTime({ mealType: 'DINNER', option: five[2] }).confidence, 'UNKNOWN');
  // 「…이전」은 끼니 시작 기본값부터 센다: 점심 11:00~11:20
  const before = mealTimeOptions(at('13:20'), KST, 'LUNCH').options[2];
  assert.deepEqual(estimateMealTime({ mealType: 'LUNCH', option: before }).window, ['11:00', '11:20']);
});

test('표기 · 오전 · 오후와 12시 처리', () => {
  assert.equal(formatKoTime(0).text, '오전 12:00');
  assert.equal(formatKoTime(12 * 60 + 5).text, '오후 12:05');
  assert.equal(formatKoTime(23 * 60 + 50).text, '오후 11:50');
});
