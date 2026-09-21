-- =============================================================================
--  지식DB → maiReport 전달 테이블 추출 스크립트
-- =============================================================================
--  대상 DB : maireport-knowledge
--  실행    : 순수 SQL 이므로 psql · pgAdmin · DBeaver · VS Code 어디서나 그대로 실행된다.
--            (psql 메타명령 \copy \o \echo 을 쓰지 않는다)
--              psql   : psql -h localhost -p 5432 -U postgres -d maireport-knowledge -f 이파일
--              pgAdmin: Query Tool 에 붙여넣고 전체 실행 → 이후 PART 5 의 조회 쿼리를 하나씩 실행
--  산출    : maireport_export 스키마에 조회용 뷰 8개
--            CSV·.sql 파일까지 자동 생성하려면 지식DB_전달테이블_추출_psql_파일생성_claude.sql 을 쓴다
--
--  전제 문서 : 지식코칭_maiReport_전달테이블_설계_claude.md
--
--  이 스크립트가 하는 일
--   1) 지식DB(coaching_line / coaching_condition / fact / measurement_* / requirement)를
--      maiReport 전달용 5개 테이블 모양으로 평탄화한다.
--   2) 같은 뜻의 fact 중복(같은 임계가 근거 문서 수만큼 반복)을 하나로 합친다.
--   3) below / within / above 를 숫자 구간(value_min 이상, value_max 미만)으로 바꾼다.
--
--  이 스크립트가 못 하는 일 (= 아래 map_* 테이블에서 사람이 관리하는 부분)
--   - 지표 이름 짓기            → map_metric
--   - 문구 묶음과 우선순위      → map_rule
--   - 입력 카탈로그와 질문 문장 → map_input
--   - 운영 관찰 창(근거 아닌 값)→ map_window
--   - 출처 표기 문자열          → map_authority
--   지식DB에 없는 정보이므로 이 5개 테이블만 유지보수하면 나머지는 자동 반영된다.
--
--  ⚠️ public 스키마(지식DB 본체)는 읽기만 한다. 쓰기는 maireport_export 스키마 안에서만 일어나며,
--     스크립트 첫 줄이 그 스키마를 DROP/CREATE 하므로 몇 번을 재실행해도 결과가 같다.
-- =============================================================================


BEGIN;

DROP SCHEMA IF EXISTS maireport_export CASCADE;
CREATE SCHEMA maireport_export;
SET search_path TO maireport_export, public;


-- =============================================================================
--  PART 1. 사람이 관리하는 매핑 (지식DB에 없는 정보)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1-1. measurement_target_key + unit  →  maiReport 지표 이름
--      키가 (target, unit) 두 칸인 이유: 같은 target이 단위에 따라 다른 지표가 된다.
--      예) moderate_to_vigorous_intensity_aerobic_activity 는
--          minute_per_week 이면 주간 활동 시간, day_per_week 이면 주간 활동 일수.
-- -----------------------------------------------------------------------------
CREATE TABLE map_metric (
  measurement_target_key text NOT NULL,
  unit                   text NOT NULL,
  metric_key             text NOT NULL,
  PRIMARY KEY (measurement_target_key, unit)
);
INSERT INTO map_metric VALUES
 -- 중강도만
 ('moderate_intensity_activity',                     'minute_per_week', 'moderate_minutes_per_week'),
 ('moderate_intensity_aerobic_activity',             'minute_per_week', 'moderate_minutes_per_week'),
 ('moderate_intensity_physical_activity',            'minute_per_week', 'moderate_minutes_per_week'),
 ('moderate_intensity_aerobic_physical_activity',    'minute_per_week', 'moderate_minutes_per_week'),
 ('moderate_intensity_aerobic_exercise',             'minute_per_week', 'moderate_minutes_per_week'),
 -- 고강도만
 ('vigorous_intensity_activity',                     'minute_per_week', 'vigorous_minutes_per_week'),
 ('vigorous_intensity_physical_activity',            'minute_per_week', 'vigorous_minutes_per_week'),
 ('vigorous_intensity_aerobic_physical_activity',    'minute_per_week', 'vigorous_minutes_per_week'),
 ('vigorous_intensity_aerobic_exercise',             'minute_per_week', 'vigorous_minutes_per_week'),
 -- 중강도 이상(MVPA)
 ('moderate_to_vigorous_intensity_aerobic_activity', 'minute_per_week', 'mvpa_minutes_per_week'),
 ('moderate_to_vigorous_intensity_physical_activity','minute_per_week', 'mvpa_minutes_per_week'),
 ('moderate_to_vigorous_physical_activity',          'minute_per_week', 'mvpa_minutes_per_week'),
 ('aerobic_activity',                                'minute_per_day',  'mvpa_minutes_per_day'),
 ('moderate_to_vigorous_intensity_aerobic_activity', 'day_per_week',    'mvpa_days_per_week'),
 -- 그 밖
 ('days_elapsed_between_exercise_sessions',          'day_interval',    'days_between_exercise_sessions'),
 ('good_quality_sleep',                              'hour_per_day',    'sleep_hours_per_night'),
 ('daily_step_count',                                'step_per_day',    'daily_steps');

-- 1-2. 정수 단위 표시 (원문 부등호를 정수로 옮길 때 쓴다)
--      예) 지식DB (,2] 의 above = "2일 초과" → 정수 단위이므로 value_min = 3
CREATE TABLE map_unit (
  unit         text PRIMARY KEY,
  integer_step integer   -- 정수 단위면 1, 연속 단위면 NULL
);
INSERT INTO map_unit VALUES
 ('minute_per_week', NULL),
 ('minute_per_day',  NULL),
 ('hour_per_day',    NULL),
 ('step_per_day',    1),
 ('day_per_week',    1),
 ('day_interval',    1),
 ('minute_per_bout', NULL);

-- 1-3. 지표별 계산 창과 입력 (지식DB에 없는 운영 정보)
--      eval_window_days / min_observed_days 는 근거 값이 아니다.
--      단 coaching_axis_observation_rule 이 있는 지표는 그 값이 우선한다(PART 2에서 처리).
CREATE TABLE map_window (
  metric_key         text PRIMARY KEY,
  window_kind        text NOT NULL,
  required_input_key text,
  computable_now     boolean NOT NULL,
  eval_window_days   integer NOT NULL,
  min_observed_days  integer NOT NULL,
  display_name       text NOT NULL,
  out_unit           text NOT NULL
);
INSERT INTO map_window VALUES
 ('moderate_minutes_per_week',      'rolling_7d','activity_interval',false, 7,7,'주간 중강도 활동 시간',     'minute'),
 ('vigorous_minutes_per_week',      'rolling_7d','activity_interval',false, 7,7,'주간 고강도 활동 시간',     'minute'),
 ('mvpa_minutes_per_week',          'rolling_7d','activity_interval',false, 7,7,'주간 중강도이상 활동 시간', 'minute'),
 ('mvpa_minutes_per_day',           'day',       'activity_interval',true,  1,1,'하루 중강도이상 활동 시간', 'minute'),
 ('mvpa_days_per_week',             'rolling_7d','activity_interval',false, 7,7,'주간 활동일수',             'day'),
 ('days_between_exercise_sessions', 'event_gap', 'exercise_session', false,14,2,'최근 운동 세션 간격',       'day'),
 ('sleep_hours_per_night',          'night',     'sleep_session',    true,  7,5,'야간 수면 시간',            'hour'),
 ('short_brisk_bouts_per_day',      'day',       'activity_interval',false, 1,1,'짧고 빠른 보행 구간 수',    'count'),
 ('daily_steps',                    'day',       'daily_step_total', true,  1,1,'하루 총 걸음수',            'step');
-- computable_now: 개발팀이 채우는 값. mvpa_minutes_per_day 는 앱의 activeMinutes(1분 bin, 100 steps/min)로
-- 이미 계산 중이므로 true. 자세한 근거는 삼성헬스_애플헬스_추가수집항목_claude.md §3 참고.

-- 1-4. measurement_definition 의 단위 → 신호 이름과 우선순위
CREATE TABLE map_signal (
  unit       text PRIMARY KEY,
  signal_key text NOT NULL,
  priority   integer NOT NULL,
  formula    text
);
INSERT INTO map_signal VALUES
 ('MET',           'met',       1, NULL),
 ('steps_per_min', 'cadence',   2, '구간 걸음수 / 구간 분'),
 ('percent_hrmax', 'pct_hrmax', 3, 'HRmax = 220 - 나이');

-- 1-5. 강도 정의가 없는 지표의 신호 (수면·걸음수)
CREATE TABLE map_signal_extra (
  metric_key text NOT NULL,
  signal_key text NOT NULL,
  signal_min numeric,
  signal_max numeric,
  signal_unit text NOT NULL,
  priority   integer NOT NULL,
  required_input_key text,
  formula    text,
  note       text,
  PRIMARY KEY (metric_key, signal_key)
);
INSERT INTO map_signal_extra VALUES
 ('sleep_hours_per_night','asleep_minutes',NULL,NULL,'minute',1,'sleep_session','수면 분 / 60',
  '자정을 넘는 수면의 날짜 귀속 규칙이 필요하다(기상 시각이 속한 날짜 권장)'),
 ('daily_steps','step_total',NULL,NULL,'step',1,'daily_step_total',NULL,
  '보정된 하루 총량만 사용. raw 구간 샘플을 단순 합산하지 않는다');

-- 1-5b. fact 없이 sample requirement 로만 서는 지표의 강도 신호
--       임계를 여기 적어 넣지 않고, 지식DB의 강도 정의를 그대로 빌려 쓴다.
--       (sample requirement note 가 "cadence >=100 steps/min 또는 MET >=3" 라고 적은 것과
--        같은 값이 moderate_to_vigorous_intensity 정의에 있다)
CREATE TABLE map_signal_borrow (
  metric_key                    text PRIMARY KEY,
  borrow_measurement_target_key text NOT NULL,
  note                          text
);
INSERT INTO map_signal_borrow VALUES
 ('short_brisk_bouts_per_day','moderate_to_vigorous_intensity_aerobic_activity',
  '1분 이상 10분 미만 단일 샘플에만 적용한다. 샘플 사이를 이어붙이지 않고, daily total steps 로는 판정하지 않는다');

-- 1-6. 질환 상태 매핑 (지식DB population_condition → maiReport health_condition)
CREATE TABLE map_condition (
  kb_condition                 text PRIMARY KEY,
  health_condition             text NOT NULL,
  requires_confirmed_diagnosis boolean NOT NULL
);
INSERT INTO map_condition VALUES
 ('general',  'general',            false),
 ('diabetes', 'diabetes',           true),
 -- 지식DB는 pneumonia 로 저장하지만 문서가 회복기를 전제한다 → 이름을 명시적으로 바꾼다
 ('pneumonia','pneumonia_recovery', true);

-- 1-7. 문구 묶음 · 우선순위 · 안전 게이트 · 주제 · rule_id
--      (message_id, metric_key) 당 1행. metric_key IS NULL 이면 지표 없는 규칙.
--      ⚠️ 새 코칭 문구가 지식DB에 추가되면 여기에도 한 줄 넣어야 한다.
--         빠뜨리면 PART 4 검증 쿼리 V1이 잡아낸다.
CREATE TABLE map_rule (
  message_id  text NOT NULL,
  metric_key  text,
  rule_id     text NOT NULL,
  rule_group  text NOT NULL,
  priority    integer NOT NULL,
  safety_gate text
);
CREATE UNIQUE INDEX map_rule_key
  ON map_rule (message_id, coalesce(metric_key, '-'));
INSERT INTO map_rule (message_id, metric_key, rule_id, rule_group, priority, safety_gate) VALUES
 -- 일반 성인
 ('aerobic_volume_is_not_the_lever','moderate_minutes_per_week','r_gen_moderate_met','aerobic_volume',10,NULL),
 ('aerobic_volume_is_not_the_lever','vigorous_minutes_per_week','r_gen_vigorous_met','aerobic_volume',10,NULL),
 ('aerobic_below_guideline_start','moderate_minutes_per_week','r_gen_moderate_low','aerobic_volume',20,NULL),
 ('aerobic_below_guideline_start','vigorous_minutes_per_week','r_gen_vigorous_low','aerobic_volume',20,NULL),
 ('general_regular_short_sleep_duration','sleep_hours_per_night','r_gen_sleep_short','sleep_duration',10,NULL),
 ('general_short_ambulatory_mvpa_proxy','short_brisk_bouts_per_day','r_gen_short_brisk_bout','activity_moment',10,NULL),
 -- 2형 당뇨
 ('dm_shift_walking_to_after_meals','moderate_minutes_per_week','r_dm_moderate_met','dm_weekly_volume',10,NULL),
 ('dm_shift_walking_to_after_meals','mvpa_minutes_per_week','r_dm_mvpa_met','dm_weekly_volume',10,NULL),
 ('dm_shift_walking_to_after_meals','mvpa_minutes_per_day','r_dm_daily_met','dm_daily_volume',10,NULL),
 ('dm_below_guideline_glycemia','moderate_minutes_per_week','r_dm_moderate_low','dm_weekly_volume',20,NULL),
 ('dm_below_guideline_glycemia','mvpa_minutes_per_week','r_dm_mvpa_low','dm_weekly_volume',20,NULL),
 ('dm_daily_short_of_target_move_after_meals','mvpa_minutes_per_day','r_dm_daily_low','dm_daily_volume',20,NULL),
 ('dm_few_active_days_try_short_bouts','mvpa_days_per_week','r_dm_active_days_low','dm_active_days',10,
  '고강도 1분 인터벌을 권유하는 문구 — 심혈관 위험 평가와 운동 가능 여부 확인 필요'),
 ('dm_gap_between_sessions_too_long','days_between_exercise_sessions','r_dm_session_gap_long','dm_session_gap',10,NULL),
 ('dm_plan_postmeal_activity',NULL,'r_dm_plan_postmeal','dm_postmeal_habit',10,NULL),
 ('dm_walk_after_meal_instead_of_sitting',NULL,'r_dm_walk_after_meal','dm_postmeal_habit',20,NULL),
 ('dm_start_soon_after_meal',NULL,'r_dm_start_soon_after_meal','dm_postmeal_habit',30,NULL),
 ('dm_break_up_prolonged_sitting',NULL,'r_dm_break_up_sitting','dm_sedentary',10,NULL),
 -- 폐렴 회복기
 ('pneumonia_recovery_lower_intensity',NULL,'r_pn_lower_intensity','pneumonia_recovery',10,
  '진단 확정 + 회복기 확인 + 활동 가능 여부 확인'),
 ('pneumonia_rise_slowly_after_lying',NULL,'r_pn_rise_slowly','pneumonia_recovery',20,
  '진단 확정 + 침상안정/회복기 맥락 확인');

-- 1-8. 문구 주제
CREATE TABLE map_topic (message_id text PRIMARY KEY, topic text NOT NULL);
INSERT INTO map_topic VALUES
 ('aerobic_below_guideline_start','activity'),
 ('aerobic_volume_is_not_the_lever','activity'),
 ('general_regular_short_sleep_duration','sleep'),
 ('general_short_ambulatory_mvpa_proxy','activity'),
 ('dm_below_guideline_glycemia','activity'),
 ('dm_daily_short_of_target_move_after_meals','postmeal'),
 ('dm_shift_walking_to_after_meals','postmeal'),
 ('dm_plan_postmeal_activity','postmeal'),
 ('dm_walk_after_meal_instead_of_sitting','postmeal'),
 ('dm_start_soon_after_meal','postmeal'),
 ('dm_few_active_days_try_short_bouts','activity'),
 ('dm_gap_between_sessions_too_long','activity'),
 ('dm_break_up_prolonged_sitting','sedentary'),
 ('pneumonia_recovery_lower_intensity','recovery'),
 ('pneumonia_rise_slowly_after_lying','recovery');

-- 1-9. 출처 표기 축약 (package.identity->>'authority' → 화면용 문자열)
CREATE TABLE map_authority (authority text PRIMARY KEY, label text NOT NULL);
INSERT INTO map_authority VALUES
 ('World Health Organization',                                     'WHO 2020'),
 ('UK Chief Medical Officers (Department of Health and Social Care)','UK CMO 2019'),
 ('질병관리청 국가건강정보포털',                                     '질병관리청 신체활동 지침'),
 ('American Diabetes Association',                                 'ADA Standards of Care 2026'),
 ('Canadian Society for Exercise Physiology',                      'CSEP 24-Hour Movement Guidelines'),
 ('Australian Government Department of Health, Disability and Ageing','Australian 24-Hour Movement Guidelines 2025');

-- 1-10. 입력 카탈로그 (지식DB에는 event_kind / requirement_kind 이름만 있다)
CREATE TABLE map_input (
  input_key        text PRIMARY KEY,
  display_name     text NOT NULL,
  input_type       text NOT NULL,
  question_text_ko text,
  answer_format    text,
  freshness_hours  integer,
  available_now    boolean NOT NULL,
  note             text
);
INSERT INTO map_input VALUES
 ('birth_date','생년월일','user_profile','생년월일을 알려주세요','YYYY-MM-DD',NULL,false,
  '모든 규칙의 나이 조건과 HRmax(220-나이) 계산에 필요. 앱 온보딩 질문이 유일한 공통 경로'),
 ('confirmed_condition','확진 질환','user_answer','의사에게 진단받으신 질환이 있나요?',
  'type_2_diabetes | pneumonia_recovery | none',720,false,
  'AI 리포트 소견은 확진이 아니다. 플랫폼(애플/삼성)에 해당 데이터가 없어 앱 질문 전용'),
 ('daily_step_total','하루 총 걸음수','device_daily',NULL,NULL,24,true,
  '보정된 하루 총량만 사용. raw StepCount interval을 단순 합산하지 않는다'),
 ('sleep_session','수면 세션','device_daily',NULL,NULL,24,true,
  '밤별 수면 시간. 단일 밤만으로 판정하지 않는다'),
 ('activity_interval','활동 구간 샘플','device_interval',NULL,'start, end, steps | met | heart_rate',24,false,
  '강도별 활동 시간의 필수 입력. cadence 경로가 애플·삼성·Health Connect 공통으로 가능한 유일한 신호'),
 ('exercise_session','운동 세션','device_interval',NULL,'start, end',168,false,
  '세션 간격 계산용. 10분 이상 지속 구간을 1세션으로 본다'),
 ('meal_event','식사 시각','user_answer','오늘 점심은 몇 시에 드셨나요?',
  '{"start":"HH:MM","meal_label":"breakfast|lunch|dinner"}',12,false,
  '최소 계약은 시작 시각만. 탄수화물량·음식 종류는 넣지 않는다'),
 ('sedentary_bout','좌식 구간','device_interval',NULL,'start, end',24,false,
  'dm_break_up_prolonged_sitting 트리거 정교화용. 현재 해당 규칙은 비활성');

-- 1-11. 지식DB의 event_kind / requirement_kind → 입력 키
CREATE TABLE map_requirement (
  kb_kind    text PRIMARY KEY,
  input_key  text,          -- 규칙의 context_input_key 로 나갈 값
  metric_key text,          -- sample requirement 가 지표로 바뀌는 경우
  value_min  numeric,       -- 그 지표의 임계
  value_max  numeric
);
INSERT INTO map_requirement VALUES
 ('meal_event',    'meal_event',    NULL,                       NULL, NULL),
 ('sedentary_bout','sedentary_bout',NULL,                       NULL, NULL),
 ('sleep_session', 'sleep_session', NULL,                       NULL, NULL),
 -- sample requirement 는 "관찰되면 뜬다" 이므로 개수 지표 1회 이상으로 바꾼다
 ('short_ambulatory_mvpa_proxy','activity_interval','short_brisk_bouts_per_day', 1, NULL);


-- =============================================================================
--  PART 2. 지식DB → 전달 테이블 뷰
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 2-0. fact 조건을 숫자 구간으로 바꾼 원본 (평탄화 1단계, 중복 아직 있음)
--      value_min 이상 / value_max 미만 규약으로 통일한다.
-- -----------------------------------------------------------------------------
CREATE VIEW v_rule_raw AS
SELECT
    cc.line_id                                AS message_id,
    mm.metric_key,
    cc.fact_seq,
    cc.position,
    f.range_type,
    -- value_min: 이상
    CASE cc.position
      WHEN 'below'  THEN NULL
      WHEN 'within' THEN lower(f.quantity)
      WHEN 'above'  THEN CASE f.range_type
                           WHEN 'recommended_range'  THEN upper(f.quantity)
                           -- 상한 포함 (,2] 의 초과 → 정수 단위면 +1
                           WHEN 'maximum_threshold'  THEN upper(f.quantity)
                                                          + coalesce(mu.integer_step, 0)
                           ELSE lower(f.quantity)
                         END
    END                                       AS value_min,
    -- value_max: 미만
    CASE cc.position
      WHEN 'below'  THEN lower(f.quantity)
      WHEN 'within' THEN CASE f.range_type
                           WHEN 'recommended_range'  THEN upper(f.quantity)
                           WHEN 'maximum_threshold'  THEN upper(f.quantity)
                                                          + coalesce(mu.integer_step, 0)
                           ELSE NULL
                         END
      WHEN 'above'  THEN NULL
    END                                       AS value_max,
    lower(f.population_age)                   AS age_min,
    upper(f.population_age)                   AS age_max,
    coalesce(f.population_condition,'general') AS kb_condition,
    coalesce(ma.label,
             p.identity->>'authority',
             '(출처 미표기)')                  AS evidence_label,
    obs.window_days                           AS obs_window_days,
    obs.min_observed_count                    AS obs_min_observed,
    obs.below_fraction_gt                     AS obs_min_match_ratio
FROM coaching_condition cc
JOIN fact f              ON f.fact_seq = cc.fact_seq
JOIN map_metric mm       ON mm.measurement_target_key = f.measurement_target_key
                        AND mm.unit                  = f.unit
LEFT JOIN map_unit mu    ON mu.unit = f.unit
LEFT JOIN package p      ON p.package_id = f.package_id
LEFT JOIN map_authority ma ON ma.authority = p.identity->>'authority'
LEFT JOIN coaching_axis_observation_rule obs ON obs.fact_seq = f.fact_seq;

-- -----------------------------------------------------------------------------
-- 2-1. coaching_rule — 지표 기반 규칙 (중복 제거 + 인접 구간 병합)
--      같은 (지표, 문구, 질환)에 여러 fact가 걸리면 하나로 합친다.
--      NULL 은 무한으로 취급한다: 하나라도 NULL 이면 그 방향은 열린 구간이 된다.
-- -----------------------------------------------------------------------------
CREATE VIEW v_rule_metric AS
SELECT
    mr.rule_id,
    mr.rule_group,
    mr.priority,
    mc.health_condition,
    mc.requires_confirmed_diagnosis,
    CASE WHEN bool_or(r.age_min IS NULL) THEN NULL ELSE min(r.age_min) END AS age_min,
    CASE WHEN bool_or(r.age_max IS NULL) THEN NULL ELSE max(r.age_max) END AS age_max,
    'metric_range'::text AS trigger_type,
    r.metric_key,
    CASE WHEN bool_or(r.value_min IS NULL) THEN NULL ELSE min(r.value_min) END AS value_min,
    CASE WHEN bool_or(r.value_max IS NULL) THEN NULL ELSE max(r.value_max) END AS value_max,
    -- 관찰 규칙: 지식DB에 observation rule 이 있으면 그것이 우선, 없으면 map_window
    coalesce(max(r.obs_window_days),   mw.eval_window_days)  AS eval_window_days,
    coalesce(max(r.obs_min_observed),  mw.min_observed_days) AS min_observed_days,
    max(r.obs_min_match_ratio)                               AS min_match_ratio,
    -- 문구 자체가 요구하는 사건 입력
    (SELECT mq.input_key
       FROM coaching_line_event_requirement er
       JOIN map_requirement mq ON mq.kb_kind = er.event_kind
      WHERE er.line_id = r.message_id
      ORDER BY er.event_kind
      LIMIT 1)                                               AS context_input_key,
    mr.safety_gate,
    r.message_id,
    string_agg(DISTINCT r.evidence_label, ' · ' ORDER BY r.evidence_label) AS evidence_label,
    string_agg(DISTINCT r.fact_seq::text || ':' || r.position, ', '
               ORDER BY r.fact_seq::text || ':' || r.position)             AS source_ref,
    true AS is_active
FROM v_rule_raw r
JOIN map_condition mc ON mc.kb_condition = r.kb_condition
JOIN map_window   mw  ON mw.metric_key   = r.metric_key
JOIN map_rule     mr  ON mr.message_id   = r.message_id
                     AND mr.metric_key   = r.metric_key
GROUP BY mr.rule_id, mr.rule_group, mr.priority, mr.safety_gate,
         mc.health_condition, mc.requires_confirmed_diagnosis,
         r.metric_key, r.message_id,
         mw.eval_window_days, mw.min_observed_days;

-- -----------------------------------------------------------------------------
-- 2-2. coaching_rule — sample requirement 기반 규칙
--      "관찰되면 뜬다" 형태의 문구를 개수 지표 1회 이상으로 바꾼다.
-- -----------------------------------------------------------------------------
CREATE VIEW v_rule_sample AS
SELECT
    mr.rule_id, mr.rule_group, mr.priority,
    mc.health_condition, mc.requires_confirmed_diagnosis,
    -- 이 문구에는 fact 가 없어 나이 근거도 없다. 성인 기본값(18세 이상)을 쓴다.
    -- 의학팀 확인 대상: 설계서 §8-4
    18::integer   AS age_min,
    NULL::integer AS age_max,
    'metric_range'::text     AS trigger_type,
    mq.metric_key,
    mq.value_min, mq.value_max,
    mw.eval_window_days, mw.min_observed_days,
    NULL::numeric            AS min_match_ratio,
    mq.input_key             AS context_input_key,
    mr.safety_gate,
    l.line_id                AS message_id,
    '짧고 산발적 MVPA 관련 코호트 근거'::text AS evidence_label,
    'line:' || l.line_id || ' (sample requirement: ' || sr.requirement_kind || ')' AS source_ref,
    true AS is_active
FROM coaching_line_sample_requirement sr
JOIN coaching_line l   ON l.line_id = sr.line_id
JOIN map_requirement mq ON mq.kb_kind = sr.requirement_kind
JOIN map_condition mc  ON mc.kb_condition = l.population_condition
JOIN map_window mw     ON mw.metric_key = mq.metric_key
JOIN map_rule mr       ON mr.message_id = l.line_id
                      AND mr.metric_key = mq.metric_key
WHERE mq.metric_key IS NOT NULL;

-- -----------------------------------------------------------------------------
-- 2-3. coaching_rule — 지표 없는 규칙 (질환만으로 뜨는 문구)
--      coaching_condition 과 sample requirement 가 모두 없는 line.
-- -----------------------------------------------------------------------------
CREATE VIEW v_rule_condition_only AS
SELECT
    mr.rule_id, mr.rule_group, mr.priority,
    mc.health_condition, mc.requires_confirmed_diagnosis,
    NULL::integer AS age_min,
    NULL::integer AS age_max,
    'condition_only'::text AS trigger_type,
    NULL::text    AS metric_key,
    NULL::numeric AS value_min,
    NULL::numeric AS value_max,
    1 AS eval_window_days,
    1 AS min_observed_days,
    NULL::numeric AS min_match_ratio,
    (SELECT mq.input_key
       FROM coaching_line_event_requirement er
       JOIN map_requirement mq ON mq.kb_kind = er.event_kind
      WHERE er.line_id = l.line_id
      ORDER BY er.event_kind
      LIMIT 1) AS context_input_key,
    mr.safety_gate,
    l.line_id AS message_id,
    coalesce(
      (SELECT string_agg(DISTINCT lc.claim_id, ' · ' ORDER BY lc.claim_id)
         FROM coaching_line_claim lc WHERE lc.line_id = l.line_id),
      '(근거 claim 없음)') AS evidence_label,
    'line:' || l.line_id AS source_ref,
    -- 좌식 문구는 관찰 입력과 연결되지 않아 트리거 미확정 → 비활성으로 내보낸다
    (l.line_id <> 'dm_break_up_prolonged_sitting') AS is_active
FROM coaching_line l
JOIN map_condition mc ON mc.kb_condition = l.population_condition
JOIN map_rule mr      ON mr.message_id = l.line_id AND mr.metric_key IS NULL
WHERE NOT EXISTS (SELECT 1 FROM coaching_condition cc WHERE cc.line_id = l.line_id)
  AND NOT EXISTS (SELECT 1 FROM coaching_line_sample_requirement sr WHERE sr.line_id = l.line_id);

-- -----------------------------------------------------------------------------
-- 2-4. 최종 5개 전달 뷰
-- -----------------------------------------------------------------------------

-- (1) coaching_input
CREATE VIEW export_coaching_input AS
SELECT input_key, display_name, input_type, question_text_ko, answer_format,
       freshness_hours, available_now, note
FROM map_input
ORDER BY input_type, input_key;

-- (2) coaching_metric
CREATE VIEW export_coaching_metric AS
SELECT
    mw.metric_key,
    mw.display_name,
    mw.out_unit                        AS unit,
    mw.window_kind,
    -- 지속 시간 하한: measurement_target_activity.bout_fact_seq 가 가리키는 fact 의 하한
    (SELECT min(lower(bf.quantity))
       FROM map_metric mm2
       JOIN measurement_target_activity mta
              ON mta.measurement_target_key = mm2.measurement_target_key
       JOIN fact bf ON bf.fact_seq = mta.bout_fact_seq
      WHERE mm2.metric_key = mw.metric_key)   AS min_bout_minutes,
    -- 상한은 지식DB에 없다. sample requirement 계열만 값이 있다(1-10분).
    CASE WHEN mw.metric_key = 'short_brisk_bouts_per_day' THEN 10 END AS max_bout_minutes,
    mw.required_input_key,
    mw.computable_now,
    mw.metric_key || ' — ' || mw.display_name AS description
FROM map_window mw
ORDER BY mw.metric_key;

-- (3) coaching_metric_signal
CREATE VIEW export_coaching_metric_signal AS
SELECT DISTINCT
    mm.metric_key,
    ms.signal_key,
    lower(md.quantity) AS signal_min,
    upper(md.quantity) AS signal_max,
    md.unit            AS signal_unit,
    ms.priority,
    'activity_interval'::text AS required_input_key,
    ms.formula,
    left(md.note, 200) AS note
FROM measurement_target_intensity mti
JOIN measurement_definition md ON md.definition_id = mti.intensity_definition_id
JOIN map_metric mm ON mm.measurement_target_key = mti.measurement_target_key
JOIN map_signal ms ON ms.unit = md.unit
UNION ALL
-- fact 없이 sample requirement 로만 서는 지표: 강도 정의를 빌려 온다
SELECT DISTINCT
    mb.metric_key,
    ms.signal_key,
    lower(md.quantity), upper(md.quantity), md.unit, ms.priority,
    'activity_interval'::text,
    ms.formula,
    left(mb.note, 200)
FROM map_signal_borrow mb
JOIN measurement_target_intensity mti
       ON mti.measurement_target_key = mb.borrow_measurement_target_key
JOIN measurement_definition md ON md.definition_id = mti.intensity_definition_id
JOIN map_signal ms ON ms.unit = md.unit
UNION ALL
SELECT metric_key, signal_key, signal_min, signal_max, signal_unit,
       priority, required_input_key, formula, note
FROM map_signal_extra
ORDER BY metric_key, priority;

-- (4) coaching_message
CREATE VIEW export_coaching_message AS
SELECT
    l.line_id  AS message_id,
    l.headline AS title,
    l.detail   AS body,
    mt.topic,
    'line:' || l.line_id AS source_ref
FROM coaching_line l
LEFT JOIN map_topic mt ON mt.message_id = l.line_id
ORDER BY mt.topic, l.line_id;

-- (5) coaching_rule
CREATE VIEW export_coaching_rule AS
SELECT rule_id, rule_group, priority, health_condition, requires_confirmed_diagnosis,
       age_min, age_max, trigger_type, metric_key, value_min, value_max,
       eval_window_days, min_observed_days, min_match_ratio,
       context_input_key, safety_gate, message_id, evidence_label, source_ref, is_active
FROM (
  SELECT * FROM v_rule_metric
  UNION ALL
  SELECT * FROM v_rule_sample
  UNION ALL
  SELECT * FROM v_rule_condition_only
) t
ORDER BY health_condition, rule_group, priority, rule_id;

-- =============================================================================
--  PART 3. 검증 뷰
-- =============================================================================
--  GUI 클라이언트(pgAdmin / DBeaver)는 스크립트를 한 번에 실행하면 마지막 결과만
--  보여준다. 그래서 검증 9종을 뷰 하나로 합쳤다. 실행 후 아래 한 줄만 돌리면 된다.
--
--      SELECT * FROM maireport_export.export_validation;
--
--  severity = 'ERROR' 가 0건이어야 정상이다.
--  'REVIEW' 는 의학팀 확인 대상, 'INFO' 는 병합 결과 확인용 참고 자료다.
-- =============================================================================

CREATE VIEW export_validation AS

-- V1. 코칭 문구가 새로 추가됐는데 map_rule 에 묶음·우선순위가 없다
SELECT 'V1'::text AS check_id, 'ERROR'::text AS severity,
       'map_rule 에 등록되지 않은 코칭 문구'::text AS check_name,
       l.line_id || '  (' || l.population_condition || ')' AS detail
FROM coaching_line l
WHERE NOT EXISTS (SELECT 1 FROM map_rule mr WHERE mr.message_id = l.line_id)

UNION ALL
-- V2. fact 조건이 걸렸는데 지표 매핑이 없다
SELECT 'V2', 'ERROR', 'map_metric 에 매핑되지 않은 fact 조건',
       f.measurement_target_key || ' / ' || f.unit
       || '  (조건 ' || count(*) || '건)'
FROM coaching_condition cc
JOIN fact f ON f.fact_seq = cc.fact_seq
WHERE NOT EXISTS (
        SELECT 1 FROM map_metric mm
         WHERE mm.measurement_target_key = f.measurement_target_key
           AND mm.unit                  = f.unit)
GROUP BY f.measurement_target_key, f.unit

UNION ALL
-- V3. 구간 병합이 위험하다
--     PART 2 의 병합은 "같은 (지표,문구,질환)의 구간은 서로 붙어 있다"를 전제한다.
--     below 와 above 가 한 문구에 함께 오면 떨어진 두 구간이 하나로 뭉개진다.
SELECT 'V3', 'ERROR', 'below 와 within/above 가 같은 문구에 섞임',
       metric_key || ' / ' || message_id || ' / ' || kb_condition
       || '  → ' || string_agg(DISTINCT position, ', ' ORDER BY position)
FROM v_rule_raw
GROUP BY metric_key, message_id, kb_condition
HAVING bool_or(position = 'below')
   AND bool_or(position IN ('within','above'))

UNION ALL
-- V4. 지식DB의 event_kind / requirement_kind 가 입력 카탈로그에 없다
SELECT 'V4', 'ERROR', 'map_requirement 에 없는 event/sample kind',
       k.kind || '  (' || k.kb_source || ')'
FROM (
  SELECT DISTINCT event_kind AS kind, 'coaching_line_event_requirement' AS kb_source
    FROM coaching_line_event_requirement
  UNION
  SELECT DISTINCT event_kind, 'coaching_axis_event_requirement'
    FROM coaching_axis_event_requirement
  UNION
  SELECT DISTINCT requirement_kind, 'coaching_line_sample_requirement'
    FROM coaching_line_sample_requirement
) k
WHERE NOT EXISTS (SELECT 1 FROM map_requirement mq WHERE mq.kb_kind = k.kind)

UNION ALL
-- V5. 계산 신호가 하나도 없는 지표
SELECT 'V5', 'ERROR', '계산 신호가 없는 지표', m.metric_key
FROM export_coaching_metric m
WHERE NOT EXISTS (SELECT 1 FROM export_coaching_metric_signal s
                   WHERE s.metric_key = m.metric_key)

UNION ALL
-- V6. 규칙 자체가 성립하지 않는 경우
SELECT 'V6', 'ERROR', '문구가 없는 규칙', r.rule_id
FROM export_coaching_rule r
WHERE NOT EXISTS (SELECT 1 FROM export_coaching_message m
                   WHERE m.message_id = r.message_id)
UNION ALL
SELECT 'V6', 'ERROR', '구간이 비어 있는 metric_range 규칙', rule_id
FROM export_coaching_rule
WHERE trigger_type = 'metric_range' AND value_min IS NULL AND value_max IS NULL
UNION ALL
SELECT 'V6', 'ERROR', '정의되지 않은 지표를 참조하는 규칙', r.rule_id
FROM export_coaching_rule r
WHERE r.metric_key IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM export_coaching_metric m WHERE m.metric_key = r.metric_key)

UNION ALL
-- V7. 질환 상태 매핑 누락
SELECT 'V7', 'ERROR', 'map_condition 에 없는 population_condition',
       population_condition
FROM (SELECT DISTINCT population_condition FROM coaching_line) c
WHERE population_condition NOT IN (SELECT kb_condition FROM map_condition)

UNION ALL
-- V8. [의학팀 확인] 지속시간 하한을 물려받은 지표
--     measurement_target_activity 는 measurement_target_key 단위로만 bout 을 갖는다.
--     같은 target 이 단위만 달라 두 지표로 갈라질 때 bout 이 양쪽에 함께 붙는다.
--     예) moderate_to_vigorous_intensity_aerobic_activity 는 day_per_week(주간 활동일수)와
--         minute_per_week(주간 활동시간) 양쪽에 쓰이는데, "10분 이상 지속"이 활동시간에도
--         적용되면 「짧게라도 움직이라」는 문구와 충돌할 수 있다.
SELECT 'V8', 'REVIEW', '지속시간 하한(min_bout_minutes)을 물려받은 지표',
       metric_key || '  → ' || min_bout_minutes || '분 이상 (' || display_name || ')'
FROM export_coaching_metric
WHERE min_bout_minutes IS NOT NULL

UNION ALL
-- V9. 나이 범위가 여러 개여서 하나로 합쳐진 규칙 (병합 결과 눈으로 확인)
SELECT 'V9', 'INFO', '여러 나이 범위가 하나로 합쳐진 규칙',
       metric_key || ' / ' || message_id || '  → 원본 '
       || string_agg(DISTINCT coalesce(age_min::text,'-') || '~' || coalesce(age_max::text,'-'),
                     ' | ' ORDER BY coalesce(age_min::text,'-') || '~' || coalesce(age_max::text,'-'))
FROM v_rule_raw
GROUP BY metric_key, message_id
HAVING count(DISTINCT coalesce(age_min::text,'-') || '~' || coalesce(age_max::text,'-')) > 1;


-- 행 수 요약 (설계서 기대값과 비교)
CREATE VIEW export_summary AS
SELECT * FROM (
  SELECT 1 AS ord, 'coaching_input'  AS table_name, count(*) AS row_count, 8  AS expected FROM export_coaching_input
  UNION ALL SELECT 2,'coaching_metric',        count(*),  9 FROM export_coaching_metric
  UNION ALL SELECT 3,'coaching_metric_signal', count(*), 18 FROM export_coaching_metric_signal
  UNION ALL SELECT 4,'coaching_message',       count(*), 15 FROM export_coaching_message
  UNION ALL SELECT 5,'coaching_rule',          count(*), 20 FROM export_coaching_rule
) s;


-- =============================================================================
--  PART 4. INSERT 스크립트 생성 뷰
-- =============================================================================
--  maiReport DB 에 그대로 실행할 적재 스크립트를 텍스트로 만든다.
--  GUI 에서는 아래를 실행한 뒤 결과 열을 전체 복사해서 .sql 파일로 저장하면 된다.
--
--      SELECT txt FROM maireport_export.export_insert_script;
--
--  psql 로 파일까지 자동 생성하려면 지식DB_전달테이블_추출_psql_파일생성_claude.sql 을 쓴다.
-- =============================================================================

CREATE VIEW export_insert_script AS
WITH lines AS (
  SELECT 1 AS ord, 0 AS sub,
         '-- maiReport 코칭 테이블 적재 스크립트 (지식DB 추출본, 생성: '
         || to_char(now(),'YYYY-MM-DD HH24:MI') || ')' AS txt
  UNION ALL SELECT 1,1,'-- 원본: maireport-knowledge / 스크립트: 지식DB_전달테이블_추출_claude.sql'
  UNION ALL SELECT 1,2,'BEGIN;'
  UNION ALL SELECT 1,3,'TRUNCATE coaching_rule, coaching_metric_signal, coaching_metric, coaching_message, coaching_input;'
  UNION ALL SELECT 1,4,''

  UNION ALL
  SELECT 2, row_number() OVER (ORDER BY input_key)::int,
         format('INSERT INTO coaching_input VALUES (%L,%L,%L,%L,%L,%s,%s,%L);',
                input_key, display_name, input_type, question_text_ko, answer_format,
                coalesce(freshness_hours::text,'NULL'),
                CASE WHEN available_now THEN 'true' ELSE 'false' END, note)
  FROM export_coaching_input

  UNION ALL SELECT 3,0,''
  UNION ALL
  SELECT 4, row_number() OVER (ORDER BY metric_key)::int,
         format('INSERT INTO coaching_metric VALUES (%L,%L,%L,%L,%s,%s,%L,%s,%L);',
                metric_key, display_name, unit, window_kind,
                coalesce(min_bout_minutes::text,'NULL'),
                coalesce(max_bout_minutes::text,'NULL'),
                required_input_key,
                CASE WHEN computable_now THEN 'true' ELSE 'false' END, description)
  FROM export_coaching_metric

  UNION ALL SELECT 5,0,''
  UNION ALL
  SELECT 6, row_number() OVER (ORDER BY metric_key, priority)::int,
         format('INSERT INTO coaching_metric_signal VALUES (%L,%L,%s,%s,%L,%s,%L,%L,%L);',
                metric_key, signal_key,
                coalesce(signal_min::text,'NULL'), coalesce(signal_max::text,'NULL'),
                signal_unit, priority, required_input_key, formula, note)
  FROM export_coaching_metric_signal

  UNION ALL SELECT 7,0,''
  UNION ALL
  SELECT 8, row_number() OVER (ORDER BY message_id)::int,
         format('INSERT INTO coaching_message VALUES (%L,%L,%L,%L,%L);',
                message_id, title, body, topic, source_ref)
  FROM export_coaching_message

  UNION ALL SELECT 9,0,''
  UNION ALL
  SELECT 10, row_number() OVER (ORDER BY health_condition, rule_group, priority, rule_id)::int,
         format('INSERT INTO coaching_rule VALUES (%L,%L,%s,%L,%s,%s,%s,%L,%L,%s,%s,%s,%s,%s,%L,%L,%L,%L,%L,%s);',
                rule_id, rule_group, priority, health_condition,
                CASE WHEN requires_confirmed_diagnosis THEN 'true' ELSE 'false' END,
                coalesce(age_min::text,'NULL'), coalesce(age_max::text,'NULL'),
                trigger_type, metric_key,
                coalesce(value_min::text,'NULL'), coalesce(value_max::text,'NULL'),
                eval_window_days, min_observed_days,
                coalesce(min_match_ratio::text,'NULL'),
                context_input_key, safety_gate, message_id, evidence_label, source_ref,
                CASE WHEN is_active THEN 'true' ELSE 'false' END)
  FROM export_coaching_rule

  UNION ALL SELECT 11,0,''
  UNION ALL SELECT 11,1,'COMMIT;'
)
SELECT ord, sub, txt FROM lines;

COMMIT;


-- =============================================================================
--  PART 5. 사용법 — 여기서부터는 필요한 것만 하나씩 실행한다
-- =============================================================================
--  위 PART 1~4 는 스키마와 뷰를 만들 뿐이다. 결과는 아래 뷰를 조회해서 본다.
--  pgAdmin / DBeaver 는 스크립트 전체 실행 시 마지막 결과만 보여주므로
--  아래 쿼리는 한 줄씩 선택해서 실행하는 편이 편하다.
--
--   [검증]  SELECT * FROM maireport_export.export_validation ORDER BY check_id, detail;
--           SELECT * FROM maireport_export.export_summary    ORDER BY ord;
--
--   [내용]  SELECT * FROM maireport_export.export_coaching_rule;
--           SELECT * FROM maireport_export.export_coaching_metric;
--           SELECT * FROM maireport_export.export_coaching_metric_signal;
--           SELECT * FROM maireport_export.export_coaching_message;
--           SELECT * FROM maireport_export.export_coaching_input;
--
--   [적재]  SELECT txt FROM maireport_export.export_insert_script ORDER BY ord, sub;
--           → 결과 열을 전체 복사해 .sql 로 저장하고 maiReport DB 에서 실행한다.
--
--   [파일]  CSV 와 .sql 파일까지 자동 생성하려면 psql 로 아래를 실행한다.
--           psql -h localhost -p 5432 -U postgres -d maireport-knowledge \
--                -f 지식DB_전달테이블_추출_psql_파일생성_claude.sql
--
--  maireport_export 스키마는 남겨 둔다. 다시 뽑을 때는 이 파일을 그대로 재실행하면 되고,
--  첫 줄이 스키마를 DROP/CREATE 하므로 몇 번을 재실행해도 결과가 같다.
-- =============================================================================

-- 스크립트 전체를 한 번에 실행했을 때 마지막에 보이는 결과: 검증 + 행 수 요약
SELECT s.table_name        AS item,
       s.row_count::text || ' / ' || s.expected::text AS "실제/기대",
       CASE WHEN s.row_count = s.expected THEN 'OK' ELSE 'DIFF' END AS status
FROM maireport_export.export_summary s
UNION ALL
SELECT '검증 ERROR 건수',
       count(*) FILTER (WHERE severity = 'ERROR')::text,
       CASE WHEN count(*) FILTER (WHERE severity = 'ERROR') = 0 THEN 'OK' ELSE 'CHECK' END
FROM maireport_export.export_validation
ORDER BY 1;
