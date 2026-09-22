# 외부 개발자 인수 테스트

다음 테스트는 외부 개발자가 자신의 언어·프레임워크로 재현해야 한다.

| ID | 입력 상황 | 기대 결과 |
|---|---|---|
| T01 | timezone 있는 Apple step interval | 사용자 local day로 집계 |
| T02 | timezone 없는 timestamp | row 제외 또는 unknown |
| T03 | 동일 interval exact duplicate | 한 번만 집계 |
| T04 | 겹치는 step interval | 해당 day high-resolution 계산 차단 |
| T05 | 자정 넘김 interval | daypart/gap 계산에서 제외 |
| T06 | Samsung source_type=-2 | native all-source lane |
| T07 | Samsung source_type=0 | -2로 변환하지 않음 |
| T08 | Samsung summary 값 충돌 | unknown_conflict, 임의 선택 금지 |
| T09 | positive intervals 여러 개 | I1 movement·partition·I2 gap 파생 |
| T10 | positive interval 하나 | I2 reactivation lane null; reactivation만으로 score를 만들지 않음 |
| T11 | daily total-only | I1/I2 context_only |
| T12 | I3 최근 관측 2일 | insufficient |
| T13 | I3 component 기준 window 2일 | 해당 component 제외 |
| T14 | completed 1, not_completed 1, unknown 1 | opportunity 2, completed 1, unknown 분모 제외 |
| T15 | movement만 있고 service completion 없음 | completion 생성 금지 |
| T16 | sleep duration-only | routine/fragmentation 승격 금지 |
| T17 | I1 raw 35/62.5/90 | display 0/50/100 |
| T18 | I2 raw 0/50/100 | display 0/50/100 |
| T19 | I3 raw 30/50/70 | display 0/50/100 |
| T20 | category 경계값 | I1 40·70, I2/I3 33·66 적용 |
| T21 | post-anchor action credit 0/1 | I2 action lane이 낮음/높음 방향으로 움직임 |
| T22 | post-anchor outcome unknown | I2 action credit에서 임의 완료·미완료로 변환하지 않음 |
| T23 | Health Connect 동일 `metadata.id` 재전송 | 한 건만 집계 |
| T24 | 서로 다른 data origin의 겹치는 StepsRecord | 합산하지 않고 충돌 차단 |
| T25 | Health Connect `COUNT_TOTAL`만 존재 | I1/I2 context_only, interval 파생 금지 |
| T26 | offset 없는 Health Connect timestamp | timezone 보강 전 거부 |
| T27 | 자정을 넘는 SleepSessionRecord | local end day에 한 번 귀속 |
| T28 | Health Connect exercise session | end-start를 분 단위로 변환 |
| T29 | 실제 Samsung Health CSV row를 fixture producer로 변환 | record id·count·timestamp·Samsung origin 보존 |
| T30 | 변환된 Samsung interval에 겹침 존재 | 해당 day I1/I2 rich lane 차단, I3 volume replay는 별도 수행 |
| T31 | Health Connect data origin 2개, allowlist 없음 | source policy required로 계산 차단 |
| T32 | Apple/Samsung 수면 session이 자정을 넘음 | local end day에 한 번 귀속 |
| T33 | Samsung ZIP에 같은 종류의 snapshot이 2개 이상 | 자동 선택하지 않고 변환 차단 |
| T34 | 합성 Samsung CSV ZIP → Health Connect-shaped JSON | 실제 원본 없이 record id·device UUID·Samsung origin 보존 |
| T35 | normalized/output sample을 contract shape에 대조 | required field·범위·추가 필드 위반 차단 |

모든 결과는 `status`, `raw_score`, `display_score_0_100`, `category`, `coverage`,
`provenance`를 반환해야 한다. 상태값은 `available`, `context_only`,
`insufficient`, `unknown`이다.
