# maiReport v7.0 지표산식 검토

검토일: 2026-09-22. 범위: 전달 폴더의 명세·전처리·스키마·샘플 계산기·변환기·테스트. 원본은 수정하지 않았다. 문서 안의 개발자 지시는 검토 대상 사양으로 취급했다.

**판정: 구현용 초안으로는 활용할 수 있으나, 현재 상태를 외부 개발의 확정 기준으로 사용하기에는 점수 오류와 정의 누락이 있다.** 아래의 확정 오류와 정책 판단 사항을 구분해 해결해야 한다. 이 검토는 산식의 논리·재현성과 구현 일치성 검토이며, 건강 효과나 임상 타당성을 입증하는 검증은 아니다.

## 1. 우선 수정할 구현 오류

### 1) I3 수면 규칙성 항목이 정상 입력에서 항상 누락됨 — 높음 / 실행 재현

[계산기 210행](C:/Users/이사라/Documents/Project_maiReport/지표산식_정훈샘/maireport-external-developer-v7.0-handoff/sample_v7_calculator.py:210) 및 260행. 계약은 취침·기상 시각을 day.i3 안에 저장하지만 routine_stability는 day 바로 아래에서 읽는다. 14일 모두 유효한 수면 시각을 넣어도 수면 component가 생기지 않는다. 수면만 있으면 insufficient, 다른 항목이 있으면 수면의 15% 가중치를 빼고 재계산된다.

수정: i3 내부를 읽고, 양쪽 기간에 각각 최소 3일을 확인한다. 별도로 23:50·00:00·00:10을 일반 숫자 표준편차로 처리하면 자정 부근의 규칙적인 수면을 불규칙으로 오인한다. 기준시각에 맞춰 시각을 펼치거나 원형 통계를 사용해야 한다. 현재 입력 경로 오류에 가려진 두 번째 문제다.

### 2) 겹친 걸음 기록이 I3 총량에는 그대로 합산됨 — 높음 / 실행 재현

[계산기 529행](C:/Users/이사라/Documents/Project_maiReport/지표산식_정훈샘/maireport-external-developer-v7.0-handoff/sample_v7_calculator.py:529), 일반 adapter 375행. 08:00~09:00 100걸음과 08:30~09:30 200걸음이 들어오면 충돌을 기록하지만 volume=300을 반환한다. I1/I2의 시간 관련 값만 비우고 I3 총량은 유효값으로 남긴다. 따라서 중복 수집이 최근 기간에 늘면 활동 개선으로 해석할 수 있다.

수정: 충돌한 원본으로 만든 일일 총량도 무효화한다. 별도로 검증한 aggregate를 사용하려면 출처와 선택 규칙을 명시한다. 인수 테스트 T30의 “I3 volume replay는 별도 수행”은 충돌 총량 사용을 허용하는지 모호하므로 함께 정리한다.

### 3) 수면 중 깨어 있던 시간까지 수면시간으로 계산 — 높음 / 실행 재현

[계산기 554행](C:/Users/이사라/Documents/Project_maiReport/지표산식_정훈샘/maireport-external-developer-v7.0-handoff/sample_v7_calculator.py:554), 일반 adapter 398행. stages를 보존하지만 수면 부족분은 session의 end-start 전체로 계산한다. 8시간 세션 중 2시간 AWAKE, 6시간 SLEEPING인 입력에도 부족분이 0분이다. 현재 코드의 480분 목표를 그대로 적용하더라도 실제 수면 기준이면 부족분은 120분이어야 한다.

수정: 유효한 수면 단계의 시간을 합집합으로 집계하고, 깨어 있음·미상·stage 공백 처리 및 duration-only 대체 규칙을 정의한다. Apple의 겹친 in-bed/stage 구간도 단순 합산하면 안 된다. 공식 API도 깨어 있음과 수면을 구분한다. [Android 수면 단계 정의](https://developer.android.com/reference/androidx/health/connect/client/records/SleepSessionRecord).

### 4) 결측을 0으로 바꿔 I3 비교에 포함 — 높음 / 실행 재현

[계산기 416행](C:/Users/이사라/Documents/Project_maiReport/지표산식_정훈샘/maireport-external-developer-v7.0-handoff/sample_v7_calculator.py:416) 및 579행. 운동 기록이 없으면 exercise_minutes=0으로 저장한다. Health Connect 수면만 있는 날에도 active_minutes=0, 일반 adapter는 걸음이 없는 날 volume=0까지 생성한다. 권한 없음·미수집·진짜 0을 구별할 수 없다.

수정: 기록이 없고 관측을 보장할 수 없으면 null. 관측 범위가 확인된 실제 0만 0으로 저장한다. 그렇지 않으면 연동 시작·권한 변경이 행동 변화로 점수화된다.

### 5) 시간 구간 경계를 넘는 활동을 시작 구간에 몰아넣음 — 높음 / 실행 재현

[계산기 536행](C:/Users/이사라/Documents/Project_maiReport/지표산식_정훈샘/maireport-external-developer-v7.0-handoff/sample_v7_calculator.py:536), 일반 adapter 380행. 08:50~09:10 활동은 3시간 단위 구획에서 두 구획에 걸치는데, 현재는 active_partition_count=1, concentration=1이다. 명세의 overlap 방식이면 각 10분, count=2, concentration=0.5가 된다. I1/I2 분산 점수가 달라진다.

수정: 각 고정 구획과 interval의 교집합 시간을 배분한다. 기본 구획 수·경계·시간대 정책도 명세에 고정한다.

### 6) Health Connect에서 자정 넘는 걸음 구간이 제외되지 않음 — 높음 / 실행 재현

[계산기 462행](C:/Users/이사라/Documents/Project_maiReport/지표산식_정훈샘/maireport-external-developer-v7.0-handoff/sample_v7_calculator.py:462). Apple/Samsung 경로에는 날짜 비교가 있지만 Health Connect에는 없다. 23:50~다음 날 00:10이 전날의 rich 활동 20분으로 처리된다. 전처리 규칙 및 T05와 다르다.

수정: 자정 넘김의 시간 기반 파생 금지를 공통 함수로 적용하고, 총량 귀속은 별도로 확정한다.

### 7) I2 evidence cap이 명세와 불일치 — 중간 / 실행 재현

[명세 46행](C:/Users/이사라/Documents/Project_maiReport/지표산식_정훈샘/maireport-external-developer-v7.0-handoff/formula-spec.md:46), [계산기 162행](C:/Users/이사라/Documents/Project_maiReport/지표산식_정훈샘/maireport-external-developer-v7.0-handoff/sample_v7_calculator.py:162). daily volume(0.55)+분산(0.10)만 있고 두 credit이 1이면 명세상 cap은 55+0.65×45=84.25다. 코드는 과거 volume_only 정책의 85 하한을 적용해 85점을 반환한다. 문서는 그 정책이 v7에 적용되지 않는다고 한다.

또한 “3개 이상이면 최소 95”는 코드에서 daily_step_volume이 있는 경우만 적용된다. volume 없이 나머지 3개가 있는 경우의 정책도 명시해야 한다. 명세와 실행 코드 중 정본을 확정하고 수치 예제를 추가한다.

### 8) 같은 날짜의 중복 행이 최소 관측일 조건을 통과함 — 높음 / 실행 재현

[계산기 219행](C:/Users/이사라/Documents/Project_maiReport/지표산식_정훈샘/maireport-external-developer-v7.0-handoff/sample_v7_calculator.py:219). 유효 일수가 아니라 행 개수를 센다. 기준 기간 하루를 3번, 최근 기간 하루를 3번 넣으면 실제 관측은 각 1일인데 available을 반환한다. 재현 입력에서는 표시 87.5점이다.

수정: 날짜당 하나의 정규화 행을 강제하고 중복 날짜·상충 값은 계산 전에 차단한다. 최신 기록일을 기준일로 사용하는 정책도 문서에 명시해야 한다. 현재는 과거 데이터만 있어도 그 과거 시점 점수를 반환한다.

### 9) 결과가 자체 출력 스키마를 위반하고 입력 검증도 빠짐 — 중간 / 구조 및 실행 값 대조

[계산기 117행](C:/Users/이사라/Documents/Project_maiReport/지표산식_정훈샘/maireport-external-developer-v7.0-handoff/sample_v7_calculator.py:117) 및 265행에서 부족 상태의 available_components/components를 숫자 0으로 반환한다. [출력 스키마](C:/Users/이사라/Documents/Project_maiReport/지표산식_정훈샘/maireport-external-developer-v7.0-handoff/contracts/indicator-v7-output.schema.json:36)는 배열을 요구하므로 빈 배열이어야 한다. 문서에서 필수인 coverage/provenance도 스키마 required에는 없다.

calculate()는 버전 외에 입력 스키마·단위·provenance·관측 상태를 검증하지 않는다. active_partition_count<=partition_count, completed<=opportunities 등의 교차 조건도 필요하다. completed 초과를 min()으로 조용히 잘라내면 원본 오류가 감춰진다.

기존 계약 테스트는 키 존재 여부 위주이며 JSON Schema 전체 검증이 아니다. 이번 환경에는 jsonschema가 없어 정식 validator는 실행하지 않았고, 위 두 타입 불일치는 실제 반환값과 스키마를 직접 대조했다.

## 2. 산식 설계·표현에서 결정해야 할 사항

### A) “활동시간”이 실제 활동시간이 아니라 기록 구간 길이임

전처리는 steps>0이면 end-start 전체를 movement_minutes로 본다. 재현상 같은 100걸음도 1분 구간이면 1분, 60분 구간이면 60분이다. Health Connect StepsRecord는 구간의 걸음 수를 담으며, 그 구간 전체에서 계속 걸었다는 보장은 정의에 없다. [Android StepsRecord 정의](https://developer.android.com/reference/androidx/health/connect/client/records/StepsRecord).

이는 코드 버그만의 문제가 아니라 현 명세의 가정이다. 최대 허용 구간 길이·입력 해상도·provider별 적격 조건을 정하고 검증해야 한다. 그 전에는 “추정 활동 구간 시간”처럼 proxy임을 드러내는 이름이 더 정확하다. 수집 해상도가 바뀌면 I3 개선 점수도 영향을 받는다.

### B) I1은 자료가 적어도 100점 가능하고, 활동 증가 시 감점됨

rich 입력에 sleep_shortfall=0만 있으면 가중치 재정규화로 표시 100점이 나온다. 스키마상 다른 항목이 null인 입력을 막지 않는다. rich의 필수 충족 조건과 최소 관측 근거를 명시해야 한다.

분산·수면 조건을 고정하고 활동을 240분에서 480분으로 늘리면 재현 입력의 표시 점수는 85→72.5로 내려간다. movement 가점은 240분에서 포화되지만 low_burden은 이후 감소하기 때문이다. 의도한 “균형/부담” 점수라면 설명과 검증이 필요하며, 일반 활동 실천 점수라면 사용자 기대와 충돌할 수 있다.

### C) I2 “식후 행동”과 “비활동 해소”의 의미가 점수보다 강함

식후 항목이 없어도 다른 값들로 I2 점수가 나온다. 식후 행동은 운영 판정이라고만 되어 있어 식사 후 몇 분 이내, 어떤 행동·지속시간, 복수 기회 가중치, 판정 마감, unknown 전환 시점이 비어 있다. 동일한 생활 기록을 개발사마다 다르게 판정할 수 있다.

gap credit은 첫 번째 긴 공백 이후의 활동만 사용한다. 긴 공백이 없으면 이 component가 null이고, 공백이 생기면 새 component가 추가된다. 나중의 걸음이 증가해 daily_steps 분모가 커지면 첫 재활성화 비율은 감소한다. 이런 비단조 동작을 의도했는지 확인해야 한다. coverage_unproven_inferred_zero_proxy 표기는 명세에 있으나 실제 출력에는 보존되지 않는다.

수정 방향: 행동 기회 판정표와 집계식을 별도 계약으로 만들고, “추정 기록 공백 이후 활동”이라는 측정 의미를 명확히 한다. 관측 근거 수준은 점수와 별도 표시하는 방안도 검토할 수 있다.

### D) I3 distribution·persistence 이름과 실제 계산이 다름

I3 distribution은 시간대 분산이 아니라 active_minutes의 평균 변화다. 한 번에 몰아 움직여도 값이 증가할 수 있으므로 “활동시간 변화”로 명명하거나 실제 분산값을 사용해야 한다.

persistence는 관측된 날 중 1걸음이라도 있는 날의 비율이다. 양쪽 모든 관측일에 걸음이 조금이라도 있으면 항상 변화 0이고, 목표 행동의 지속 여부는 측정하지 않는다. “관측일 중 걸음 발생일 비율”이 현재 정의에 맞다.

I3 표시 50은 변화 없음, 0은 감소 방향 포화, 100은 증가 방향 포화다. 절대 건강 수준이나 목표 달성률이 아니다. low/middle/high보다 “감소/유지/증가” 등 변화 지표임을 드러내는 표현을 검토해야 한다. 각 기간에 관측된 항목 구성·기기·수집 해상도가 바뀌면 비교 가능성도 확인해야 한다.

### E) 주요 상수와 빠진 정의

240분·480분·120분·60분 gap·900분 cap·25% 재활성화 기준·각 weight·category 경계의 선정 근거와 보정 절차가 폴더에 없다. 이것만으로 잘못된 상수라고 단정할 수는 없지만, “검증된 기준”이라고 설명할 근거도 이 전달물에는 없다.

I3 sleep routine의 표준편차 방식·15분 분모 하한은 코드에만 있고 formula-spec에 완전한 수식이 없다. 반올림 전후 category 판정 순서, 날짜 기준, 잠/운동의 날짜 귀속, partial 데이터의 점수 비교 조건도 고정해야 한다.

README의 raw=52.4 / display=49.82 예시는 어느 지표에도 맞지 않는다. I1이면 약 31.64, I2면 52.4, I3이면 56이다. indicator를 밝히고 값을 바로잡아야 한다.

## 3. 추가 adapter 인계 누락 — 정적 검토

- 일반 adapter의 운동 duration은 단위를 변환하지 않고 session ID 중복도 제거하지 않는다(367행). provider-field-map에는 durationUnit이 있으므로 단위 계약을 실제로 적용해야 한다.
- Health Connect steps의 device/client record 식별자는 읽어 놓고 최종 정규화에는 record ID와 package만 남긴다(558행). exercise provenance도 최종 출력에서 사라진다. 문서의 보존 요구를 충족하지 못한다.
- allowed_data_origin_packages에 여러 package를 넣을 수 있어 “승인된 하나의 source 선택”이 강제되지 않는다. aggregate는 source 정책 검사 대상에서도 빠져 있으며 같은 날 중복 aggregate가 있으면 마지막 값으로 덮어쓴다(482행).
- 같은 metadata.id의 수정본을 재전송 중복으로 간주해 먼저 읽은 값만 남긴다(469행). 동일 재전송과 수정·충돌을 구별하는 정책이 필요하다.
- [Samsung 변환기 82행](C:/Users/이사라/Documents/Project_maiReport/지표산식_정훈샘/maireport-external-developer-v7.0-handoff/samsung_health_to_health_connect_fixture.py:82): record ID 누락 시 generated-deviceID를 공통으로 만들어 같은 기기의 여러 기록이 중복으로 사라질 수 있다. ID를 비워 adapter의 fallback key를 쓰거나 내용 기반 안정적 ID를 만들어야 한다.
- [Samsung 변환기 95행](C:/Users/이사라/Documents/Project_maiReport/지표산식_정훈샘/maireport-external-developer-v7.0-handoff/samsung_health_to_health_connect_fixture.py:95): 특정 202109221041 파일이 있으면 우선 선택하므로 다른 snapshot이 함께 있어도 차단 규칙을 우회한다. 기존 T33 테스트는 helper만 검사하므로 convert() 전체 경로에 대한 검증이 필요하다.

## 4. 검증 내역과 수정 순서

동봉 test_health_connect_adapter.py의 12개 함수는 모두 통과했다. 추가 합성 입력의 결과는 outputs/v7_review_repro_results.json, 재현 코드는 outputs/v7_review_repro.py에 있다. 실제 사용자 데이터나 기기 동기화를 시험한 결과는 아니다.

권장 순서:

1. 수면 입력 경로·수면시간·결측/0·충돌 총량·시간 구획·자정 넘김·중복 날짜 오류 수정.
2. I1 최소 근거, I2 cap 및 행동 인정 규칙, I3 수면 수식과 지표 의미 확정.
3. 하나의 명세·스키마·코드로 일치시키고, T01~T35 각각을 실제 검증 입력과 정확한 기대값에 연결.
4. 동일 행동을 다른 기록 해상도·source·누락률로 표현해도 결과가 허용 범위 안인지 비교 검증.

개발자에게 전달할 핵심 문장: “v7 계산기의 실행 가능 여부는 확인했으나, 문서와 코드의 일치 및 결측·중복·수면·시간 구간 처리가 아직 인수 가능한 수준으로 검증되지 않았습니다. 재현 사례를 기준으로 수정 후 산식 정본을 다시 확정해 주세요.”

