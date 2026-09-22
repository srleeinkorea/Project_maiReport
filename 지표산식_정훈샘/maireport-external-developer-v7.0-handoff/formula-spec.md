# v7 산식 명세

## I1

입력: `movement_minutes`, `active_partition_count`, `partition_count`,
`activity_concentration`, 선택적 `sleep_shortfall_minutes`.

```text
movement_amount = clip(movement_minutes / 240, 0, 1)
movement_distribution = clip(active_partition_count / partition_count, 0, 1)
                         * clip((1 - activity_concentration) / 0.75, 0, 1)
low_burden = 0.5 * (1 - clip((movement_minutes - 240) / 240, 0, 1))
             + 0.5 * (1 - clip((activity_concentration - 0.50) / 0.50, 0, 1))
sleep_sufficiency = clip(1 - sleep_shortfall_minutes / 120, 0, 1)
raw = 35 + 55 * weighted_mean(available components)
```

가중치: movement 0.20, distribution 0.30, low burden 0.25, sleep 0.25.
수면이 없으면 cap 82를 적용한다. daily total-only는 `context_only`다.
raw 35~90은 `(raw - 35) / 55 * 100`으로 display한다.

## I2

입력 component는 `daily_steps`, `post_anchor_action_credit`,
`inactivity_break_credit`, `movement_distribution_credit`이다. 식후 활동은
`post_anchor_action_credit`로 전달되는 핵심 action lane이며, 움직임만으로 완료를
추정하지 않는다.

```text
daily_step_volume = piecewise_credit(daily_steps,
  [(0, 0.00), (3000, 0.35), (6000, 0.65), (10000, 0.95), (12000, 1.00)])
features = {
  daily_step_volume,
  postmeal_activity_timing: post_anchor_action_credit,
  inactivity_break_reactivation: inactivity_break_credit,
  movement_distribution: movement_distribution_credit
}
raw = weighted_mean(available features) * evidence_cap(available features)
```

가중치는 daily step volume 0.55, post-meal/anchor action 0.20,
inactivity-break reactivation 0.15, movement distribution 0.10이다. daily total만
있으면 `context_only`이며 numeric score를 만들지 않는다. timed/action component가
있으면 daily step volume은 활동량 context로 산식에 포함할 수 있지만, service action
완료를 대신하지 않는다. scoreable component가 일부만 있으면 evidence cap은
`partial_base 55 + observed_weight × 45`, 3개 이상의 context component가 있는 경우
최소 95, full context는 100이다. `volume-only 85`는 v5.7 호환 계산기의 역사적
정책이며 v7 계산 결과에는 적용하지 않는다. I2 raw와 display는
모두 0~100이며 I2 category 경계는 33/66이다.

`post_anchor_action_credit`는 운영이 식사 등 anchor 이후 행동 기회의 완료 여부를
`completed`/`not_completed`/`unknown`으로 판정해 0~1 credit으로 변환한 값이다.
`unknown`은 완료 credit이나 기회 분모에 임의로 포함하지 않는다. 어떤 이벤트를
식후 행동으로 인정할지는 운영이 결정하고 계산기는 전달받은 credit만 사용한다.

## I3

최근 7 calendar days와 직전 7 calendar days를 비교한다. 최근 window 유효 관측이
3일 미만이면 계산하지 않는다. 각 component가 양쪽 window에 3일 미만이면 제외한다.

```text
generic_signal = clip(
  (recent_observed_day_mean - baseline_observed_day_mean)
  / max(abs(baseline_mean) * 0.50, 1), -1, 1
)
action_signal = clip(
  (recent_completed / recent_opportunities
   - baseline_completed / baseline_opportunities) / 0.50, -1, 1
)
raw = 50 + 20 * clip(weighted_mean(available signals), -1, 1)
```

여기서 `distribution`은 일별 `active_minutes`, `exercise`는 일별
`exercise_minutes`를 사용한다. `persistence`는 volume이 관측된 날 중 `volume > 0`인
비율이다. action은 각 날짜의 rate를 평균하지 않고, 각 window의
`completed`와 `opportunities`를 먼저 합산한 뒤 window 완료율을 비교한다.
`unknown`은 opportunities와 completed에 포함하지 않는다. component에 필요한 유효
관측일이 양쪽 window에서 3일 미만이면 그 component를 제외하고 나머지 weight를
재정규화한다. 가중치는 volume 0.30, distribution 0.15, exercise 0.15, action 0.15,
persistence 0.10, sleep routine 0.15다. raw 30~70은 `(raw - 30) / 40 * 100`으로
display한다.

## Category

- I1: display `<40` low, `40~<70` middle, `>=70` high
- I2: display `<33` low, `33~<66` middle, `>=66` high
- I3: display `<33` low, `33~<66` middle, `>=66` high
