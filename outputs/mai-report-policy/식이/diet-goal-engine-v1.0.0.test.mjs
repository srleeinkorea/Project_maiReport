import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import { addCalendarMonths, isScreeningSignalValid, validScreeningSignals,
  recalculateAxisStage, selectDietGoal } from './diet-goal-engine-v1.0.0.mjs';
import { DIET_REFERENCE } from './diet-reference-config-v1.0.0.mjs';

const diseaseRules = [
  { rule_id: 'DX-01', link_enabled: true, ban_enabled: true },
  { rule_id: 'DX-02', link_enabled: true, ban_enabled: false },
  { rule_id: 'DX-07', link_enabled: true, ban_enabled: false },
];
const axisRows = [
  { rule_id: 'DX-01', question_id: 'DIET-Q-01' },
  { rule_id: 'DX-02', question_id: 'DIET-Q-03' },
  { rule_id: 'DX-07', question_id: 'DIET-Q-07' },
];
const banNatureRows = [{ rule_id: 'DX-01', nature_code: 'FAST' }];
const conditionInput = (manual, clinicStates = []) => ({ manual, clinicStates, diseaseRules, axisRows, banNatureRows });
const row = (phrase_id, question_id, extra = {}) => ({
  phrase_id, phrase_version: '1.0.0', question_id, stage_code: 'INTRO', source_status: '사용', parse_status: 'READY',
  nature_code: null, time_code: 'ANY', calendar_code: 'ANY', context_code: 'ANY', ...extra,
});

test('엔진·JSON·데모가 같은 v1.0.0 참조 설정을 사용한다', async () => {
  const json = JSON.parse(await fs.readFile(new URL('./diet-reference-v1.0.0.json', import.meta.url), 'utf8'));
  assert.deepEqual(json, DIET_REFERENCE);
  assert.deepEqual(DIET_REFERENCE.sourcePriority.map(x => x.code), ['SELF_REPORTED', 'CLINIC_CONFIRMED', 'SCREENING', 'QUESTION']);
});

test('검진 유효기간은 달력 기준 3개월이며 월말을 마지막 날로 맞춘다', () => {
  assert.equal(addCalendarMonths('2026-01-31', 3), '2026-04-30');
  assert.equal(isScreeningSignalValid('2026-01-31', '2026-04-30'), true);
  assert.equal(isScreeningSignalValid('2026-01-31', '2026-05-01'), false);
  assert.equal(isScreeningSignalValid('2026-09-28', '2026-09-27'), false);
});

test('검진 신호는 범주·유효기간을 검사하고 혈당→혈압→콜레스테롤·체중 순으로 정렬한다', () => {
  const out = validScreeningSignals([
    { metric_id: 'BMI', category_code: 'SUSPECT', screening_date: '2026-07-01' },
    { metric_id: 'BP', category_code: 'NORMAL_B', screening_date: '2026-06-28' },
    { metric_id: 'FPG', category_code: 'NORMAL_A', screening_date: '2026-09-01' },
    { metric_id: 'TC', category_code: 'SUSPECT', screening_date: '2026-05-01' },
  ], '2026-09-28');
  assert.deepEqual(out.map(x => x.metric_id), ['BP', 'BMI']);
});

test('직접 선택 축에 통과 후보가 없으면 진료정보 축으로 넘어간다', () => {
  const result = selectDietGoal({
    rows: [
      row('HTN-BLOCKED', 'DIET-Q-03', { parse_status: 'BLOCKED' }),
      row('CLINIC-OK', 'DIET-Q-07'),
      row('GENERAL-OK', 'DIET-Q-01'),
    ],
    instant: '2026-09-28T13:00:00+09:00', timeZone: 'Asia/Seoul',
    conditionInput: conditionInput({ state: 'SELECTED', codes: [{ code: 'HYPERTENSION', selection_order: 1 }] }, [
      { rule_id: 'DX-07', confirmation_state: 'USER_CONFIRMED', effective_at: '2026-09-01' },
    ]),
    axisSnapshots: [{ question_id: 'DIET-Q-01', status_code: 'IMPROVEMENT_NEEDED', valid_answer_count: 2 }],
  });
  assert.equal(result.phrase_id, 'CLINIC-OK');
  assert.equal(result.source_code, 'CLINIC_CONFIRMED');
  assert.deepEqual(result.attempted.map(x => [x.source, x.candidate_count]), [
    ['SELF_REPORTED', 0], ['CLINIC_CONFIRMED', 1],
  ]);
});

test('직접·진료 후보가 없으면 유효 검진을 사용하고 만료되면 일반 질문으로 내려간다', () => {
  const common = {
    rows: [row('SCREEN-BP', 'DIET-Q-03'), row('GENERAL', 'DIET-Q-01')],
    instant: '2026-09-28T13:00:00+09:00', timeZone: 'Asia/Seoul',
    conditionInput: conditionInput({ state: 'UNANSWERED', codes: [] }),
    axisSnapshots: [{ question_id: 'DIET-Q-01', status_code: 'OBSERVING', valid_answer_count: 1 }],
  };
  const valid = selectDietGoal({ ...common, screeningSignals: [{ metric_id: 'BP', category_code: 'NORMAL_B', screening_date: '2026-06-28' }] });
  assert.equal(valid.source_code, 'SCREENING');
  const expired = selectDietGoal({ ...common, screeningSignals: [{ metric_id: 'BP', category_code: 'NORMAL_B', screening_date: '2026-06-27' }] });
  assert.equal(expired.source_code, 'QUESTION');
});

test('금지 성격은 모든 출처 후보에 적용된다', () => {
  const result = selectDietGoal({
    rows: [row('FAST', 'DIET-Q-01', { nature_code: 'FAST' }), row('SAFE', 'DIET-Q-01')],
    instant: '2026-09-28T13:00:00+09:00', timeZone: 'Asia/Seoul',
    conditionInput: conditionInput({ state: 'SELECTED', codes: ['DIABETES'] }),
  });
  assert.equal(result.phrase_id, 'SAFE');
});

test('일반 목표도 최근 30일 미노출 문구를 먼저 쓰고 모두 썼으면 가장 오래된 문구로 순환한다', () => {
  const rows = [row('VEG-01', 'DIET-Q-01'), row('VEG-02', 'DIET-Q-01'), row('VEG-03', 'DIET-Q-01')];
  const common = {
    rows, instant: '2026-09-28T13:00:00+09:00', timeZone: 'Asia/Seoul',
    conditionInput: conditionInput({ state: 'UNANSWERED', codes: [] }),
    axisSnapshots: [{ question_id: 'DIET-Q-01', status_code: 'IMPROVEMENT_NEEDED', valid_answer_count: 2 }],
  };
  assert.equal(selectDietGoal(common).phrase_id, 'VEG-01');
  assert.equal(selectDietGoal({ ...common, recentPhraseIdsNewestFirst: ['VEG-01'] }).phrase_id, 'VEG-02');
  assert.equal(selectDietGoal({ ...common, recentPhraseIdsNewestFirst: ['VEG-02', 'VEG-01'] }).phrase_id, 'VEG-03');
  assert.equal(selectDietGoal({ ...common, recentPhraseIdsNewestFirst: ['VEG-03', 'VEG-02', 'VEG-01'] }).phrase_id, 'VEG-01');
});

test('명절 목표는 전달된 명절 날짜에만 후보가 된다', () => {
  const common = {
    rows: [row('HOLIDAY', 'DIET-Q-01', { calendar_code: 'HOLIDAY' })],
    instant: '2026-09-28T13:00:00+09:00', timeZone: 'Asia/Seoul',
    conditionInput: conditionInput({ state: 'UNANSWERED', codes: [] }),
    axisSnapshots: [{ question_id: 'DIET-Q-01', status_code: 'IMPROVEMENT_NEEDED', valid_answer_count: 2 }],
  };
  assert.equal(selectDietGoal(common).goal_state, 'GUIDANCE_ONLY');
  assert.equal(selectDietGoal({ ...common, holidayDates: ['2026-09-28'] }).phrase_id, 'HOLIDAY');
});

test('단계는 미완료 2건을 먼저 하락시키고 7일 완료 3건이면 한 단계만 상승한다', () => {
  const down = recalculateAxisStage({ currentStage: 'CHALLENGE', lastChangedDate: '2026-09-20', asOfDate: '2026-09-28', goals: [
    { session_date: '2026-09-26', completed: false }, { session_date: '2026-09-27', completed: false },
    { session_date: '2026-09-25', completed: true }, { session_date: '2026-09-24', completed: true }, { session_date: '2026-09-23', completed: true },
  ] });
  assert.deepEqual(down, { stage: 'BASE', changed: true, reason: 'TWO_CONSECUTIVE_MISSES' });
  const up = recalculateAxisStage({ currentStage: 'INTRO', lastChangedDate: '2026-09-20', asOfDate: '2026-09-28', goals: [
    { session_date: '2026-09-23', completed: true }, { session_date: '2026-09-24', completed: true },
    { session_date: '2026-09-25', completed: true }, { session_date: '2026-09-26', completed: false },
  ] });
  assert.deepEqual(up, { stage: 'BASE', changed: true, reason: 'THREE_COMPLETIONS_IN_7_DAYS' });
});
