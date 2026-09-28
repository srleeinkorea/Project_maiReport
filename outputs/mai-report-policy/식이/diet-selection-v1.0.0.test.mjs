import test from 'node:test';
import assert from 'node:assert/strict';
import {
  sessionDateAt, mealAt, currentAnswer, questionStateFromExistingAnswer,
  questionPlan, afterDinnerCandidates, selectAfterDinnerGoal,
} from './diet-selection-v1.0.0.mjs';

const KST = 'Asia/Seoul';
const at = (day, time) => `${day}T${time}+09:00`;

test('식사 질문 경계는 뒤 구간에 포함하고 04시 이전은 전날 세션이다', () => {
  const cases = [
    ['2026-09-23', '00:00', '2026-09-22', '2026-09-22', 'DINNER'],
    ['2026-09-23', '03:59', '2026-09-22', '2026-09-22', 'DINNER'],
    ['2026-09-23', '04:00', '2026-09-23', '2026-09-22', 'DINNER'],
    ['2026-09-23', '09:59', '2026-09-23', '2026-09-22', 'DINNER'],
    ['2026-09-23', '10:00', '2026-09-23', '2026-09-23', 'BREAKFAST'],
    ['2026-09-23', '12:00', '2026-09-23', '2026-09-23', 'LUNCH'],
    ['2026-09-23', '17:00', '2026-09-23', '2026-09-23', 'DINNER'],
  ];
  for (const [day, time, sessionDate, mealDate, mealType] of cases) {
    const actual = mealAt(at(day, time), KST);
    assert.equal(actual.sessionDate, sessionDate, time);
    assert.equal(actual.mealDate, mealDate, time);
    assert.equal(actual.mealType, mealType, time);
    assert.equal(sessionDateAt(at(day, time), KST), sessionDate, time);
  }
});

test('04시 새 세션에서도 같은 어제 저녁 답은 재질문하지 않는다', () => {
  const existing = [{
    answer_id: 'A-1', user_id: 'U-1', meal_date: '2026-09-22',
    meal_type: 'DINNER', question_id: 'DIET-Q-01', question_version: '1.0.0',
    is_current: true,
  }];
  const key = {
    user_id: 'U-1', session_date: '2026-09-23', meal_date: '2026-09-22',
    meal_type: 'DINNER', question_id: 'DIET-Q-01', question_version: '1.0.0',
  };
  assert.equal(currentAnswer(existing, key)?.answer_id, 'A-1');
  assert.deepEqual(questionStateFromExistingAnswer(existing, key, 'MORNING'), {
    ...key, slot_code: 'MORNING', state_code: 'ANSWERED', effective_answer_id: 'A-1',
  });
  assert.equal(questionStateFromExistingAnswer([], key, 'MORNING').state_code, 'PENDING');
  assert.throws(() => currentAnswer([...existing, existing[0]], key), /중복/);
});

test('질환 확인 질문이 있는 날도 식이 질문은 최대 2개다', () => {
  assert.deepEqual(questionPlan(), ['FIXED', 'ROTATING']);
  assert.deepEqual(questionPlan({ hasPendingClinicConfirmation: true }), ['CLINIC_CONFIRMATION']);
  assert.deepEqual(questionPlan({ hasPendingClinicConfirmation: true, confirmationAnswer: 'USER_CONFIRMED' }),
    ['CLINIC_CONFIRMATION', 'DISEASE_ROTATING']);
  assert.deepEqual(questionPlan({ hasPendingClinicConfirmation: true, confirmationAnswer: 'DENIED' }),
    ['CLINIC_CONFIRMATION', 'FIXED']);
  assert.deepEqual(questionPlan({ hasPendingClinicConfirmation: true, confirmationAnswer: 'UNKNOWN' }),
    ['CLINIC_CONFIRMATION', 'FIXED']);
});

test('식후 주말 조건은 04시 세션 날짜가 아닌 실제 행동 날짜를 따른다', () => {
  const row = (id, calendar) => ({
    phrase_id: id, phrase_version: '1.0.0', source_status: '사용',
    after_dinner_eligible: true, parse_status: 'READY',
    time_code: 'EVENING', context_code: 'ANY', calendar_code: calendar,
    nature_code: 'PREP',
  });
  const rows = [row('WEEKDAY', 'WEEKDAY'), row('WEEKEND', 'WEEKEND')];
  const when = at('2026-09-26', '01:00'); // 토요일 01시, 금요일 세션
  assert.equal(sessionDateAt(when, KST), '2026-09-25');
  assert.deepEqual(afterDinnerCandidates(rows, when, KST).map(x => x.phrase_id), ['WEEKEND']);
  assert.deepEqual(selectAfterDinnerGoal(rows, when, KST), {
    goal_state: 'CREATED', phrase_id: 'WEEKEND', phrase_version: '1.0.0',
    session_date: '2026-09-25', target_meal_date: '2026-09-25', target_meal_type: 'TONIGHT',
  });
});

test('식후 시간 밖·금지 성격·판정 불가·후보 없음은 자동 생성하지 않는다', () => {
  const base = {
    phrase_id: 'P', phrase_version: '1.0.0', source_status: '사용',
    after_dinner_eligible: true, parse_status: 'READY', time_code: 'EVENING',
    context_code: 'ANY', calendar_code: 'ANY', nature_code: 'PREP',
  };
  const evening = at('2026-09-23', '18:00');
  assert.equal(afterDinnerCandidates([base], at('2026-09-23', '16:59'), KST).length, 0);
  assert.equal(afterDinnerCandidates([base], evening, KST, ['PREP']).length, 0);
  assert.equal(afterDinnerCandidates([{ ...base, parse_status: 'BLOCKED' }], evening, KST).length, 0);
  assert.equal(afterDinnerCandidates([{ ...base, calendar_code: 'HOLIDAY' }], evening, KST).length, 0);
  assert.equal(afterDinnerCandidates([{ ...base, calendar_code: 'HOLIDAY' }], evening, KST, [], {
    holidayDates: ['2026-09-23'],
  }).length, 1);
  assert.deepEqual(selectAfterDinnerGoal([], evening, KST), {
    goal_state: 'GUIDANCE_ONLY', phrase_id: null,
  });
  const nextDayWording = { ...base, phrase_id: 'NEXT-DAY', time_code: 'PRE_MIDNIGHT' };
  assert.equal(afterDinnerCandidates([nextDayWording], evening, KST).length, 1);
  assert.equal(afterDinnerCandidates([nextDayWording], at('2026-09-24', '01:00'), KST).length, 0);
});

test('명절·연휴 문구는 백엔드 날짜 목록이 있을 때만 노출한다', () => {
  const base = {
    phrase_id: 'HOLIDAY', phrase_version: '1.0.0', source_status: '사용',
    after_dinner_eligible: true, parse_status: 'READY', time_code: 'EVENING',
    calendar_code: 'HOLIDAY_OR_EXTENDED', nature_code: null,
  };
  const evening = at('2026-10-03', '20:00');
  assert.equal(afterDinnerCandidates([base], evening, KST).length, 0);
  assert.equal(afterDinnerCandidates([base], evening, KST, [], {
    extendedHolidayDates: ['2026-10-03'],
  }).length, 1);
});

test('식후 목표는 최근 30일 노출이 없는 문구부터 돌고 모두 썼으면 가장 오래된 문구를 고른다', () => {
  const rows = ['DIET-P-0131', 'DIET-P-0156', 'DIET-P-0226'].map(phrase_id => ({
    phrase_id, phrase_version: '1.0.0', source_status: '사용', after_dinner_eligible: true,
    parse_status: 'READY', time_code: 'EVENING', context_code: 'ANY', calendar_code: 'ANY', nature_code: null,
  }));
  const evening = at('2026-09-23', '20:00');
  assert.equal(selectAfterDinnerGoal(rows, evening, KST).phrase_id, 'DIET-P-0131');
  assert.equal(selectAfterDinnerGoal(rows, evening, KST, [], ['DIET-P-0131']).phrase_id, 'DIET-P-0156');
  assert.equal(selectAfterDinnerGoal(rows, evening, KST, [], ['DIET-P-0156', 'DIET-P-0131']).phrase_id, 'DIET-P-0226');
  assert.equal(selectAfterDinnerGoal(rows, evening, KST, [], ['DIET-P-0226', 'DIET-P-0156', 'DIET-P-0131']).phrase_id, 'DIET-P-0131');
});
