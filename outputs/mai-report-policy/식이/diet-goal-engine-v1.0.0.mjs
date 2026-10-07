import { resolveDietDiseaseContext } from './diet-profile-condition-v1.0.0.mjs';
import { calendarEligible, sessionDateAt, selectLeastRecentlyShown } from './diet-selection-v1.0.0.mjs';
import { DIET_REFERENCE } from './diet-reference-config-v1.0.0.mjs';

export const STAGES = DIET_REFERENCE.stages;
export const SCREENING_PRIORITY = DIET_REFERENCE.screeningPriority;
export const SCREENING_AXIS = DIET_REFERENCE.screeningAxis;

const isoDate = value => {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new TypeError(`YYYY-MM-DD 날짜가 필요합니다: ${value}`);
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== value) throw new TypeError(`유효한 날짜가 필요합니다: ${value}`);
  return value;
};

export function addCalendarMonths(value, months) {
  const source = isoDate(value);
  if (!Number.isInteger(months) || months < 0) throw new TypeError('개월 수는 0 이상의 정수여야 합니다');
  const [year, month, day] = source.split('-').map(Number);
  const first = new Date(Date.UTC(year, month - 1 + months, 1));
  const lastDay = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate();
  return `${first.getUTCFullYear()}-${String(first.getUTCMonth() + 1).padStart(2, '0')}-${String(Math.min(day, lastDay)).padStart(2, '0')}`;
}

export function isScreeningSignalValid(screeningDate, selectionDate, validityMonths = DIET_REFERENCE.screeningValidityMonths) {
  const screened = isoDate(screeningDate);
  const selected = isoDate(selectionDate);
  return screened <= selected && selected <= addCalendarMonths(screened, validityMonths);
}

export function validScreeningSignals(signals, selectionDate, validityMonths = DIET_REFERENCE.screeningValidityMonths) {
  return signals
    .filter(signal => ['NORMAL_B', 'SUSPECT'].includes(signal.category_code))
    .filter(signal => signal.screening_date && isScreeningSignalValid(signal.screening_date, selectionDate, validityMonths))
    .filter(signal => SCREENING_AXIS[signal.metric_id])
    .sort((a, b) => SCREENING_PRIORITY.indexOf(a.metric_id) - SCREENING_PRIORITY.indexOf(b.metric_id));
}

const shiftDate = (value, days) => {
  const date = new Date(`${isoDate(value)}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
};

const statusRank = status => ({ IMPROVEMENT_NEEDED: 0, OBSERVING: 1, NORMAL: 2, GOOD: 3 }[status] ?? 9);

const STAGE_UP_RECENT_GOALS = 4;
const STAGE_UP_MIN_COMPLETED = 3;
const STAGE_UP_MIN_ENDED = 3;
const STAGE_DOWN_CONSECUTIVE_INCOMPLETE = 2;
const STAGE_LOOKBACK_DAYS = 56;
const NON_STAGE_GOAL_STATES = ['GUIDANCE_ONLY', 'RECOVERY', 'BURDEN_REDUCTION'];

export function recalculateAxisStage({ currentStage = 'INTRO', lastChangedDate, goals = [], asOfDate }) {
  if (!STAGES.includes(currentStage)) throw new Error(`알 수 없는 목표 단계: ${currentStage}`);
  const today = isoDate(asOfDate);
  const windowStart = shiftDate(today, -STAGE_LOOKBACK_DAYS);
  const afterChange = goal => !lastChangedDate || goal.session_date > lastChangedDate;
  // 실제 행동 목표가 생성된 기록만 단계 계산에 사용한다.
  // 안내만·회복·부담 줄이기 목표는 사용자가 수행할 행동 목표가 아니므로 미완료나 완료 수에 세지 않는다.
  const countsForStage = goal => !NON_STAGE_GOAL_STATES.includes(goal.goal_state) && goal.completion_counts_for_stage !== false;
  const ended = goals.filter(goal => countsForStage(goal) && goal.session_date < today && goal.session_date >= windowStart && afterChange(goal)).sort((a, b) => b.session_date.localeCompare(a.session_date));
  const consecutiveMisses = ended.slice(0, STAGE_DOWN_CONSECUTIVE_INCOMPLETE).length === STAGE_DOWN_CONSECUTIVE_INCOMPLETE
    && ended.slice(0, STAGE_DOWN_CONSECUTIVE_INCOMPLETE).every(goal => goal.completed !== true);
  const recent = ended.slice(0, STAGE_UP_RECENT_GOALS);
  const completed = recent.filter(goal => goal.completed === true).length;
  const upReady = recent.length >= STAGE_UP_MIN_ENDED && completed >= STAGE_UP_MIN_COMPLETED;
  const index = STAGES.indexOf(currentStage);
  if (consecutiveMisses && index > 0) return { stage: STAGES[index - 1], changed: true, reason: 'TWO_CONSECUTIVE_MISSES' };
  if (upReady && index < STAGES.length - 1) return { stage: STAGES[index + 1], changed: true, reason: 'THREE_OF_RECENT_FOUR_COMPLETED' };
  return { stage: currentStage, changed: false, reason: null };
}

const dateParts = (instant, timeZone) => {
  const date = instant instanceof Date ? instant : new Date(instant);
  if (Number.isNaN(date.getTime())) throw new TypeError('유효한 시각이 필요합니다');
  const parts = Object.fromEntries(new Intl.DateTimeFormat('en-US', {
    timeZone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23', weekday: 'short',
  }).formatToParts(date).map(({ type, value }) => [type, value]));
  return { date: `${parts.year}-${parts.month}-${parts.day}`, hour: Number(parts.hour), weekday: parts.weekday };
};

function rowEligible(row, { instant, timeZone, bannedNatures, holidayDates = [], extendedHolidayDates = [] }) {
  const local = dateParts(instant, timeZone);
  if (row.source_status !== '사용' || row.parse_status !== 'READY' || bannedNatures.has(row.nature_code)) return false;
  const weekday = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].indexOf(local.weekday);
  if (!calendarEligible(row.calendar_code, local.date, weekday, { holidayDates, extendedHolidayDates })) return false;
  if (row.time_code === 'MORNING_ENTRY' && !(local.hour >= 4 && local.hour < 10)) return false;
  if (row.time_code === 'AFTERNOON_ENTRY' && !(local.hour >= 12 && local.hour < 17)) return false;
  if (row.time_code === 'EVENING' && !(local.hour >= 17 || local.hour < 4)) return false;
  if (row.time_code === 'PRE_MIDNIGHT' && !(local.hour >= 17 && local.hour < 24)) return false;
  if (row.time_code && !['ANY', 'MORNING_ENTRY', 'AFTERNOON_ENTRY', 'EVENING', 'PRE_MIDNIGHT'].includes(row.time_code)) return false;
  return true;
}

function axisCandidates(context, axisRows, screeningSignals, axisSnapshots, selectionDate, generalQuestionIds) {
  const byRule = new Map();
  for (const row of axisRows) {
    if (!byRule.has(row.rule_id)) byRule.set(row.rule_id, []);
    byRule.get(row.rule_id).push(row.question_id);
  }
  const candidates = [];
  context.linkRuleSources.forEach(({ ruleId, source }) => {
    for (const questionId of byRule.get(ruleId) ?? []) candidates.push({ source, rule_id: ruleId, question_id: questionId });
  });
  for (const signal of validScreeningSignals(screeningSignals, selectionDate)) {
    candidates.push({ source: 'SCREENING', metric_id: signal.metric_id, question_id: SCREENING_AXIS[signal.metric_id] });
  }
  [...axisSnapshots].sort((a, b) => statusRank(a.status_code) - statusRank(b.status_code)
    || (a.valid_answer_count ?? 0) - (b.valid_answer_count ?? 0)
    || String(a.last_asked_date ?? '').localeCompare(String(b.last_asked_date ?? ''))
    || a.question_id.localeCompare(b.question_id))
    .forEach(row => candidates.push({ source: 'QUESTION', question_id: row.question_id }));
  for (const questionId of generalQuestionIds) candidates.push({ source: 'QUESTION', question_id: questionId });
  const seen = new Set();
  return candidates.filter(item => {
    const key = `${item.source}:${item.question_id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function selectDietGoal({ rows, instant, timeZone, conditionInput, screeningSignals = [], axisSnapshots = [], axisStages = {}, holidayDates = [], extendedHolidayDates = [], recentPhraseIdsNewestFirst = [] }) {
  const selectionDate = sessionDateAt(instant, timeZone);
  const context = resolveDietDiseaseContext(conditionInput);
  const bannedNatures = new Set(context.bannedNatures);
  const generalQuestionIds = [...new Set(rows.map(row => row.question_id ?? row.axis_question_id).filter(Boolean))];
  const axes = axisCandidates(context, conditionInput.axisRows, screeningSignals, axisSnapshots, selectionDate, generalQuestionIds);
  const attempted = [];
  for (const axis of axes) {
    const stage = axisStages[axis.question_id] ?? 'INTRO';
    const eligible = rows.filter(row => (row.question_id ?? row.axis_question_id) === axis.question_id)
      .filter(row => !row.stage_code || row.stage_code === stage)
      .filter(row => rowEligible(row, { instant, timeZone, bannedNatures, holidayDates, extendedHolidayDates }));
    attempted.push({ ...axis, stage, candidate_count: eligible.length });
    if (eligible.length) {
      const selected = selectLeastRecentlyShown(eligible, recentPhraseIdsNewestFirst);
      return { goal_state: 'CREATED', phrase_id: selected.phrase_id, phrase_version: selected.phrase_version,
        question_id: axis.question_id, stage_code: stage, source_code: axis.source, session_date: selectionDate,
        condition_context: context, attempted };
    }
  }
  return { goal_state: 'GUIDANCE_ONLY', phrase_id: null, session_date: selectionDate, condition_context: context, attempted };
}
