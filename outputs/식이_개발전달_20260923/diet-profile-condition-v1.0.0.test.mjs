import test from 'node:test';
import assert from 'node:assert/strict';
import { PROFILE_CONDITIONS, normalizeManualConditionSelection, resolveDietDiseaseContext } from './diet-profile-condition-v1.0.0.mjs';

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
];
const banNatureRows = [
  { rule_id: 'DX-01', nature_code: 'FAST' },
  { rule_id: 'DX-05', nature_code: 'INCREASE' },
  { rule_id: 'DX-05', nature_code: 'REDUCE' },
  { rule_id: 'DX-06', nature_code: 'FLUID' },
];
const run = (manual, clinicStates = []) => resolveDietDiseaseContext({
  manual, clinicStates, diseaseRules, axisRows, banNatureRows,
});

test('공개 내정보의 12개 선택 항목은 중복 코드 없이 정의된다', () => {
  assert.equal(PROFILE_CONDITIONS.length, 12);
  assert.equal(new Set(PROFILE_CONDITIONS.map(x => x.code)).size, 12);
  assert.equal(PROFILE_CONDITIONS.filter(x => x.dietStatus === 'MAPPED').length, 5);
});

test('직접 입력과 미입력, 해당 없음은 서로 다른 상태다', () => {
  assert.deepEqual(normalizeManualConditionSelection([]), { state: 'UNANSWERED', codes: [] });
  assert.deepEqual(normalizeManualConditionSelection([], true), { state: 'NONE', codes: [] });
  assert.throws(() => normalizeManualConditionSelection(['DIABETES'], true), /동시에/);
  assert.throws(() => normalizeManualConditionSelection(['UNKNOWN_CODE']), /정의되지 않은/);
});

test('사용자 입력 당뇨병과 신장질환은 연결 축과 금지 성격을 합쳐 적용한다', () => {
  const out = run({ state: 'SELECTED', codes: ['DIABETES', 'CHRONIC_KIDNEY_DISEASE'] });
  assert.deepEqual(out.linkRuleIds, ['DX-01', 'DX-05']);
  assert.deepEqual(out.banRuleIds, ['DX-01', 'DX-05']);
  assert.deepEqual(out.bannedNatures, ['FAST', 'INCREASE', 'REDUCE']);
  assert.deepEqual(out.axisQuestionIds, ['DIET-Q-01', 'DIET-Q-03']);
});

test('매핑되지 않은 선택은 저장 대상이지만 임의의 식이 규칙이 되지 않는다', () => {
  const out = run({ state: 'SELECTED', codes: ['OBESITY', 'HEART_DISEASE', 'GOUT'] });
  assert.deepEqual(out.linkRuleIds, []);
  assert.deepEqual(out.bannedNatures, []);
  assert.deepEqual(out.notMapped, [
    { code: 'OBESITY', status: 'UNMAPPED' },
    { code: 'HEART_DISEASE', status: 'NEEDS_SUBTYPE' },
    { code: 'GOUT', status: 'UNMAPPED' },
  ]);
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
