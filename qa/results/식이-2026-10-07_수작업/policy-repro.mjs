import fs from 'node:fs';
import {recalculateAxisStage, selectDietGoal} from '../../mai-report-policy/식이/diet-goal-engine-v1.0.0.mjs';
const goals = ['2026-10-04','2026-10-05','2026-10-06'].map(session_date => ({session_date, goal_state:'CREATED', completed:true}));
const cases = [];
for (const [id,currentStage,axisState,expected] of [
  ['QA-DIET-01','INTRO','OBSERVING','INTRO'],
  ['QA-DIET-02','BASE','NEEDS_WORK','BASE'],
]) {
  const actual = recalculateAxisStage({currentStage,axisState,goals,asOfDate:'2026-10-07'});
  cases.push({id,input:{currentStage,axisState,goals,asOfDate:'2026-10-07'},expected,actual,result:actual.stage===expected?'PASS':'FAIL'});
}
const rows = ['DIET-Q-01','DIET-Q-03'].map((question_id,index)=>({phrase_id:`P${index}`,phrase_version:'1.0.0',question_id,stage_code:'INTRO',source_status:'사용',parse_status:'READY',time_code:'ANY',calendar_code:'ANY'}));
const common={rows,instant:'2026-10-07T13:00:00+09:00',timeZone:'Asia/Seoul',conditionInput:{manual:{state:'UNANSWERED',codes:[]},diseaseRules:[],axisRows:[],banNatureRows:[]}};
const snapshots=[{question_id:'DIET-Q-01',state_code:'GOOD',valid_answer_count:1},{question_id:'DIET-Q-03',state_code:'NEEDS_WORK',valid_answer_count:4}];
const native=selectDietGoal({...common,axisSnapshots:snapshots});
const adapted=selectDietGoal({...common,axisSnapshots:snapshots.map(s=>({...s,status_code:s.state_code==='NEEDS_WORK'?'IMPROVEMENT_NEEDED':s.state_code}))});
cases.push({id:'QA-DIET-03',description:'계약 state_code와 구현 status_code의 입력 차이',input:snapshots,contractInputResult:native.question_id,adaptedInputResult:adapted.question_id,result:native.question_id===adapted.question_id?'PASS':'FAIL',note:'선정 순위의 정책은 별도 확인 필요. 입력 필드 변환 유무에 따라 결과가 바뀌는 사실을 확인했다.'});
fs.writeFileSync(new URL('./policy-repro-results.json',import.meta.url),JSON.stringify(cases,null,2));
console.log(JSON.stringify(cases,null,2));
