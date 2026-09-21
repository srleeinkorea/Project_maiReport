/* ════════════════════════════════════════════════════════════
   AI 건강 인사이트 — 다시 분석(재분석) 프로세스 보완 패치
   붙여넣은 프로토타입의 AI 인사이트 블록에서 아래 이름의 함수·변수를
   그대로 교체하면 됩니다. (교체 대상: aiCreateReport, aiSummaryHtml,
   renderAiInsightEntry의 재분석 분기, generateAiInsight, 확인 시트 핸들러)
   ════════════════════════════════════════════════════════════ */

/* ── 1. 재분석 상태를 '주' 단위로 보관 ──
   기존에는 리포트 객체의 redoneOn에만 기록해서, 리포트를 삭제하고 다시 만들면
   하루 1회 제한이 풀렸다. 주 시작일을 키로 따로 보관해 삭제와 무관하게 유지한다. */
const AI_REDO = {};                                  /* monday → { on:'YYYY-MM-DD', count:n } */
function aiRedoState(mStr){ return AI_REDO[mStr] || { on:null, count:0 }; }
function aiCanRedo(mStr){ return aiRedoState(mStr).on !== aiYmd(AI_TODAY); }
function aiMarkRedone(mStr){
  const s = aiRedoState(mStr);
  AI_REDO[mStr] = { on: aiYmd(AI_TODAY), count: s.count + 1 };
}

/* ── 2. 리포트 생성: 회차·분석 시각을 남기고, 다시 분석하면 결과가 실제로 갱신되게 ──
   재분석은 '오늘까지의 기록'을 다시 반영하는 것이므로 기간 끝과 점수가 함께 움직여야
   사용자가 갱신을 확인할 수 있다. */
function aiCreateReport(monday, revision){
  const mStr = aiYmd(monday);
  const { start, end } = aiPeriod(monday);
  const withCheckup = !!imp.checkup;                 /* 생성 시점 데이터로 고정 */
  const src = withCheckup ? AI_MOCK.withCheckup : AI_MOCK.lifeOnly;
  const rev = revision || 1;
  const base = AI_WEEK_SCORES[mStr] ?? 74;
  /* 프로토타입용: 회차가 올라갈수록 오늘 기록이 더해진 만큼 점수가 조금 움직인다 */
  const score = Math.max(0, Math.min(100, base + (rev - 1) * 3));
  const now = new Date();
  const r = {
    id: ++aiSeq, monday: mStr, week: aiWeekLabelOf(monday),
    range: `${aiDot(start)} ~ ${aiDot(end)}`,
    score, withCheckup, revision: rev,
    analyzedAt: `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`,
    headline: src.headline, summary: src.summary, findings: src.findings
  };
  AI_REPORTS.push(r); AI_REPORTS.sort((a,b)=>a.monday.localeCompare(b.monday));
  return r;
}

/* ── 3. 요약 화면: 분석 기준·갱신 시각을 드러내고, 재분석 가능 여부를 주 단위로 판단 ── */
function aiSummaryHtml(r){
  const isThisWeek = r.monday === aiYmd(aiMondayFor(0));
  const meta = r.revision > 1
    ? `분석 기준 ${r.range} · 오늘 ${r.analyzedAt} 다시 분석 (${r.revision}회차)`
    : `분석 기준 ${r.range}`;
  /* 이전 분석에 없던 검진정보가 연동된 경우 안내 */
  const newlyCheckup = isThisWeek && imp.checkup && !r.withCheckup;
  const redoBlock = !isThisWeek ? '' : (
    aiCanRedo(r.monday)
      ? `<button class="ai-btn2" id="aiRedo">다시 분석하기</button>
         ${newlyCheckup ? `<p class="ai-redo-note">검진정보가 연동됐어요. 다시 분석하면 이번 리포트에 반영돼요</p>` : ''}`
      : `<button class="ai-btn2" disabled>다시 분석하기</button>
         <p class="ai-redo-note">오늘 다시 분석했어요. 내일 다시 분석할 수 있어요</p>`
  );
  return `
    <div class="ai-in-sec"><h3>${r.week} 인사이트</h3></div>
    <p class="ai-redo-note" style="margin:-6px 0 2px;text-align:left">${meta}</p>
    <section class="ai-hero">
      <p class="hl">${r.headline}</p>
      <div class="ai-sc"><small>종합 점수</small>
        <div class="ai-sc-row"><b>${r.score}<span>/ 100</span></b>${aiDeltaHtml(r, true)}</div>
        <div class="ai-bar"><i style="width:${r.score}%"></i></div></div>
    </section>
    <section class="ai-card"><h4>종합 소견</h4><p class="ai-txt">${r.summary}</p></section>
    <section class="ai-card"><h4>핵심 인사이트</h4>
      ${r.findings.map(f=>`<div class="ai-ki"><span class="ai-cic ${f.cat}">${AI_ICON[f.cat]}</span><div><em class="ai-clab ${f.cat}">${AI_CAT[f.cat]}</em><b>${f.title}</b></div></div>`).join('')}
    </section>
    <p class="ai-disclaimer-v2">AI 건강 인사이트는 검진·헬스 데이터를 바탕으로 한 생활습관 참고 정보이며, 의학적 진단이나 의료진의 판단을 대신하지 않습니다.</p>
    <button class="ai-btn" id="aiMore">자세히 보기</button>
    ${redoBlock}`;
}

/* ── 4. 분석 중 화면: 최초 분석과 재분석을 구분 ──
   renderAiInsightEntry 안의 aiGenerating 분기를 아래로 교체한다. */
function aiGeneratingHtml(mStr){
  const redo = !!aiRedoPending;                      /* 재분석으로 시작한 경우 */
  return redo
    ? `<section class="ai-box loading"><div class="spin"></div>
         <h3>다시 분석하고 있어요</h3>
         <p>오늘까지의 기록으로 새로 계산하는 중이에요<br>완료되면 지금 인사이트가 새 결과로 바뀌어요</p></section>`
    : `<section class="ai-box loading"><div class="spin"></div>
         <h3>AI가 건강 데이터를 분석하고 있어요</h3>
         <p>생활 데이터${imp.checkup ? ' · 검진정보' : ''}를 종합하는 중이에요</p></section>`;
}

/* ── 5. 생성/교체 순서 정리 ──
   기존 코드는 replace 리포트를 먼저 지우고 새로 만들었다. 중간에 실패하면 둘 다 잃는다.
   새 리포트를 만든 뒤 교체하고, 상세 화면이 열려 있으면 새 리포트로 갱신한다. */
let aiRedoPending = null;
function generateAiInsight(monday, replace){
  const m = monday || aiMondayFor(0);
  const mStr = aiYmd(m);
  if(replace && !aiCanRedo(mStr)) return;            /* 하루 1회 */
  aiRedoPending = replace || null;
  aiGenerating = mStr;
  renderAiInsightEntry();
  setTimeout(()=>{
    const rev = replace ? (replace.revision || 1) + 1 : 1;
    const created = aiCreateReport(m, rev);          /* 먼저 만들고 */
    if(replace){                                     /* 성공한 뒤에 교체 */
      AI_REPORTS = AI_REPORTS.filter(x => x.id !== replace.id);
      aiMarkRedone(mStr);
    }
    aiGenerating = null; aiRedoPending = null;
    renderAiInsightEntry();
    /* 상세 화면이 열린 채 재분석했다면 사라진 리포트를 보고 있지 않도록 새 것으로 교체 */
    const det = document.getElementById('aiInsightDet');
    if(replace && det && det.classList.contains('open')){ openAiInsight(created.id, aiCurTab || 'detail'); }
  }, 1600);
}

/* ── 6. 확인 시트 문구 ──
   검진정보가 새로 연동된 경우를 문구에 반영한다. 기존 정적 텍스트 대신 열 때 채운다. */
function openAiRedoConfirm(r){
  aiRedoTarget = r;
  const newlyCheckup = imp.checkup && !r.withCheckup;
  document.querySelector('#aiRedoConfirm .update-desc').innerHTML = newlyCheckup
    ? '검진정보가 연동돼 이번 분석부터 혈압·혈당 등 검진 결과가 함께 반영돼요. 지금 인사이트는 새 결과로 바뀌고, 다시 분석은 하루에 한 번 할 수 있어요.'
    : '오늘까지의 기록으로 새로 분석해요. 지금 인사이트는 새 결과로 바뀌고, 다시 분석은 하루에 한 번 할 수 있어요.';
  document.getElementById('aiRedoConfirm').classList.add('open');
}
/* renderAiInsightEntry의 바인딩을 다음으로 교체:
     if(redo) redo.onclick = ()=>openAiRedoConfirm(rep);                                   */

/* ── 7. 삭제 확인 문구 ──
   "이 주는 다시 분석할 수 있어요"는 하루 1회 제한과 어긋난다. 삭제해도 오늘 이미
   재분석했다면 오늘은 다시 만들 수 없다는 사실을 그대로 말한다. */
function openAiDeleteConfirm(r){
  const can = aiCanRedo(r.monday);
  document.querySelector('#aiDeleteConfirm .update-desc').textContent = can
    ? '삭제한 인사이트는 되돌릴 수 없어요. 이 주는 오늘 다시 분석할 수 있어요.'
    : '삭제한 인사이트는 되돌릴 수 없어요. 오늘은 이미 다시 분석해서, 이 주는 내일부터 다시 만들 수 있어요.';
  document.getElementById('aiDeleteConfirm').classList.add('open');
}
