# v7 원본 전처리 규칙

## 시간과 날짜

1. 원본 timestamp를 timezone-aware datetime으로 파싱한다.
2. 사용자 서비스 프로필의 IANA timezone으로 local datetime을 계산한다.
3. `local_day = local_datetime.date()`를 기준일로 사용한다.
4. timezone 없는 timestamp는 `unknown`으로 거부한다.
5. 자정 넘김 step interval은 daypart·gap 계산에서 제외하며 임의 분할하지 않는다.
   수면 session은 별도 규칙으로 local end day에 한 번 귀속한다.

## 중복과 충돌

- 동일 `source + start + end + metric + value`는 한 건으로 dedupe한다.
- 같은 구간의 값이 다르면 `unknown_conflict`로 차단한다.
- 겹치는 positive step interval은 합산하지 않는다.
- Samsung `source_type=-2`만 native all-source total로 인정한다.
- `source_type=0`과 기타 source를 `-2`로 추정하지 않는다.

## Health Connect

- `StepsRecord.startTime/endTime/count`를 timestamped step interval로 읽는다.
- `SleepSessionRecord.startTime/endTime/stages[]`는 하나의 수면 session으로 보존한다.
- `ExerciseSessionRecord.startTime/endTime`에서 duration minutes를 계산한다.
- 모든 record의 `metadata.id`, `metadata.dataOrigin.packageName`, `metadata.device`를
  provenance에 보존한다. 동일 `metadata.id`는 한 번만 사용한다.
- 원본에 기기 UUID만 있고 제조사·모델이 없으면 UUID를 `device.model`로 복사하지 않는다.
  UUID는 `clientRecordId` 또는 별도 source-device identifier로 보존하고 모델은 unknown으로 둔다.
- id가 없으면 `(dataOrigin, start, end, value)`를 fallback dedupe key로 사용한다.
- 서로 다른 data origin의 겹치는 step interval은 합산하지 않고 충돌로 차단한다.
  aggregate total을 사용할 때는 raw interval lane과 섞지 않는다.
- 여러 data origin이 동시에 들어오면 `allowed_data_origin_packages` 없이 계산하지 않는다.
  하나의 승인된 source lane을 선택한 뒤 나머지는 거부한다.
- Samsung Health에서 동기화된 record는 `dataOrigin.packageName`이
  `com.sec.android.app.shealth`일 때 `samsung_health_via_health_connect`로 표시한다.
  운영이 이 원천만 사용하기로 한 경우 `allowed_data_origin_packages`에 해당 package를
  지정하고 다른 원천은 거부한다. 이 record를 Samsung CSV의 `source_type=-2`로 역변환하지 않는다.
- `StepsRecord.COUNT_TOTAL` aggregate만 들어오면 일별 총량 context-only로 처리한다.
  timestamped 분산·I2 gap 재활성화·I3 active minutes에는 사용하지 않는다.
- 자정을 넘는 수면 session은 local end day에 한 번 귀속한다. 수면을 임의로 두 row로
  분할하지 않는다.
- `SleepSessionRecord.Stage` 값은 수면 stage로만 보존한다. `AWAKE`·`OUT_OF_BED`를
  활동량, 비활동 gap, service action completion으로 승격하지 않는다.

## Timestamped step 파생 의사코드

```text
valid = parse_and_validate_step_rows(rows)
valid = convert_to_user_local_timezone(valid)
valid = keep_same_local_day_intervals(valid)
valid = deduplicate_exact_rows(valid)
reject_if_overlapping(valid)

positive = rows where steps > 0
movement_minutes = sum(end - start for positive)
daily_steps = sum(steps for all valid rows)

for each fixed local-day partition:
    partition_minutes = overlap(partition, positive)
active_partition_count = count(partition_minutes > 0)
partition_count = number of configured partitions
activity_concentration = max(partition_minutes) / movement_minutes

for each adjacent positive interval:
    gap = next.start - previous.end
    if gap >= 60 minutes:
        total_inferred_gap_minutes += gap
        if first_activity_after_long_gap_steps is empty:
            first_activity_after_long_gap_steps = next.steps

total_inferred_gap_minutes = min(total_inferred_gap_minutes, 900)
gap_quality = clip(1 - total_inferred_gap_minutes / 900, 0, 1)
reactivation_quality = clip(first_activity_after_long_gap_steps / daily_steps / 0.25, 0, 1)
inactivity_break_credit = 0.70 * reactivation_quality + 0.30 * gap_quality
movement_distribution_credit = clip(active_partition_count / partition_count, 0, 1)
                         * clip((1 - activity_concentration) / 0.75, 0, 1)
coverage_provenance = "coverage_unproven_inferred_zero_proxy"
```

이 proxy는 기록 공백을 계산에 사용하는 것이며 실제 비활동·기기 미착용·full-day
coverage를 관측했다는 뜻이 아니다. positive interval이 하나뿐이면 reactivation은
`null`이고 `inactivity_break_credit`도 `null`이다. `movement_distribution_credit`와
`inactivity_break_credit`를 I2에 전달한다. 식사 등 anchor 이후 행동은 device movement에서
생성하지 않고, 운영이 판정한 `completed`/`not_completed`/`unknown` 결과를
`post_anchor_action_credit`으로 변환해 전달한다.

## 수면·운동·action

- stage interval이 있으면 asleep minutes, in-bed minutes, efficiency, transition을 계산한다.
- duration-only 수면은 수면시간 context로만 사용하며 routine·fragmentation으로 승격하지 않는다.
- sleep session은 provider id 또는 동일 start/end로 dedupe한다.
- 운동 duration은 분으로 통일하고 source session id로 dedupe한다.
- action anchor는 서비스가 제공해야 하며 movement에서 만들지 않는다.
- `completed`, `not_completed`, `unknown`은 운영에서 판정한다.
- `unknown`은 action 분모에서 제외한다.

## 금지되는 변환

- missing을 observed zero로 대체
- 일반 심박을 Samsung RHR로 대체
- Apple SDNN을 RMSSD로 변경
- summary conflict에서 최신값·최대값을 임의 선택
- movement observation을 action completion으로 승격
- awake-region을 fragmentation transitions/hour로 승격
