// 실행 결과를 사람이 읽는 보고서(HTML 한 장 + 요약 MD)로 만든다.
import { SEVERITIES } from './runner.mjs';

const esc = value => String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const json = value => (typeof value === 'string' ? value : JSON.stringify(value, null, 2));
const STATUS_LABEL = { PASS: '통과', FAIL: '실패', ERROR: '실행 오류', '확인 필요': '확인 필요' };
const KIND_LABEL = { call: '시나리오', same: '시나리오(입력 비교)' };
const sevRank = s => { const i = SEVERITIES.indexOf(s); return i < 0 ? 9 : i; };

function issues(result) {
  const all = [
    ...result.cases.map(c => ({ ...c, group: KIND_LABEL[c.type] ?? '시나리오' })),
    ...result.dataChecks.map(d => ({ ...d, group: d.kind ?? '데이터' })),
    ...result.findings.map(f => ({ ...f, group: f.kind ?? '정적 점검' })),
  ];
  const order = (a, b) => sevRank(a.severity) - sevRank(b.severity) || String(a.id).localeCompare(String(b.id));
  return {
    open: all.filter(i => i.status === 'FAIL' || i.status === 'ERROR').sort(order),
    ask: all.filter(i => i.status === '확인 필요').sort(order),
    passed: all.filter(i => i.status === 'PASS'),
  };
}

function ruleTexts(result, ids) {
  const byId = new Map(result.trace.map(t => [t.id, t]));
  return ids.map(id => {
    const rule = byId.get(id);
    return `<li><b>${esc(id)}</b>${rule ? ` <span class="muted">(${esc(rule.sheet)})</span> ${esc(rule.text)}` : ''}</li>`;
  }).join('');
}

function issueCard(item, result) {
  const block = (label, value) => (value === undefined || value === null || value === '' ? '' :
    `<div class="io"><div class="io-label">${label}</div><pre>${esc(json(value))}</pre></div>`);
  const diffs = item.diffs?.length ? `<div class="diffs">${item.diffs.map(d => `<div>· <code>${esc(d.path)}</code> 기대 <code>${esc(JSON.stringify(d.expected))}</code> → 실제 <code>${esc(JSON.stringify(d.actual))}</code></div>`).join('')}</div>` : '';
  const samples = item.samples?.length ? `<div class="io"><div class="io-label">예시 행</div><pre>${esc(item.samples.join('\n'))}</pre></div>` : '';
  return `<article class="card sev-${sevRank(item.severity)}">
  <header><span class="id">${esc(item.id)}</span><span class="pill sev">${esc(item.severity)}</span><span class="pill">${esc(item.group)}</span><span class="pill st-${esc(item.status)}">${esc(STATUS_LABEL[item.status] ?? item.status)}</span></header>
  <h3>${esc(item.title)}</h3>
  ${item.scenario ? `<p class="scene">${esc(item.scenario)}</p>` : ''}
  ${item.rules?.length ? `<details class="rules" open><summary>근거 규칙</summary><ul>${ruleTexts(result, item.rules)}</ul></details>` : ''}
  ${item.basis ? `<p><b>기준</b> ${esc(item.basis)}</p>` : ''}
  ${item.evidence ? `<p><b>증거</b> ${esc(item.evidence)}</p>` : ''}
  <div class="grid3">${block('입력', item.input)}${block('기대', item.expected)}${block('실제', item.actual)}</div>
  ${diffs}${samples}
  ${item.where ? `<p><b>위치</b> <code>${esc(item.where)}</code></p>` : ''}
  ${item.suggestion ? `<p><b>제안</b> ${esc(item.suggestion)}</p>` : ''}
  ${item.note ? `<p class="muted"><b>메모</b> ${esc(item.note)}</p>` : ''}
</article>`;
}

export function renderHtml(result) {
  const { open, ask, passed } = issues(result);
  const s = result.summary;
  const t = result.tests;
  const level = { 통과: 'ok', '조건부 통과': 'warn', 보류: 'bad' }[result.verdict.level] ?? 'warn';
  const uncovered = result.trace.filter(r => !r.items.length);
  const traceRows = result.trace.map(r => `<tr class="${r.items.length ? '' : 'gap'}"><td><b>${esc(r.id)}</b></td><td>${esc(r.text)}</td><td>${r.items.length ? r.items.map(i => `<span class="pill st-${esc(i.status)}">${esc(i.id)} ${esc(STATUS_LABEL[i.status] ?? i.status)}</span>`).join(' ') : '<span class="muted">미검증</span>'}</td></tr>`).join('');
  const passRows = passed.map(p => `<tr><td>${esc(p.id)}</td><td>${esc(p.group)}</td><td>${esc(p.title)}</td><td>${esc((p.rules ?? []).join(', '))}</td></tr>`).join('');
  const list = items => (items?.length ? `<ul>${items.map(i => `<li>${esc(i)}</li>`).join('')}</ul>` : '<p class="muted">없음</p>');
  return `<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(result.feature)} QA 보고서</title>
<style>
:root{--bg:#fbfbfa;--panel:#fff;--ink:#1d1d1b;--muted:#6b6b66;--line:#e4e3de;--ok:#1f7a4d;--ok-bg:#e6f4ec;--warn:#9a6200;--warn-bg:#fdf2dc;--bad:#b42318;--bad-bg:#fdeceb;--code:#f3f2ee}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--panel:#1f1f1d;--ink:#ecebe6;--muted:#a3a29b;--line:#34332f;--ok:#5cc58f;--ok-bg:#183326;--warn:#e7b356;--warn-bg:#3a2d12;--bad:#f2867c;--bad-bg:#3d1b18;--code:#2a2a27}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 system-ui,-apple-system,"Segoe UI","Malgun Gothic",sans-serif}
main{max-width:1080px;margin:0 auto;padding:32px 16px 64px}h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:40px 0 12px;padding-top:8px;border-top:1px solid var(--line)}h3{font-size:16px;margin:6px 0}
.muted{color:var(--muted)}code,pre{font-family:ui-monospace,Consolas,monospace;font-size:12.5px}code{background:var(--code);padding:1px 5px;border-radius:4px}
pre{background:var(--code);padding:10px;border-radius:8px;margin:4px 0 0;max-height:260px;overflow:auto;white-space:pre-wrap;word-break:break-all}
.verdict{margin:20px 0;padding:16px 18px;border-radius:12px;border:1px solid var(--line);background:var(--panel)}.verdict b{font-size:20px}
.verdict.ok{background:var(--ok-bg);color:var(--ok)}.verdict.warn{background:var(--warn-bg);color:var(--warn)}.verdict.bad{background:var(--bad-bg);color:var(--bad)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}.stat .n{font-size:22px;font-weight:700}.stat .l{color:var(--muted);font-size:13px}
.card{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0}.card.sev-0{border-left-color:var(--bad)}.card.sev-1{border-left-color:var(--warn)}
.card header{display:flex;gap:6px;flex-wrap:wrap;align-items:center}.id{font-weight:700;margin-right:4px}
.pill{display:inline-block;font-size:12px;padding:1px 8px;border-radius:999px;border:1px solid var(--line);color:var(--muted);white-space:nowrap}
.st-PASS{color:var(--ok);border-color:var(--ok)}.st-FAIL{color:var(--bad);border-color:var(--bad)}.st-ERROR{color:var(--warn);border-color:var(--warn)}
.scene{background:var(--code);border-radius:8px;padding:8px 12px;margin:8px 0}
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px;margin-top:8px}.io-label{font-size:12px;color:var(--muted)}.diffs{margin-top:8px;font-size:13.5px}
.rules ul{margin:4px 0;padding-left:18px;font-size:13.5px}.rules summary{cursor:pointer;color:var(--muted);font-size:13px}
table{width:100%;border-collapse:collapse;background:var(--panel);font-size:13.5px}th,td{border-bottom:1px solid var(--line);padding:7px 8px;text-align:left;vertical-align:top}th{color:var(--muted);font-weight:600}
tr.gap td{color:var(--muted)}.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px}
details>summary{cursor:pointer}
</style></head><body><main>
<p class="muted">QA 보고서 · ${esc(result.date)}</p>
<h1>${esc(result.feature)}</h1>
<p class="muted">대상 <code>${esc(result.target)}</code>${result.baseline.contract ? ` · 기준 <code>${esc(result.baseline.contract.file)}</code>${result.baseline.contract.status ? ` (${esc(result.baseline.contract.status)})` : ''}` : ''}</p>
<div class="verdict ${level}"><b>${esc(result.verdict.level)}</b> — ${esc(result.verdict.reason)}</div>
<div class="stats">
  <div class="stat"><div class="n">${t.ran ? `${t.pass} / ${t.tests}` : '—'}</div><div class="l">기존 테스트 통과${t.fail ? ` · 실패 ${t.fail}` : ''}</div></div>
  <div class="stat"><div class="n">${s.cases.PASS} / ${s.cases.total}</div><div class="l">시나리오 케이스 통과${s.cases.FAIL ? ` · 실패 ${s.cases.FAIL}` : ''}${s.cases.ERROR ? ` · 오류 ${s.cases.ERROR}` : ''}</div></div>
  <div class="stat"><div class="n">${s.dataChecks.PASS} / ${s.dataChecks.total}</div><div class="l">데이터·문서 점검 통과</div></div>
  <div class="stat"><div class="n">${s.findings.FAIL}</div><div class="l">코드 읽기로 찾은 불일치</div></div>
  <div class="stat"><div class="n">${s.rules.covered} / ${s.rules.total}</div><div class="l">규칙 중 검증 항목이 연결된 것</div></div>
</div>

<h2>고쳐야 할 것 (${open.length})</h2>
${open.length ? open.map(i => issueCard(i, result)).join('') : '<p class="muted">없음</p>'}

${ask.length || result.openQuestions.length ? `<h2>정책 확인이 필요한 것</h2>${ask.map(i => issueCard(i, result)).join('')}${list(result.openQuestions)}` : ''}

<h2>통과한 것 (${passed.length})</h2>
<details><summary>목록 펼치기</summary><div class="table-wrap"><table><thead><tr><th>ID</th><th>종류</th><th>확인한 것</th><th>규칙</th></tr></thead><tbody>${passRows}</tbody></table></div></details>
${t.failures?.length ? `<h3>기존 테스트 실패</h3>${list(t.failures)}` : ''}

<h2>규칙 추적표</h2>
<p>기준 문서의 규칙마다 어떤 검증 항목이 연결됐는지 보여 줍니다. <b>미검증</b>은 실패가 아니라 <b>이번에 확인하지 않았다</b>는 뜻입니다. 남은 미검증 ${uncovered.length}개는 다음 회차 후보입니다.</p>
${result.unknownRuleRefs.length ? `<p class="muted">기준 문서에 없는 규칙 번호를 참조한 항목: ${esc(result.unknownRuleRefs.join(', '))}</p>` : ''}
<details><summary>${result.trace.length}개 규칙 펼치기</summary><div class="table-wrap"><table><thead><tr><th>규칙</th><th>내용</th><th>연결된 검증</th></tr></thead><tbody>${traceRows}</tbody></table></div></details>

<h2>범위</h2>
<h3>이번에 확인한 것</h3>${list(result.scope.in)}
<h3>이번에 확인하지 않은 것</h3>${list(result.scope.out)}

<h2>다시 돌리는 법</h2>
<pre>node qa-agent/bin/qa.mjs run ${esc(result.plan)}</pre>
${t.command ? `<p class="muted">기존 테스트만: <code>${esc(t.command)}</code></p>` : ''}
<p class="muted">Node ${esc(result.environment.node)} · 계약 파일 지문 ${esc(result.baseline.contract?.sha256 ?? '—')} (같은 지문이면 같은 계약으로 돌린 결과)</p>
</main></body></html>
`;
}

export function renderMarkdown(result) {
  const { open, ask } = issues(result);
  const s = result.summary;
  const t = result.tests;
  const lines = [
    `# ${result.feature} QA 요약 — ${result.date}`,
    '',
    `**판정: ${result.verdict.level}** — ${result.verdict.reason}`,
    '',
    '| 항목 | 결과 |', '|---|---|',
    `| 기존 테스트 | ${t.ran ? `${t.pass}/${t.tests} 통과` : '없음'} |`,
    `| 시나리오 케이스 | ${s.cases.PASS}/${s.cases.total} 통과 |`,
    `| 데이터·문서 점검 | ${s.dataChecks.PASS}/${s.dataChecks.total} 통과 |`,
    `| 코드 읽기 불일치 | ${s.findings.FAIL}건 |`,
    `| 규칙 연결 | ${s.rules.covered}/${s.rules.total} |`,
    '',
    `## 고쳐야 할 것 (${open.length})`,
    ...open.map(i => `- **${i.id}** [${i.severity}·${STATUS_LABEL[i.status]}] ${i.title}${i.rules?.length ? ` — ${i.rules.join(', ')}` : ''}`),
    ...(ask.length ? ['', '## 정책 확인 필요', ...ask.map(i => `- **${i.id}** ${i.title}`)] : []),
    '',
    `재실행: \`node qa-agent/bin/qa.mjs run ${result.plan}\``,
    '',
  ];
  return lines.join('\n');
}
