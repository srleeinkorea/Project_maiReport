# QA 에이전트

기능 하나의 구현이 **기준 문서(데이터 계약·확정 규칙)대로 됐는지** 검증하고 보고서를 만든다.
설계 이유와 다른 기능으로 넓히는 법은 `outputs/qa/maiReport_QA에이전트_설계설명_v1.0.0.html`에 있다.

## 빠른 시작

Node 20 이상이 필요하다. 설치 패키지는 없다.

```
# 식이 QA 다시 돌리기 → outputs/qa/식이-<오늘>/식이_QA보고서.html
node qa-agent/bin/qa.mjs run qa-agent/plans/식이.qa-plan.json

# node가 PATH에 없을 때 (Windows)
powershell -NoProfile -ExecutionPolicy Bypass -File qa-agent/qa.ps1 run qa-agent/plans/식이.qa-plan.json
```

Claude Code에서는 이렇게 부른다.

- `/feature-qa 수면 outputs/mai-report-policy/수면` — 지금 대화에서 6단계 절차를 진행 (정책 질문을 바로 물어볼 수 있음)
- 「feature-qa 에이전트로 수면 QA 돌려줘」 — 별도 에이전트에게 맡김 (여러 기능을 동시에 돌릴 때)

## 구성

| 위치 | 하는 일 |
|---|---|
| `.claude/skills/feature-qa/SKILL.md` | **절차** — 6단계, 지키는 규칙, 심각도 기준 |
| `.claude/agents/feature-qa.md` | **역할** — 제3자 검증자로서의 권한과 보고 형식 |
| `qa-agent/bin/qa.mjs` | **실행기** — init · extract · run |
| `qa-agent/plans/<기능>.qa-plan.json` | **케이스 묶음** — 기능마다 하나, 회차마다 쌓인다 |
| `outputs/qa/<기능>-<날짜>/` | **결과** — 보고서 HTML, 요약 MD, results.json, 그날 계획 사본 |

## 명령

| 명령 | 하는 일 |
|---|---|
| `init <기능> --target <폴더>` | 폴더를 훑어 테스트·계약 엑셀·규칙 시트·내보낸 함수를 보여 주고 계획 뼈대를 만든다 |
| `extract <엑셀> [--sheet 이름,이름] [--out x.json]` | 시트 목록, 또는 지정 시트의 행을 한 줄씩 보여 준다 |
| `run <계획> [--out 폴더] [--date YYYY-MM-DD]` | 실행하고 보고서를 쓴다. 종료 코드 0 통과·조건부, 1 보류, 2 계획 오류 |

## 계획 파일 쓰는 법

완성 예시: `qa-agent/plans/식이.qa-plan.json`. 경로는 `target`은 저장소 기준, 나머지는 `target` 기준이다.

| 필드 | 뜻 |
|---|---|
| `feature` | 기능 이름. 결과 폴더 이름이 된다 |
| `target` | 검증 대상 폴더 |
| `baseline.contract` | 정답지 엑셀. 데이터 점검과 규칙 추적에 쓴다 |
| `baseline.ruleSheets` | 규칙이 적힌 시트 `{sheet, idField, textField}`. 보고서의 규칙 추적표가 된다 |
| `scope.in` / `scope.out` | 이번에 확인한 것 / 안 한 것 |
| `existingTests` | 이미 있는 `node --test` 파일. 먼저 돌린다 |
| `fixtures` | 여러 케이스가 같이 쓰는 입력에 이름을 붙인다 |
| `cases` | 함수를 실제로 불러 보는 시나리오 |
| `dataChecks` | 계약 엑셀 데이터 점검, 문서 숫자 대조 |
| `findings` | 실행으로 못 보이는 것을 코드 읽기로 찾은 불일치 |
| `openQuestions` | 정책이 애매해 사람이 정해야 하는 질문 |

### 시나리오 케이스 (`cases`)

```json
{
  "id": "QA-DIET-01",
  "title": "관찰 중인 축은 목표 단계가 오르지 않는다",
  "scenario": "지영 씨는 채소 축이 '관찰 중'이다. 사흘 연속 완료하고 7일에 앱을 연다 → 단계는 '시작'에 머물러야 한다.",
  "rules": ["V-42"],
  "severity": "높음",
  "module": "diet-goal-engine-v1.0.0.mjs",
  "export": "recalculateAxisStage",
  "args": { "currentStage": "INTRO", "axisState": "OBSERVING", "goals": { "$fixture": "사흘연속완료" }, "asOfDate": "2026-10-07" },
  "expect": { "stage": "INTRO" }
}
```

- `args`가 배열이면 펼쳐서(`fn(a, b)`), 객체면 그대로(`fn(obj)`) 넘긴다.
- `expect`는 **적은 키만** 비교한다. 연산자: `$in` `$ne` `$gt` `$gte` `$lt` `$lte` `$exists` `$contains` `$length`.
- 오류가 나야 맞으면 `"expectError": "메시지 일부"`.
- 두 입력의 결과가 같아야 하면 `"type": "same"`, `"calls": [{label, args}, {label, args}]`, `"compare": "결과 안 경로"`.
- 보고서용 선택 필드: `basis`(규칙 번호 외 근거), `where`(파일:줄), `suggestion`, `note`.

### 데이터 점검 (`dataChecks`)

| `check` | 필요한 값 | 예 |
|---|---|---|
| `count` | `sheet`, `expected`, (`where`) | 질문 행이 8개다 |
| `unique` | `sheet`, `keys` | ID+버전이 겹치지 않는다 |
| `allIn` | `sheet`, `field`, `values` | 상태는 READY만 |
| `range` | `sheet`, `field`, `min`·`max` | 백분위는 0~100 |
| `maxLength` | `sheet`, `field`, `max` | 타일 문구 22자 이하 |
| `notEmpty` | `sheet`, `field` | 이유 문장 빈칸 없음 |
| `groupCount` | `sheet`, `by`, `expected` | 질문마다 선택지 3개 |
| `sameKeys` | `sheets`(2개), `keys` | 두 시트가 일대일 |
| `foreignKey` | `sheet`, `field`, `refSheet`, `refField` | 참조한 ID가 실제로 있다 |

`where`는 `{필드: 값}` 또는 `{필드: [값, 값]}`. 문서 숫자 대조는 `"kind": "문서 대조"`와 `"basis": "어느 문서 몇 행"`을 붙인다.

### 코드 읽기 발견 (`findings`)

`id, title, scenario, rules, severity, where, evidence, suggestion`. `status`를 생략하면 실패로, `"확인 필요"`로 두면 정책 질문 칸에 나온다.

## 판정

| 판정 | 조건 |
|---|---|
| 보류 | 기존 테스트 실패, 심각도 높음 실패, 또는 실행 오류가 하나라도 있음 |
| 조건부 통과 | 보통·낮음 실패만 있음 |
| 통과 | 계획한 항목이 모두 기준과 일치 |

미검증 규칙은 판정에 넣지 않고 규칙 추적표에 따로 보인다. "통과"는 **계획한 범위 안에서** 통과라는 뜻이다.
