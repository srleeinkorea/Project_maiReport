// 내정보의 자가 입력 질환을 식이 규칙에 연결하는 참조 구현.
// 병원 진료정보의 진단 후보/사용자 확인 기록과 별도로 보관한다.
import { selectAfterDinnerGoal } from './diet-selection-v1.0.0.mjs';

export const PROFILE_CONDITIONS = Object.freeze([
  { code: 'HYPERTENSION', label: '고혈압', ruleId: 'DX-02', dietStatus: 'MAPPED' },
  { code: 'DIABETES', label: '당뇨병', ruleId: 'DX-01', dietStatus: 'MAPPED' },
  { code: 'DYSLIPIDEMIA', label: '이상지질혈증', ruleId: 'DX-03', dietStatus: 'MAPPED' },
  { code: 'CHRONIC_KIDNEY_DISEASE', label: '만성 신장질환', ruleId: 'DX-05', dietStatus: 'SAFETY_ONLY' },
]);

const byCode = new Map(PROFILE_CONDITIONS.map(row => [row.code, row]));

export function normalizeManualConditionSelection(codes, noneSelected = false) {
  if (!Array.isArray(codes)) throw new TypeError('질환 코드는 배열이어야 합니다');
  const normalized = codes.map((item, index) => typeof item === 'string'
    ? { code: item, selection_order: index + 1 }
    : { code: item?.code, selection_order: item?.selection_order ?? index + 1 });
  if (normalized.some(item => !Number.isInteger(item.selection_order) || item.selection_order < 1)) {
    throw new Error('질환 선택 순서는 1 이상의 정수여야 합니다');
  }
  const seenOrders = new Set();
  const seenCodes = new Set();
  const selections = normalized
    .sort((a, b) => a.selection_order - b.selection_order)
    .filter(item => {
      if (seenOrders.has(item.selection_order)) throw new Error(`질환 선택 순서 중복: ${item.selection_order}`);
      seenOrders.add(item.selection_order);
      if (seenCodes.has(item.code)) return false;
      seenCodes.add(item.code);
      return true;
    });
  const selected = selections.map(item => item.code);
  const unknown = selected.filter(code => !byCode.has(code));
  if (unknown.length) throw new Error(`정의되지 않은 질환 코드: ${unknown.join(', ')}`);
  if (noneSelected && selected.length) throw new Error('질환 없음과 질환 선택을 동시에 저장할 수 없습니다');
  return {
    state: noneSelected ? 'NONE' : selected.length ? 'SELECTED' : 'UNANSWERED',
    codes: selected,
    selections,
  };
}

// 같은 질환의 여러 진료 기록은 effective_at(없으면 입력 순서)이 가장 최신인 상태 1건으로 집계한다.
export function aggregateClinicStates(records = []) {
  if (!Array.isArray(records)) throw new TypeError('진료정보 기록은 배열이어야 합니다');
  const allowed = new Set(['CANDIDATE', 'USER_CONFIRMED', 'DENIED', 'UNKNOWN']);
  const byRule = new Map();
  records.forEach((record, index) => {
    if (!record?.rule_id) throw new Error('진료정보 질환 규칙 ID가 없습니다');
    if (!allowed.has(record.confirmation_state)) throw new Error(`알 수 없는 확인 상태: ${record.confirmation_state}`);
    const stamp = record.effective_at ?? record.confirmed_at ?? record.encounter_date ?? '';
    const time = stamp ? Date.parse(stamp) : Number.NaN;
    if (stamp && Number.isNaN(time)) throw new Error(`유효하지 않은 진료정보 시각: ${stamp}`);
    const current = byRule.get(record.rule_id);
    const candidate = { ...record, _time: Number.isNaN(time) ? null : time, _index: index };
    const isLater = !current ||
      (candidate._time !== null && (current._time === null || candidate._time > current._time)) ||
      (candidate._time === current?._time && candidate._index > current._index) ||
      (candidate._time === null && current?._time === null && candidate._index > current._index);
    if (isLater) byRule.set(record.rule_id, candidate);
  });
  return [...byRule.values()].sort((a, b) => a._index - b._index)
    .map(({ _time, _index, ...record }) => record);
}

// clinicStates는 진료정보 경로에서 확정된 원본 상태이며, 이 함수는 그 행을 수정하지 않는다.
export function resolveDietDiseaseContext({ manual, clinicStates = [], diseaseRules, axisRows, banNatureRows }) {
  const selection = normalizeManualConditionSelection(manual?.codes ?? [], manual?.state === 'NONE');
  if (manual?.state === 'SELECTED' && !selection.codes.length) throw new Error('선택 상태에 질환 코드가 없습니다');
  if (manual?.state && !['SELECTED', 'NONE', 'UNANSWERED'].includes(manual.state)) throw new Error(`알 수 없는 직접 입력 상태: ${manual.state}`);
  if (manual?.state && manual.state !== selection.state) throw new Error('직접 입력 상태와 질환 코드가 일치하지 않습니다');
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
  const manualLinkRuleIds = new Set();
  const manualRuleIds = new Set();
  const clinicLinkRuleIds = new Set();
  const banRuleIds = new Set();
  const aggregatedClinicStates = aggregateClinicStates(clinicStates);
  const clinicByRule = new Map();
  for (const entry of aggregatedClinicStates) {
    clinicByRule.set(entry.rule_id, entry.confirmation_state);
    const rule = rules.get(entry.rule_id);
    if (!rule) throw new Error(`알 수 없는 질환 규칙: ${entry.rule_id}`);
    if (entry.confirmation_state === 'CANDIDATE' && rule.ban_enabled) banRuleIds.add(entry.rule_id);
    else if (entry.confirmation_state === 'USER_CONFIRMED') {
      if (rule.link_enabled) clinicLinkRuleIds.add(entry.rule_id);
      if (rule.ban_enabled) banRuleIds.add(entry.rule_id);
    } else if (!['DENIED', 'UNKNOWN'].includes(entry.confirmation_state)) {
      throw new Error(`알 수 없는 확인 상태: ${entry.confirmation_state}`);
    }
  }
  const notMapped = [];
  const conflicts = [];
  for (const code of selection.codes) {
    const item = byCode.get(code);
    if (!['MAPPED', 'SAFETY_ONLY'].includes(item.dietStatus)) { notMapped.push({ code, status: item.dietStatus }); continue; }
    const rule = rules.get(item.ruleId);
    if (!rule) throw new Error(`매핑된 질환 규칙 없음: ${item.ruleId}`);
    manualRuleIds.add(item.ruleId);
    if (clinicByRule.get(item.ruleId) === 'DENIED') conflicts.push(code);
    if (item.dietStatus === 'MAPPED' && rule.link_enabled) manualLinkRuleIds.add(item.ruleId);
    if (rule.ban_enabled) banRuleIds.add(item.ruleId);
  }
  // 목표 축은 직접 선택을 먼저 사용하고, 진료정보는 같은 질환을 중복하지 않고 뒤에 보완한다.
  const linkRuleIds = [
    ...manualLinkRuleIds,
    ...[...clinicLinkRuleIds].filter(id => !manualRuleIds.has(id)),
  ];
  const linkRuleSources = linkRuleIds.map(ruleId => ({
    ruleId,
    source: manualLinkRuleIds.has(ruleId) ? 'SELF_REPORTED' : 'CLINIC_CONFIRMED',
  }));
  const bannedNatures = new Set([...banRuleIds].flatMap(id => [...(bans.get(id) ?? [])]));
  const axisQuestionIds = new Set(linkRuleIds.flatMap(id => [...(axis.get(id) ?? [])]));
  return {
    manualState: selection.state,
    manualSelections: selection.selections,
    clinicStates: aggregatedClinicStates,
    linkRuleIds,
    linkRuleSources,
    banRuleIds: [...banRuleIds].sort(),
    axisQuestionIds: [...axisQuestionIds],
    bannedNatures: [...bannedNatures].sort(),
    notMapped,
    conflicts,
  };
}

export function filterDietCandidatesByCondition(rows, context) {
  const banned = new Set(context.bannedNatures);
  return rows.filter(row => row.source_status === '사용' && row.parse_status === 'READY' && !banned.has(row.nature_code));
}

export function selectAfterDinnerGoalWithConditions(rows, instant, timeZone, conditionInput) {
  const context = resolveDietDiseaseContext(conditionInput);
  return {
    ...selectAfterDinnerGoal(rows, instant, timeZone, context.bannedNatures),
    condition_context: context,
  };
}
