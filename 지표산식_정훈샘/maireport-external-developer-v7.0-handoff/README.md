# maiReport I1·I2·I3 외부 개발자 전달 자료

이 문서는 maiReport 프로젝트를 전달받지 않는 외부 개발자가 Apple Health, Samsung
Health, Android Health Connect 원본 데이터를 받아 I1·I2·I3를 독립적으로 구현할 수 있도록 만든 self-contained
specification이다. 이 폴더 밖의 코드·문서·DB·fixture에 의존하지 않는다.

## 1. 구현 흐름

```text
provider export/API
 -> provider adapter
 -> timezone/local-day normalization
 -> dedupe/conflict/provenance validation
 -> v7 normalized input
 -> I1/I2/I3 calculation
 -> raw score
 -> display_score_0_100/category/status
```

이 폴더의 `provider-field-map.json`, `preprocessing-rules.md`, `formula-spec.md`,
schema와 `acceptance-tests.md`만을 기준으로 구현한다.
Health Connect 원본 구조 확인에는 `health-connect-reference.md`의 Android 공식 문서를
사용한다.

## 2. 공통 입력 규칙

각 정규화 값에는 `day`, `provider`, `metric`, `unit`, `source_identity`,
`provenance_status`, `observation_status`를 보존한다.

- timestamp는 timezone-aware로 파싱하고 사용자 local day로 변환한다.
- 동일 source의 정확한 중복만 제거한다.
- 겹치는 interval·값이 다른 중복·잘못된 단위는 차단한다.
- 자정 넘김 interval은 임의 분할하지 않는다.
- 결측을 수치 0으로 조용히 대체하지 않는다.
- 필요한 경우에만 `inferred_zero_movement` proxy로 표시한다.
- proxy를 실제 비활동·미착용·full-day coverage로 저장하지 않는다.

기계 판독용 입력·출력 schema는 `contracts/`에 있다. 원본 필드 매핑은
`provider-field-map.json`, 전처리 알고리즘은 `preprocessing-rules.md`, 산식은
`formula-spec.md`에 있다.

## 3. Apple·Samsung·Health Connect 원본 매핑

| 목적 | Apple | Samsung |
|---|---|---|
| 걸음 | `HKQuantityTypeIdentifierStepCount.value/startDate/endDate` | `step_daily_trend/-2` 또는 `pedometer_day_summary`, interval step rows |
| 수면 | `HKCategoryTypeIdentifierSleepAnalysis.value/startDate/endDate` | `sleep_stage.stage/start_time/end_time` |
| 운동 | `Workout.startDate/endDate/duration` | `exercise.start_time/end_time/duration/datauuid` |
| HRV | `HeartRateVariabilitySDNN.value` | `hrv.rmssd` 또는 `hrv.sdnn` |
| RHR | `RestingHeartRate.value` | native RHR 없으면 일반 HR로 대체하지 않음 |
| HRR | `HeartRateRecoveryOneMinute.value` | recovery sidecar chart at 60,000ms ±2,000ms |

Samsung `source_type=0` 또는 기타 source를 `-2`로 추정하지 않는다. summary 충돌은
최신값·최대값으로 자동 선택하지 않고 `unknown_conflict`로 차단한다.

Health Connect 입력은 `StepsRecord`, `SleepSessionRecord`, `ExerciseSessionRecord`의
시간 구간과 `metadata.id`, `metadata.dataOrigin.packageName`, `metadata.device`를
보존한다. Health Connect는 여러 앱과 기기의 공유 저장소이므로 package name만 보고
하나의 센서로 간주하지 않는다. 승인된 data-origin lane을 선택하고, 동일 record의
재전송은 `metadata.id`로 dedupe한다. `StepsRecord` aggregate `COUNT_TOTAL`은 일별
총량 context로만 사용하며 timestamped 분산·공백·재활성화의 근거로 확장하지 않는다.
서로 다른 원천의 raw interval은 정책 없이 합산하지 않는다.

삼성헬스가 Health Connect로 동기화한 데이터는 `metadata.dataOrigin.packageName`이
`com.sec.android.app.shealth`인 Health Connect record로 들어온다. 이 경우 transport
provider는 `health_connect`로 유지하고 source identity를
`samsung_health_via_health_connect`로 표시한다. Samsung CSV의 `source_type=-2`로
변환하지 않으며, 원천을 삼성헬스로 제한할 때는 입력의
`allowed_data_origin_packages: ["com.sec.android.app.shealth"]`를 사용한다.

Health Connect 표준 수면 stage 값은 `UNKNOWN=0`, `AWAKE=1`, `SLEEPING=2`,
`OUT_OF_BED=3`, `LIGHT=4`, `DEEP=5`, `REM=6`, `AWAKE_IN_BED=7`이다. 자정을 넘는
수면 session은 임의로 분할하지 않고 local end day에 귀속한다. stage는 수면 routine
보조 정보로 보존하며 I2 활동이나 service action 완료로 변환하지 않는다.

## 4. I1 전처리와 산식

rich 입력은 `movement_minutes`, `active_partition_count`, `partition_count`,
`activity_concentration`이며 `sleep_shortfall_minutes`는 선택값이다.

`steps > 0`인 제공 interval을 movement로 바꾸고, `steps = 0`은 제공된 구간 안에서만
observed로 기록한다. interval 밖은 coverage로 확장하지 않는다. 상세한 파생 절차는
`preprocessing-rules.md`의 의사코드를 구현한다.

```text
movement_amount = clip(movement_minutes / 240, 0, 1)
movement_distribution = clip(active_partition_count / partition_count, 0, 1)
                         × clip((1 - activity_concentration) / 0.75, 0, 1)
low_burden = 0.5 × (1 - clip((movement_minutes - 240) / 240, 0, 1))
             + 0.5 × (1 - clip((activity_concentration - 0.50) / 0.50, 0, 1))
sleep_sufficiency = clip(1 - sleep_shortfall_minutes / 120, 0, 1)
raw_I1 = 35 + 55 × weighted_mean(available components)
```

가중치는 movement 0.20, distribution 0.30, low burden 0.25, sleep 0.25다.
수면이 없으면 cap 82를 적용한다. 일별 총 걸음수만 있으면 `context_only`이며 rich
numeric score로 승격하지 않는다.

## 5. I2 전처리와 산식

I2는 비활동 이후 재활성화만 평가하지 않는다. 하루 행동 실행을 구성하는 네 가지
context/action lane을 사용한다.

- `daily_steps` → `daily_step_volume` credit
- `post_anchor_action_credit` → 식후 등 anchor 이후 행동 연결
- `inactivity_break_credit` → 긴 추정 gap 이후 재활성화
- `movement_distribution_credit` → 하루 중 활동 분산

가중치는 각각 `0.55 / 0.20 / 0.15 / 0.10`이다. 단, daily total만 있으면
`context_only`이며 numeric score를 만들지 않는다. timed/action lane이 있으면
daily volume은 활동량 context로 산식에 포함할 수 있지만 service action 완료의 대체값으로
사용하지 않는다. 식후 행동은 운영이 기회와
완료 여부를 판정해 `post_anchor_action_credit`으로 전달하며, 계산기는 이 값을
산식에 포함한다. 상세 산식과 evidence cap은 `formula-spec.md`를 따른다.

## 6. I3 전처리와 산식

일별 history는 `volume`, `active_minutes`, `movement_bouts`, `exercise_sessions`,
`exercise_minutes`, `action_opportunities`, `action_completed`,
`action_unresolved`, `bedtime_minute_local`, `wake_time_minute_local`을 포함한다.

최근 7일과 직전 7일을 비교한다. 최근 window가 3일 미만이면 계산하지 않으며,
component별 양쪽 유효 관측이 3일 미만이면 해당 component를 제외하고 weight를
재정규화한다. volume·exercise·distribution은 유효 관측일 평균을 비교한다.

기본 weight는 volume 0.30, distribution 0.15, exercise 0.15, action 0.15,
persistence 0.10, sleep routine 0.15다. `completed`와 `not_completed`만 action
분모에 포함하고 `unknown`은 제외한다. 움직임만으로 completion을 생성하지 않는다.

## 7. 출력과 카테고리

모든 numeric score는 raw와 표시값을 함께 반환한다.

```json
{
  "status": "available",
  "raw_score": 52.4,
  "display_score_0_100": 49.82,
  "category": "middle",
  "coverage": {},
  "provenance": []
}
```

상태값은 `available`, `context_only`, `insufficient`, `unknown`이다.

- I1: 0~40 / 40~70 / 70~100
- I2: 0~33 / 33~66 / 66~100
- I3: 0~33 / 33~66 / 66~100

## 8. 운영과 계산기의 경계

운영은 timezone, source/provenance, meal/action event, `completed`·`not_completed`·
`unknown` 분류와 저장을 담당한다. 계산기는 전달받은 normalized 값의 형식·coverage·
provenance를 검증하고 산식을 계산한다. 어떤 행동을 service action으로 인정할지는
운영이 결정하며, 계산기가 걸음이나 움직임만으로 완료를 추정하지 않는다.

## 9. 실행 가능한 reference sample

`sample_v7_calculator.py`는 Python 표준 라이브러리만 사용한다. 외부 개발자는 별도
프로젝트 설치 없이 다음처럼 실행할 수 있다.

```bash
# 이미 표준화된 v7 입력을 계산
python3 sample_v7_calculator.py examples/v7-normalized-input.example.json

# Apple Health 형태의 timestamped step 샘플을 표준화한 뒤 계산
python3 sample_v7_calculator.py examples/v7-device-export.example.json --format device

# Health Connect record 샘플을 표준화한 뒤 계산
python3 sample_v7_calculator.py examples/v7-health-connect-export.example.json --format device

# 삼성헬스가 Health Connect로 동기화한 원천만 선택해 계산
python3 sample_v7_calculator.py examples/v7-health-connect-samsung-health.example.json --format device

# Samsung CSV converter의 재현 가능한 합성 입력과 end-to-end 검증
python3 test_health_connect_adapter.py
```

이 프로그램은 `device export → normalized v7 input → I1/I2/I3 output`의 최소 동작을
보여준다. `examples/v7-normalized-input.example.json`은 I1·I2와 관측 부족 상태의 I3를
보여주고, `examples/v7-device-export.example.json`은 14일 timestamped step 입력을
사용해 I3 7일 대 7일 비교가 실제로 실행되는 예시다.
`samsung_health_to_health_connect_fixture.py`는 실제 Samsung Health CSV export의 row를
Health Connect record 모양으로 변환하는 검증용 producer다. 실제 공개 데이터에서 생성한
파생 fixture는 라이선스·재배포 범위 확인 전 외부 handoff에 포함하지 않으며, 이 폴더에는
합성 샘플만 포함한다. Samsung 원본 row를
`com.sec.android.app.shealth` data origin으로 표시할 뿐, CSV가 Health Connect wire
format과 동일하다고 주장하지 않는다.

샘플 adapter가 인식하는 Apple 필드명은 `startDate/endDate/value`, Samsung 계열 필드명은
`start_time/end_time/step_count`, Health Connect 필드명은 `startTime/endTime/count` 및
`metadata.id/dataOrigin/device`다. Samsung row에 `source_type`이 있으면 `-2`만
native total lane으로 통과시키고 다른 값은 거부한다. 모든 timestamp는 timezone이 있어야 하며,
offset 없는 Health Connect 원본은 서비스가 감사 가능한 timezone을 명시적으로 주입하기 전까지
계산기에 넣지 않는다. 운영용
adapter에서는 실제 export schema, provenance, source lane, 중복·충돌 차단을 provider별로
확장해야 한다. 이 샘플은 인증·DB 저장·질문 수집·운영 UI를 구현하지 않는다.

실행 결과는 `status`, `raw_score`, `display_score_0_100`, `category`, `coverage`,
`provenance`를 포함한다. 원본 입력을 넣었을 때도 먼저 표준화하고, 산식 함수는 표준화된
값만 받도록 분리되어 있으므로 외부 개발자가 adapter와 calculator의 경계를 확인할 수 있다.

이 폴더의 v7 reference runner가 외부 구현의 정본이다. 저장소 루트의
`formula_normalized_indicator_calculator.py`는 기존 v5.7 호환 계산기이므로, 그 파일의
`volume_only` numeric score/cap 85 동작을 v7에 복사하지 않는다. v7에서는 일별 총합만
있을 때 I2를 `context_only`로 반환하고, timestamped lane 또는 action lane이 있을 때만
일일 걸음량을 다른 관측 component와 함께 사용한다.
외부 개발자는 저장소 루트의 호환 계산기를 참조할 필요 없이 이 handoff 폴더의
`sample_v7_calculator.py`와 `formula-spec.md`만 기준으로 구현한다.

실제 공개 Samsung export는 handoff에 포함하지 않는다. converter의 기본 동작은
`test_health_connect_adapter.py`가 임시 합성 ZIP을 생성해 검증한다. 실제 export를
사용하는 내부 검증에서는 같은 종류의 snapshot 파일이 여러 개이면 converter가 임의로
첫 파일을 선택하지 않고 중단한다.

참조 테스트는 외부 의존성 없이 다음처럼 실행할 수 있다.

```bash
python3 test_health_connect_adapter.py
```

## 10. 인수 테스트

- timezone/local-day 변환
- 중복·겹침·Samsung conflict 차단
- `source_type=-2`와 기타 source 분리
- inferred-zero proxy와 실제 inactivity 구분
- I1/I2 daily-total-only의 `context_only` 처리
- I3 7/7 window와 component별 최소 3일
- action unknown의 분모 제외
- raw → display 0~100 변환
- I1 40/70, I2·I3 33/66 경계
- Health Connect record metadata ID dedupe, data-origin 충돌 차단, aggregate context-only
- Health Connect cross-midnight sleep의 local end day 귀속

독립 구현의 검수 기준은 `acceptance-tests.md`다. 외부 개발자는 이 테스트를 자신의
언어·프레임워크로 재현해야 한다.
