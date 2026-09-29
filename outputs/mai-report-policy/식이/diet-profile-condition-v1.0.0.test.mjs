import test from 'node:test';
import assert from 'node:assert/strict';
import { PROFILE_CONDITIONS, normalizeManualConditionSelection, resolveDietDiseaseContext,
  aggregateClinicStates, filterDietCandidatesByCondition, selectAfterDinnerGoalWithConditions } from './diet-profile-condition-v1.0.0.mjs';

const diseaseRules = [
  { rule_id: 'DX-01', link_enabled: true, ban_enabled: true },
  { rule_id: 'DX-02', link_enabled: true, ban_enabled: false },
  { rule_id: 'DX-03', link_enabled: true, ban_enabled: false },
  { rule_id: 'DX-05', link_enabled: true, ban_enabled: true },
  { rule_id: 'DX-06', link_enabled: true, ban_enabled: true },
  { rule_id: 'DX-07', link_enabled: true, ban_enabled: false },
];
const axisRows = [
  { rule_id: 'DX-01', question_id: 'DIET-Q-01' },
  { rule_id: 'DX-02', question_id: 'DIET-Q-03' },
  { rule_id: 'DX-05', question_id: 'DIET-Q-03' },
  { rule_id: 'DX-07', question_id: 'DIET-Q-07' },
];
const banNatureRows = [
  { rule_id: 'DX-01', nature_code: 'FAST' },
  { rule_id: 'DX-05', nature_code: 'INCREASE' },
  { rule_id: 'DX-05', nature_code: 'REDUCE' },
  { rule_id: 'DX-05', nature_code: 'FLUID' },
  { rule_id: 'DX-06', nature_code: 'FLUID' },
];
const run = (manual, clinicStates = []) => resolveDietDiseaseContext({
  manual, clinicStates, diseaseRules, axisRows, banNatureRows,
});

test('내정보의 4개 선택 항목은 중복 코드 없이 정의된다', () => {
  assert.equal(PROFILE_CONDITIONS.length, 4);
  assert.equal(new Set(PROFILE_CONDITIONS.map(x => x.code)).size, 4);
  assert.equal(PROFILE_CONDITIONS.filter(x => x.dietStatus === 'MAPPED').length, 3);
  assert.equal(PROFILE_CONDITIONS.filter(x => x.dietStatus === 'SAFETY_ONLY').length, 1);
});

test('직접 입력과 미입력, 해당 없음은 서로 다른 상태다', () => {
  assert.deepEqual(normalizeManualConditionSelection([]), { state: 'UNANSWERED', codes: [], selections: [] });
  assert.deepEqual(normalizeManualConditionSelection([], true), { state: 'NONE', codes: [], selections: [] });
  assert.throws(() => normalizeManualConditionSelection(['DIABETES'], true), /동시에/);
  assert.throws(() => normalizeManualConditionSelection(['UNKNOWN_CODE']), /정의되지 않은/);
  assert.throws(() => run({ state: 'UNANSWERED', codes: ['DIABETES'] }), /일치하지/);
  assert.throws(() => run({ state: 'SELECTED', codes: [] }), /선택 상태/);
});

test('질환 선택 순서를 보존하고 중복 순서는 거부한다', () => {
  const out = normalizeManualConditionSelection([
    { code: 'HYPERTENSION', selection_order: 2 },
    { code: 'DIABETES', selection_order: 1 },
  ]);
  assert.deepEqual(out.codes, ['DIABETES', 'HYPERTENSION']);
  assert.throws(() => normalizeManualConditionSelection([
    { code: 'HYPERTENSION', selection_order: 1 },
    { code: 'DIABETES', selection_order: 1 },
  ]), /순서 중복/);
});

test('같은 질환의 여러 진료 기록은 가장 최신 상태로 집계한다', () => {
  assert.deepEqual(aggregateClinicStates([
    { rule_id: 'DX-01', confirmation_state: 'CANDIDATE', effective_at: '2026-01-01' },
    { rule_id: 'DX-01', confirmation_state: 'USER_CONFIRMED', effective_at: '2026-02-01' },
    { rule_id: 'DX-02', confirmation_state: 'DENIED', effective_at: '2026-01-15' },
  ]).map(x => [x.rule_id, x.confirmation_state]), [
    ['DX-01', 'USER_CONFIRMED'], ['DX-02', 'DENIED'],
  ]);
});

test('사용자 입력 당뇨병은 축에 연결하고 신장질환은 안전 제외에만 적용한다', () => {
  const out = run({ state: 'SELECTED', codes: ['DIABETES', 'CHRONIC_KIDNEY_DISEASE'] });
  assert.deepEqual(out.linkRuleIds, ['DX-01']);
  assert.deepEqual(out.banRuleIds, ['DX-01', 'DX-05']);
  assert.deepEqual(out.bannedNatures, ['FAST', 'FLUID', 'INCREASE', 'REDUCE']);
  assert.deepEqual(out.axisQuestionIds, ['DIET-Q-01']);
  assert.deepEqual(out.linkRuleSources, [{ ruleId: 'DX-01', source: 'SELF_REPORTED' }]);
});

test('직접 선택 축을 진료정보 축보다 먼저 반환하고 같은 질환은 중복하지 않는다', () => {
  const out = run({ state: 'SELECTED', codes: ['HYPERTENSION'] }, [
    { rule_id: 'DX-07', confirmation_state: 'USER_CONFIRMED' },
    { rule_id: 'DX-02', confirmation_state: 'USER_CONFIRMED' },
  ]);
  assert.deepEqual(out.linkRuleIds, ['DX-02', 'DX-07']);
  assert.deepEqual(out.axisQuestionIds, ['DIET-Q-03', 'DIET-Q-07']);
  assert.deepEqual(out.linkRuleSources, [
    { ruleId: 'DX-02', source: 'SELF_REPORTED' },
    { ruleId: 'DX-07', source: 'CLINIC_CONFIRMED' },
  ]);
});

test('직접 선택이 없어도 확인된 진료정보 축을 2순위 경로로 사용할 수 있다', () => {
  const out = run({ state: 'UNANSWERED', codes: [] }, [
    { rule_id: 'DX-07', confirmation_state: 'USER_CONFIRMED' },
  ]);
  assert.deepEqual(out.linkRuleIds, ['DX-07']);
  assert.deepEqual(out.linkRuleSources, [{ ruleId: 'DX-07', source: 'CLINIC_CONFIRMED' }]);
});

test('신장질환을 직접 선택하면 같은 진료정보의 신장 축은 중복 연결하지 않는다', () => {
  const out = run({ state: 'SELECTED', codes: ['CHRONIC_KIDNEY_DISEASE'] }, [
    { rule_id: 'DX-05', confirmation_state: 'USER_CONFIRMED' },
  ]);
  assert.deepEqual(out.linkRuleIds, []);
  assert.deepEqual(out.axisQuestionIds, []);
  assert.deepEqual(out.banRuleIds, ['DX-05']);
});

test('선택지 밖의 질환 코드는 수동 입력으로 저장하지 않는다', () => {
  for (const code of ['OBESITY','FATTY_LIVER','GERD','GOUT','THYROID_DISEASE','HEART_DISEASE','CEREBROVASCULAR_DISEASE','CHRONIC_LUNG_DISEASE']) {
    assert.throws(() => run({ state: 'SELECTED', codes: [code] }), /정의되지 않은/);
  }
});

test('해당 없음은 자가 입력만 비우고 진료정보의 진단 후보 금지를 지우지 않는다', () => {
  const out = run({ state: 'NONE', codes: [] }, [
    { rule_id: 'DX-05', confirmation_state: 'CANDIDATE' },
  ]);
  assert.deepEqual(out.banRuleIds, ['DX-05']);
  assert.deepEqual(out.linkRuleIds, []);
});

test('진료정보 부정 기록과 새 자가 선택은 출처를 유지한 채 충돌로 표시한다', () => {
  const out = run({ state: 'SELECTED', codes: ['DIABETES'] }, [
    { rule_id: 'DX-01', confirmation_state: 'DENIED' },
  ]);
  assert.deepEqual(out.conflicts, ['DIABETES']);
  assert.deepEqual(out.linkRuleIds, ['DX-01']);
  assert.deepEqual(out.banRuleIds, ['DX-01']);
});

test('자가 입력의 금지 성격은 목표 후보와 식후 선정에 연결된다', () => {
  const manual = { state: 'SELECTED', codes: ['DIABETES'] };
  const conditionInput = { manual, diseaseRules, axisRows, banNatureRows };
  const rows = [
    { phrase_id: 'FAST', phrase_version: '1.0.0', source_status: '사용', parse_status: 'READY',
      nature_code: 'FAST', after_dinner_eligible: true, time_code: 'EVENING', context_code: 'ANY', calendar_code: 'ANY' },
    { phrase_id: 'PREP', phrase_version: '1.0.0', source_status: '사용', parse_status: 'READY',
      nature_code: null, after_dinner_eligible: true, time_code: 'EVENING', context_code: 'ANY', calendar_code: 'ANY' },
  ];
  const context = resolveDietDiseaseContext(conditionInput);
  assert.deepEqual(filterDietCandidatesByCondition(rows, context).map(x => x.phrase_id), ['PREP']);
  const selected = selectAfterDinnerGoalWithConditions(rows, '2026-09-28T20:00:00+09:00', 'Asia/Seoul', conditionInput);
  assert.equal(selected.phrase_id, 'PREP');
  assert.deepEqual(selected.condition_context.bannedNatures, ['FAST']);
});
