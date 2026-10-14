export const DIET_REFERENCE = Object.freeze({
  version: '1.0.0',
  screeningValidityMonths: 3,
  goalRecentWindowDays: 30,
  exposureConditions: Object.freeze({
    timeCodes: Object.freeze(['ANY', 'MORNING_ENTRY', 'AFTERNOON_ENTRY', 'EVENING', 'PRE_MIDNIGHT']),
    calendarCodes: Object.freeze(['ANY', 'WEEKDAY', 'WEEKEND', 'HOLIDAY', 'HOLIDAY_OR_EXTENDED']),
    contextCodes: Object.freeze(['ANY']),
  }),
  sourcePriority: Object.freeze([
    { order: 1, code: 'SELF_REPORTED', label: '직접 선택' },
    { order: 2, code: 'CLINIC_CONFIRMED', label: '진료정보 확인' },
    { order: 3, code: 'SCREENING', label: '건강검진 신호' },
    { order: 4, code: 'QUESTION', label: '일반 식이 질문' },
  ]),
  screeningPriority: Object.freeze(['FPG', 'BP', 'TC', 'BMI']),
  screeningAxis: Object.freeze({ FPG: 'DIET-Q-01', BP: 'DIET-Q-03', TC: 'DIET-Q-07', BMI: 'DIET-Q-05' }),
  stages: Object.freeze(['INTRO', 'BASE', 'CHALLENGE']),
  stageLabels: Object.freeze({ INTRO: '입문', BASE: '기본', CHALLENGE: '도전' }),
});
