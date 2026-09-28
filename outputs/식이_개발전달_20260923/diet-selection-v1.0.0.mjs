// 식이 데이터계약 v1.0.0의 날짜·응답 재사용·식후 후보 선정 참조 구현.
// 호출자는 목표문구와 노출조건을 phrase_id/phrase_version으로 결합해 전달한다.

const dateParts = (instant, timeZone) => {
  const date = instant instanceof Date ? instant : new Date(instant);
  if (Number.isNaN(date.getTime())) throw new TypeError('유효한 시각이 필요합니다');
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone, year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(date);
  const value = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  return { date: `${value.year}-${value.month}-${value.day}`, hour: Number(value.hour), minute: Number(value.minute) };
};

const shiftDate = (isoDate, days) => {
  const date = new Date(`${isoDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
};

export function sessionDateAt(instant, timeZone) {
  const local = dateParts(instant, timeZone);
  return local.hour < 4 ? shiftDate(local.date, -1) : local.date;
}

export function mealAt(instant, timeZone) {
  const local = dateParts(instant, timeZone);
  const sessionDate = local.hour < 4 ? shiftDate(local.date, -1) : local.date;
  if (local.hour < 10) return {
    sessionDate, mealDate: shiftDate(local.date, -1), mealType: 'DINNER', label: '어제 저녁',
  };
  if (local.hour < 12) return { sessionDate, mealDate: local.date, mealType: 'BREAKFAST', label: '오늘 아침' };
  if (local.hour < 17) return { sessionDate, mealDate: local.date, mealType: 'LUNCH', label: '오늘 점심' };
  return { sessionDate, mealDate: local.date, mealType: 'DINNER', label: '오늘 저녁' };
}

export function currentAnswer(answers, key) {
  const matches = answers.filter(a => a.is_current === true &&
    a.user_id === key.user_id && a.meal_date === key.meal_date &&
    a.meal_type === key.meal_type && a.question_id === key.question_id &&
    a.question_version === key.question_version);
  if (matches.length > 1) throw new Error('같은 끼니·질문의 유효 응답이 중복되었습니다');
  return matches[0] ?? null;
}

export function questionStateFromExistingAnswer(answers, key, slotCode) {
  const answer = currentAnswer(answers, key);
  return {
    user_id: key.user_id, session_date: key.session_date, slot_code: slotCode,
    question_id: key.question_id, question_version: key.question_version,
    meal_date: key.meal_date, meal_type: key.meal_type,
    state_code: answer ? 'ANSWERED' : 'PENDING',
    effective_answer_id: answer?.answer_id ?? null,
  };
}

export function afterDinnerCandidates(rows, instant, timeZone, bannedNatures = []) {
  const local = dateParts(instant, timeZone);
  if (!(local.hour >= 17 || local.hour < 4)) return [];
  const weekday = new Date(`${local.date}T00:00:00Z`).getUTCDay();
  const banned = new Set(bannedNatures);
  return rows.filter(row => {
    if (row.source_status !== '사용' || row.after_dinner_eligible !== true || row.parse_status !== 'READY') return false;
    if (row.time_code !== 'EVENING' || banned.has(row.nature_code)) return false;
    if (row.context_code !== 'ANY') return false;
    if (row.calendar_code === 'ANY') return true;
    if (row.calendar_code === 'WEEKEND') return weekday === 0 || weekday === 6;
    if (row.calendar_code === 'WEEKDAY') return weekday >= 1 && weekday <= 5;
    return false; // 명절·연휴는 판정 자료가 없으므로 보류한다.
  });
}

export function selectAfterDinnerGoal(rows, instant, timeZone, bannedNatures = []) {
  const candidates = afterDinnerCandidates(rows, instant, timeZone, bannedNatures);
  if (!candidates.length) return { goal_state: 'GUIDANCE_ONLY', phrase_id: null };
  const selected = [...candidates].sort((a, b) => a.phrase_id.localeCompare(b.phrase_id))[0];
  return { goal_state: 'CREATED', phrase_id: selected.phrase_id,
    phrase_version: selected.phrase_version,
    session_date: sessionDateAt(instant, timeZone), target_meal_date: sessionDateAt(instant, timeZone), target_meal_type: 'TONIGHT' };
}
