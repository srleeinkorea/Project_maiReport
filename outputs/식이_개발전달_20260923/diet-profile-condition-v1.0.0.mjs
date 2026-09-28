// 내정보의 자가 입력 질환을 식이 규칙에 연결하는 참조 구현.
// 병원 진료정보의 진단 후보/사용자 확인 기록과 별도로 보관한다.

export const PROFILE_CONDITIONS = Object.freeze([
  { code: 'HYPERTENSION', label: '고혈압', ruleId: 'DX-02', dietStatus: 'MAPPED' },
  { code: 'DIABETES', label: '당뇨병', ruleId: 'DX-01', dietStatus: 'MAPPED' },
  { code: 'DYSLIPIDEMIA', label: '이상지질혈증', ruleId: 'DX-03', dietStatus: 'MAPPED' },
  { code: 'CHRONIC_KIDNEY_DISEASE', label: '만성 신장질환', ruleId: 'DX-05', dietStatus: 'MAPPED' },
  { code: 'OBESITY', label: '비만', ruleId: null, dietStatus: 'UNMAPPED' },
  { code: 'FATTY_LIVER', label: '지방간', ruleId: 'DX-07', dietStatus: 'MAPPED' },
  { code: 'GERD', label: '위식도역류병', ruleId: null, dietStatus: 'UNMAPPED' },
  { code: 'GOUT', label: '통풍', ruleId: null, dietStatus: 'UNMAPPED' },
  { code: 'THYROID_DISEASE', label: '갑상선 질환', ruleId: null, dietStatus: 'UNMAPPED' },
  { code: 'HEART_DISEASE', label: '심장질환', ruleId: null, dietStatus: 'NEEDS_SUBTYPE' },
  { code: 'CEREBROVASCULAR_DISEASE', label: '뇌혈관질환', ruleId: null, dietStatus: 'NEEDS_SUBTYPE' },
  { code: 'CHRONIC_LUNG_DISEASE', label: '천식 · 만성 폐질환', ruleId: null, dietStatus: 'UNMAPPED' },
]);

const byCode = new Map(PROFILE_CONDITIONS.map(row => [row.code, row]));

export function normalizeManualConditionSelection(codes, noneSelected = false) {
  if (!Array.isArray(codes)) throw new TypeError('질환 코드는 배열이어야 합니다');
  const selected = [...new Set(codes)];
  const unknown = selected.filter(code => !byCode.has(code));
  if (unknown.length) throw new Error(`정의되지 않은 질환 코드: ${unknown.join(', ')}`);
  if (noneSelected && selected.length) throw new Error('질환 없음과 질환 선택을 동시에 저장할 수 없습니다');
  return {
    state: noneSelected ? 'NONE' : selected.length ? 'SELECTED' : 'UNANSWERED',
    codes: selected,
  };
}

// clinicStates는 진료정보 경로에서 확정된 원본 상태이며, 이 함수는 그 행을 수정하지 않는다.
export function resolveDietDiseaseContext({ manual, clinicStates = [], diseaseRules, axisRows, banNatureRows }) {
  const selection = normalizeManualConditionSelection(manual?.codes ?? [], manual?.state === 'NONE');
  if (manual?.state === 'SELECTED' && !selection.codes.length) throw new Error('선택 상태에 질환 코드가 없습니다');
  const rules = new Map(diseaseRules.map(row => [row.rule_id, row]));
  const axis = new Map();
  const bans = new Map();
  for (const row of axisRows) {
    if (!axis.has(row.rule_id)) axis.set(row.rule_id, new Set());
    axis.get(row.rule_id).add(row.question_id);
  }
  for (const row of banNatureRows) {
    if (!bans.has(row.rule_id)) bans.set(row.rule_id, new Set());
    bans.get(row.rule_id).add(row.nature_code);
  }
  const linkRuleIds = new Set();
  const banRuleIds = new Set();
  const clinicByRule = new Map();
  for (const entry of clinicStates) {
    if (clinicByRule.has(entry.rule_id)) throw new Error(`진료정보 질환 상태 중복: ${entry.rule_id}`);
    clinicByRule.set(entry.rule_id, entry.confirmation_state);
    const rule = rules.get(entry.rule_id);
    if (!rule) throw new Error(`알 수 없는 질환 규칙: ${entry.rule_id}`);
    if (entry.confirmation_state === 'CANDIDATE' && rule.ban_enabled) banRuleIds.add(entry.rule_id);
    else if (entry.confirmation_state === 'USER_CONFIRMED') {
      if (rule.link_enabled) linkRuleIds.add(entry.rule_id);
      if (rule.ban_enabled) banRuleIds.add(entry.rule_id);
    } else if (!['DENIED', 'UNKNOWN'].includes(entry.confirmation_state)) {
      throw new Error(`알 수 없는 확인 상태: ${entry.confirmation_state}`);
    }
  }
  const notMapped = [];
  const conflicts = [];
  for (const code of selection.codes) {
    const item = byCode.get(code);
    if (item.dietStatus !== 'MAPPED') { notMapped.push({ code, status: item.dietStatus }); continue; }
    const rule = rules.get(item.ruleId);
    if (!rule) throw new Error(`매핑된 질환 규칙 없음: ${item.ruleId}`);
    if (clinicByRule.get(item.ruleId) === 'DENIED') conflicts.push(code);
    if (rule.link_enabled) linkRuleIds.add(item.ruleId);
    if (rule.ban_enabled) banRuleIds.add(item.ruleId);
  }
  const bannedNatures = new Set([...banRuleIds].flatMap(id => [...(bans.get(id) ?? [])]));
  const axisQuestionIds = new Set([...linkRuleIds].flatMap(id => [...(axis.get(id) ?? [])]));
  return {
    manualState: selection.state,
    linkRuleIds: [...linkRuleIds].sort(),
    banRuleIds: [...banRuleIds].sort(),
    axisQuestionIds: [...axisQuestionIds].sort(),
    bannedNatures: [...bannedNatures].sort(),
    notMapped,
    conflicts,
  };
}
