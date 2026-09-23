const fs = require('fs');
const path = require('path');
const source = path.join(__dirname, 'maiReport_RSNA시연_급성폐렴_프로토타입_v1.0.0.html');
let html = fs.readFileSync(source, 'utf8');
html = html.replace(/if\(care && care\.v==='unsure'\) return \{act:'[^']*',\s*why:'[^']*'\};/, "if(care && care.v==='unsure') return {act:'오늘은 몸 상태에 맞춰 활동과 휴식을 조절해 보세요.',\n    why:'평소 하던 일도 오늘은 부담스럽게 느껴질 수 있어요. 피로가 느껴지면 하던 일을 나누어 하고, 중간에 쉬는 시간을 가져보세요.'};");
html = html.replace('<title>마이리포트 · 급성 폐렴 케이스 시연</title>', '<title>마이리포트 · 정보 중심 홈 구성안</title>');
html = html.replace('const DEMO_AI_REPORT_REGISTERED = false;', 'const DEMO_AI_REPORT_REGISTERED = true;');
html = html.replace('let imp = {checkup:false, clinic:false};', 'let imp = {checkup:true, clinic:false};');
html = html.replace('imp.checkup = false; imp.clinic = false; importing = null;', 'imp.checkup = true; imp.clinic = false; importing = null;');
const css = `
/* Existing prototype styles remain authoritative. Only new home content is styled. */
.home-overview .home-age-card{background:#fff;border-radius:var(--r);padding:16px 18px;box-shadow:var(--sh);display:flex;align-items:center;gap:12px}
.home-overview .home-info-row{display:flex;align-items:center;justify-content:space-between;gap:10px}
.home-overview .home-info-row b{font-size:var(--t-h2);font-weight:700}
.home-overview .home-info-tag{font-size:var(--t-mini);color:var(--ink-2);background:var(--fill);border-radius:6px;padding:3px 7px}
.home-overview .home-age-number{font-size:26px;line-height:1.3;font-weight:700;color:var(--ink-1);margin:0;letter-spacing:-.04em;white-space:nowrap}
.home-overview .home-age-number span{font-size:var(--t-h2);margin-left:4px}
.home-overview .home-age-diff{font-size:var(--t-mini);color:var(--ink-2);margin-top:3px}
.home-overview .home-age-diff b{margin-left:7px;color:var(--warn)}
.home-overview .home-age-copy{flex:1;min-width:0}.home-overview .home-age-copy>b{font-size:var(--t-sm);font-weight:600}.home-overview .home-age-meta{font-size:var(--t-mini);color:var(--ink-3);margin-top:3px}.home-overview .home-age-chevron{border:0;background:transparent;padding:8px;color:var(--ink-3);font-size:22px;cursor:pointer}
.home-overview .home-info-link{background:none;border:none;color:var(--brand);font-size:var(--t-cap);font-weight:600;padding:5px 0;cursor:pointer}
#home .home-question-section{padding:18px;margin-bottom:14px}
#pRead .reading-cover{display:block;width:calc(100% + 40px);max-width:none;aspect-ratio:3/2;object-fit:cover;margin:-20px -20px 20px;border-radius:var(--r) var(--r) 0 0}
#pRead>.card:first-child{overflow:hidden}
.home-preview-note{font-size:var(--t-mini);color:var(--ink-3);text-align:center;padding:4px 18px 16px}
.home-health-caption,.home-insight-desc,.home-peer-caption,.home-peer-note{display:none!important}.home-health-group>.h-sec{margin-bottom:12px!important}.home-insight-card{position:relative}.home-insight-title{font-size:36px!important;line-height:1.2!important;color:var(--brand);font-weight:700!important}.home-insight-title small{font-size:var(--t-cap);color:var(--ink-3);font-weight:500;margin-left:5px}.home-insight-top{margin-bottom:9px!important}.home-insight-footer{padding-top:9px!important;margin-top:11px!important}.home-peer-grid{margin-bottom:2px!important}.home-peer-item svg{display:block;width:20px;height:20px;margin:0 auto 7px;color:var(--ink-2)}.home-peer-item strong{font-size:24px!important}.home-peer-help{font-size:var(--t-mini);color:var(--ink-2);margin-top:12px}.home-peer-help summary{cursor:pointer}.home-peer-help p{margin-top:7px;line-height:1.6;color:var(--ink-3)}
.home-health-group>.h-sec{margin-bottom:4px}.home-health-caption{font-size:var(--t-cap);color:var(--ink-2);margin:0 2px 13px}.home-health-group>.home-insight,.home-health-group>.home-overview{padding:0;margin:0}.home-health-group>.home-overview{margin-top:10px}.home-health-group .home-age-card{box-shadow:var(--sh)}
.home-overview .home-age-card{flex-wrap:wrap;padding:20px 18px}.home-overview .home-age-number{font-size:36px;color:var(--brand)}.home-peer{flex:0 0 100%;border-top:1px solid var(--line);padding-top:17px;margin-top:4px}.home-peer-heading{display:flex;justify-content:space-between;align-items:center;gap:8px}.home-peer-heading b{font-size:var(--t-sm);font-weight:600}.home-peer-heading small{font-size:var(--t-mini);color:var(--ink-3)}.home-peer-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin:16px 0 12px}.home-peer-item{text-align:center;padding:0 3px}.home-peer-item+.home-peer-item{border-left:1px solid var(--line)}.home-peer-item>span{display:block;font-size:var(--t-cap);color:var(--ink-2)}.home-peer-item strong{display:block;font-size:25px;font-weight:700;letter-spacing:-.04em;line-height:1.4;margin:5px 0 2px;color:var(--ink-1)}.home-peer-item strong small{font-size:var(--t-mini);font-weight:500;margin-left:2px}.home-peer-item em{font-size:10px;font-style:normal;color:var(--ink-3)}.home-peer-note{font-size:var(--t-mini);color:var(--ink-3);line-height:1.6}.home-peer-caption{font-size:var(--t-mini);color:var(--ink-2);margin-top:5px}
.home-insight-card{display:block;width:100%;text-align:left;background:#fff;border:1px solid #E3EAF8;border-radius:var(--r);padding:18px;box-shadow:var(--sh);font-family:inherit;cursor:pointer;color:var(--ink-1)}
.home-insight-top{display:flex;align-items:center;gap:9px;margin-bottom:13px}.home-insight-icon{display:flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:9px;background:var(--brand-soft);color:var(--brand);flex-shrink:0}.home-insight-icon svg{width:18px;height:18px}.home-insight-label{font-size:var(--t-sm);font-weight:700}.home-insight-badge{margin-left:auto;color:var(--ink-2);background:var(--fill);padding:3px 7px;border-radius:6px;font-size:var(--t-mini);font-weight:500}.home-insight-title{display:block;font-size:var(--t-h2);line-height:1.55;letter-spacing:-.02em;font-weight:700}.home-insight-desc{display:block;color:var(--ink-2);font-size:var(--t-cap);line-height:1.65;margin-top:6px}.home-insight-footer{display:flex;align-items:center;justify-content:space-between;gap:8px;padding-top:13px;margin-top:14px;border-top:1px solid var(--line);font-size:var(--t-mini);color:var(--ink-3)}.home-insight-action{font-size:var(--t-cap);font-weight:600;color:var(--brand);white-space:nowrap}.home-insight-card:focus-visible{outline:2px solid var(--brand);outline-offset:3px}
`;

const polishedCss = `
/* Compact numeric hierarchy; inherits the original prototype's tokens. */
.home-health-group{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:0 10px}
.home-health-group>.h-sec{grid-column:1/-1;margin-bottom:14px!important;padding:0 2px}
.home-health-group>.home-health-caption{display:none}
.home-health-group>.home-insight{grid-column:1;grid-row:2;min-width:0}
.home-health-group>.home-overview{display:contents}
.home-health-group .home-age-card{display:contents}
.home-health-group .home-age-summary{grid-column:2;grid-row:2;min-width:0;background:#fff;border-radius:var(--r);box-shadow:var(--sh);padding:17px 16px;display:flex;flex-direction:column;position:relative}
.home-health-group .home-insight-card{height:auto;min-height:180px;border:0;padding:17px 16px;display:flex;flex-direction:column;box-shadow:var(--sh)}
.home-health-group .home-insight-top{gap:7px;margin:0!important;min-height:28px}
.home-health-group .home-insight-label{font-size:12px;font-weight:600;white-space:nowrap;letter-spacing:-.03em}
.home-health-group .home-insight-icon,.home-health-group .home-age-symbol{width:26px;height:26px;border-radius:8px;background:var(--brand-soft);color:var(--brand);display:flex;align-items:center;justify-content:center;flex-shrink:0}
.home-health-group .home-insight-icon svg,.home-health-group .home-age-symbol svg{width:16px;height:16px}
.home-health-group .home-insight-badge{display:none}
.home-health-group .home-insight-title,.home-health-group .home-age-number{font-size:38px!important;font-weight:700!important;line-height:1.15!important;letter-spacing:-.05em;margin:18px 0 9px!important;color:var(--brand);white-space:nowrap}
.home-health-group .home-insight-title small,.home-health-group .home-age-number span{font-size:12px!important;font-weight:500;color:var(--ink-2);letter-spacing:0;margin-left:4px}
.home-health-group .home-insight-footer{margin:auto 0 0!important;padding:0!important;border:0;display:flex;align-items:flex-start;flex-direction:column;gap:5px;font-size:10px;line-height:1.5}
.home-health-group .home-insight-action{font-size:11px;font-weight:600;align-self:flex-end}
.home-health-group .home-age-copy{display:contents}
.home-health-group .home-age-label{display:flex;align-items:center;gap:7px;min-height:28px;font-size:12px;font-weight:600}
.home-health-group .home-age-diff{font-size:11px;margin:0 0 3px;order:3}
.home-health-group .home-age-meta{font-size:10px;line-height:1.5;order:4;margin:0;padding-right:15px;color:var(--ink-3)}
.home-health-group .home-age-chevron{position:absolute;right:10px;bottom:9px;min-width:30px;min-height:30px;font-size:19px}
.home-health-group .home-peer{grid-column:1/-1;grid-row:3;width:100%;background:#fff;border:0;border-radius:var(--r);box-shadow:var(--sh);padding:17px 16px 14px;margin-top:10px}
.home-health-group .home-peer-heading b{font-size:13px;font-weight:600}.home-health-group .home-peer-heading small{font-size:10px}
.home-health-group .home-peer-grid{margin:18px 0 0!important;gap:0}
.home-health-group .home-peer-item{padding:0 4px}.home-health-group .home-peer-item+.home-peer-item{border-left:1px solid var(--line)}
.home-health-group .home-peer-item svg{width:20px;height:20px;margin-bottom:8px;color:var(--ink-2)}
.home-health-group .home-peer-item>span{font-size:11px}.home-health-group .home-peer-item strong{font-size:25px!important;margin:4px 0 2px;font-weight:700;letter-spacing:-.04em}.home-health-group .home-peer-item em{font-size:10px}
.home-health-group .home-peer-help{margin-top:15px;padding-top:10px;border-top:1px solid var(--line);font-size:10px;color:var(--ink-3)}
.home-health-group button:focus-visible{outline:2px solid var(--brand);outline-offset:3px}
@media(max-width:360px){.home-health-group{column-gap:8px}.home-health-group .home-insight-card,.home-health-group .home-age-summary{padding:15px 12px}.home-health-group .home-insight-label,.home-health-group .home-age-label{font-size:11px}.home-health-group .home-insight-title,.home-health-group .home-age-number{font-size:34px!important}.home-health-group .home-insight-icon,.home-health-group .home-age-symbol{width:22px;height:22px}}
`;
const friendlyCss = `
.home-health-group .home-insight-title,.home-health-group .home-age-number{color:var(--ink-1)}
.home-health-group .home-insight-icon,.home-health-group .home-age-symbol{background:transparent;width:28px;height:28px;border-radius:0;font-size:23px;line-height:1}
.home-peer-emoji{display:flex!important;align-items:center;justify-content:center;width:34px;height:34px;margin:0 auto 7px;border-radius:12px;background:var(--fill);font-size:23px!important;line-height:1}
.home-peer-item:nth-child(1) .home-peer-emoji{background:#EEF3FF}.home-peer-item:nth-child(2) .home-peer-emoji{background:#EEF7F1}.home-peer-item:nth-child(3) .home-peer-emoji{background:#F3EFFB}.home-peer-item:nth-child(4) .home-peer-emoji{background:#FFF3E7}
.home-health-group .home-insight-card.is-empty .home-insight-title{font-size:17px!important;letter-spacing:-.03em;line-height:1.5!important;margin:17px 0 4px!important;color:var(--ink-1)}
.home-health-group .home-insight-card.is-empty .home-insight-desc{display:block!important;font-size:11px;line-height:1.6;margin:0;color:var(--ink-2)}
.home-health-group .home-insight-card.is-empty .home-insight-footer{margin-top:13px!important;width:100%;padding:0!important}
.home-health-group .home-insight-card.is-empty #gptInsightPeriod{display:none}
.home-health-group .home-insight-card.is-empty .home-insight-action{align-self:stretch;text-align:center;background:var(--fill);color:var(--ink-1);border:1px solid var(--line);border-radius:9px;padding:7px 10px;font-size:12px;font-weight:600}
.home-health-group .home-insight-action{color:var(--ink-2)}
`;
const groupedCheckupCss = `
.home-health-group{display:block}.home-health-group>.home-overview{display:block;margin-top:10px}.home-health-group .home-age-card{display:block;background:#fff;border-radius:var(--r);padding:0 18px;box-shadow:var(--sh)}
.home-health-group .home-age-summary{background:none;box-shadow:none;border-radius:0;min-height:0;padding:18px 0;display:grid;grid-template-columns:1fr auto;gap:4px 12px;align-items:center}
.home-health-group .home-age-label{grid-column:1;grid-row:1}.home-health-group .home-age-number{grid-column:2;grid-row:1/4;margin:0 25px 0 0!important}.home-health-group .home-age-diff{grid-column:1;grid-row:2;margin:0}.home-health-group .home-age-meta{grid-column:1;grid-row:3}.home-health-group .home-age-chevron{right:-8px;top:50%;bottom:auto;transform:translateY(-50%)}
.home-health-group .home-peer{background:none;box-shadow:none;border-radius:0;padding:16px 0;margin:0;border-top:1px solid var(--line)}
.home-health-group .home-insight-card{min-height:0;padding:18px;display:grid;grid-template-columns:1fr auto;gap:8px 12px}.home-health-group .home-insight-top{grid-column:1;grid-row:1}.home-health-group .home-insight-title{grid-column:2;grid-row:1/3;margin:0!important;align-self:center}.home-health-group .home-insight-footer{grid-column:1;grid-row:2;display:flex;flex-direction:row;align-items:center;gap:12px}.home-health-group .home-insight-action{align-self:auto}
.home-health-group .home-insight-card.is-empty .home-insight-title{grid-column:1;grid-row:2;margin:2px 0 0!important}.home-health-group .home-insight-card.is-empty .home-insight-desc{grid-column:1;grid-row:3}.home-health-group .home-insight-card.is-empty .home-insight-footer{grid-column:2;grid-row:1/4;margin:0!important;align-self:center}.home-health-group .home-connect-notice{margin:0 0 16px!important;width:100%;background:var(--fill)!important;border:0!important}
`;
const typographyCss = `
.home-health-group .home-insight-card{padding:18px;grid-template-columns:minmax(0,1fr) auto;gap:10px 12px;align-items:center}
.home-health-group .home-insight-top{grid-column:1;grid-row:1;gap:8px}
.home-health-group .home-insight-label,.home-health-group .home-age-label{font-size:var(--t-body);font-weight:600;letter-spacing:-.02em;line-height:1.4}
.home-health-group .home-insight-icon,.home-health-group .home-age-symbol{font-size:21px;width:26px;height:26px}
.home-health-group #gptInsightAction{grid-column:2;grid-row:1;align-self:center;background:none!important;border:0!important;padding:6px 0!important;font-size:var(--t-cap);font-weight:500;color:var(--ink-2);text-align:right}
.home-health-group .home-insight-title{grid-column:1/-1;grid-row:2;margin:0!important;font-size:32px!important;line-height:1.25!important;letter-spacing:-.03em}
.home-health-group .home-insight-footer{grid-column:1/-1;grid-row:3;margin:0!important;font-size:var(--t-mini);line-height:1.5}
.home-health-group .home-insight-card.is-empty .home-insight-title{grid-column:1/-1;grid-row:2;font-size:var(--t-body)!important;font-weight:500!important;margin:0!important;color:var(--ink-2)}
.home-health-group .home-insight-card.is-empty .home-insight-desc{display:none!important}.home-health-group .home-insight-card.is-empty .home-insight-footer{display:none}
.home-health-group .home-age-summary{grid-template-columns:minmax(0,1fr) auto;padding:18px 0;gap:10px 12px;align-items:center}
.home-health-group .home-age-label{grid-column:1;grid-row:1;gap:8px}
.home-health-group .home-age-chevron{position:static;transform:none;grid-column:2;grid-row:1;font-size:var(--t-cap);font-weight:500;color:var(--ink-2);padding:6px 0;min-height:0;min-width:0;line-height:1.4}
.home-health-group .home-age-number{grid-column:1;grid-row:2;font-size:32px!important;line-height:1.25!important;letter-spacing:-.03em;margin:0!important}
.home-health-group .home-age-diff{grid-column:2;grid-row:2;text-align:right;order:initial;font-size:var(--t-cap);margin:0}
.home-health-group .home-age-meta{grid-column:1/-1;grid-row:3;order:initial;padding:0;font-size:var(--t-mini);line-height:1.5;margin:0}
.home-health-group .home-age-number span,.home-health-group .home-insight-title small{font-size:var(--t-sm)!important}
`;
const hospitalAgeCss = `
.home-health-group .home-age-summary.has-hospital-age{display:block;padding:0}
.home-health-group .home-age-summary.has-hospital-age>:not(.home-hospital-age){display:none!important}
.home-health-group .home-hospital-age{padding:24px 2px 26px;text-align:center}
.home-health-group .home-insight-card.is-empty #gptInsightAction{grid-column:1/-1;grid-row:3;justify-self:stretch;text-align:center;background:var(--brand)!important;color:#fff;border-radius:var(--r-in);padding:12px 16px!important;font-size:var(--t-sm);font-weight:600;margin-top:4px}
.home-health-group .home-insight-card.is-empty .home-insight-title{grid-column:1/-1;grid-row:2;font-size:var(--t-body)!important;line-height:1.6!important;color:var(--ink-2)}
`;
const insightReferenceCss = `
.home-health-group .home-insight-card.has-result{display:block;padding:22px 20px;text-align:left}
.home-health-group .home-insight-card.has-result>:not(.home-score-result){display:none!important}
.home-score-result{display:block}.home-score-headline{display:block;font-size:18px;font-weight:650;line-height:1.65;letter-spacing:-.025em;color:var(--ink-1);padding-bottom:18px;border-bottom:1px solid var(--line)}
.home-score-label{display:block;color:var(--ink-3);font-size:var(--t-sm);font-weight:600;margin:14px 0 9px}.home-score-line{display:flex;align-items:baseline;justify-content:space-between;gap:12px}.home-score-value{font-size:44px;font-weight:700;color:#2252D9;letter-spacing:-.04em;line-height:1.2}.home-score-value small{font-size:16px;font-weight:400;color:var(--ink-3);letter-spacing:0;margin-left:4px}.home-score-change{font-size:var(--t-cap);font-weight:500;color:var(--ink-3);white-space:nowrap}.home-score-change b{font-size:16px;font-weight:500;margin-left:6px;color:var(--ink-2)}
.home-score-track{display:block;height:10px;background:#E5E7ED;border-radius:999px;margin-top:18px;overflow:hidden}.home-score-track i{display:block;height:100%;background:#3B7EF4;border-radius:inherit}.home-score-meta{font-size:var(--t-mini);color:var(--ink-3);margin-top:10px;display:block}.home-insight-section-title{display:flex;justify-content:space-between;align-items:center;margin:0 2px 10px;font-size:var(--t-sm);font-weight:600;color:var(--ink-2)}.home-insight-section-title small{font-size:var(--t-mini);font-weight:400}
`;
const compactHomeCss = `
/* Home uses compact previews; full text remains in the existing detail view. */
.home-health-group .home-insight-card.has-result{padding:16px 18px}
.home-score-headline{font-size:var(--t-body);font-weight:600;line-height:1.55;padding-bottom:0;border:0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.home-score-label{font-size:var(--t-mini);font-weight:500;margin:11px 0 3px}
.home-score-value{font-size:30px;line-height:1.2}.home-score-value small{font-size:var(--t-cap)}
.home-score-change{font-size:var(--t-mini)}.home-score-change b{font-size:var(--t-sm)}
.home-score-track{height:6px;margin-top:10px}.home-score-meta{font-size:10px;margin-top:7px}
.home-insight-section-title{margin-bottom:8px}
.home-health-group .home-hospital-age{padding:17px 0 14px}
.home-health-group .home-hospital-age .ttl{font-size:var(--t-sm)}
.home-health-group .home-hospital-age .age-num{font-size:30px;margin:3px 0 5px}
.home-health-group .home-hospital-age .dt2{font-size:var(--t-mini)}
.home-health-group .home-hospital-age .age-gauge{margin:27px 10px 0;padding-bottom:22px}
.home-health-group .home-hospital-age .age-track{height:12px}
.home-health-group .home-hospital-age .age-badge{top:-23px;padding:3px 7px;font-size:10px}
.home-health-group .home-hospital-age .age-mark{padding:3px 7px;font-size:10px}
.home-health-group .home-peer{padding:13px 0 11px}
.home-health-group .home-peer-grid{margin-top:12px!important}
.home-health-group .home-peer-emoji{width:28px;height:28px;font-size:20px!important;border-radius:9px;margin-bottom:5px}
.home-health-group .home-peer-item strong{font-size:22px!important;margin:2px 0}
.home-health-group .home-peer-help{margin-top:10px;padding-top:7px}
`;
const unifiedSummaryCss = `
.home-insight-section-title{display:none!important}
.home-health-group .home-insight-card.has-result{padding:12px 18px;min-height:0;height:auto}
.home-score-result{display:grid;grid-template-columns:minmax(0,1fr) auto 12px;column-gap:12px;row-gap:6px;align-items:center}
.home-score-name{grid-column:1;grid-row:1;display:flex;align-items:center;gap:7px;font-size:var(--t-body);font-weight:600;color:var(--ink-1)}
.home-score-symbol,.home-health-group .home-age-label .home-age-symbol,.home-health-group .home-insight-icon{display:inline-flex;align-items:center;justify-content:center;flex:none;width:20px;height:20px;font-size:18px;line-height:1;background:transparent}
.home-score-headline{display:none}
.home-score-result{row-gap:6px}
.home-score-name{grid-row:1}
.home-score-period{grid-column:1;grid-row:2;padding-left:27px;font-size:var(--t-mini);line-height:1.5;color:var(--ink-3)}
.home-score-result{row-gap:4px}
.home-score-line{align-self:center}
.home-score-line{grid-column:2;grid-row:1/3;display:block}.home-score-value{font-size:30px;color:var(--ink-1);line-height:1.2;white-space:nowrap}.home-score-value small{font-size:var(--t-mini)}
.home-score-result::after{content:'›';grid-column:3;grid-row:1/3;font-size:20px;color:var(--ink-3)}
.home-score-label,.home-score-change,.home-score-track,.home-score-meta{display:none!important}
.home-health-group .home-age-summary.has-hospital-age{display:grid;grid-template-columns:minmax(0,1fr) auto 12px;gap:6px 12px;padding:18px 0;min-height:94px;align-items:center}
.home-health-group .home-age-summary.has-hospital-age>.home-age-label{display:flex!important;grid-column:1;grid-row:1;font-size:var(--t-body);font-weight:600;min-height:0}
.home-health-group .home-age-summary.has-hospital-age>.home-age-label .home-age-symbol{display:inline-flex}
.home-health-group .home-age-summary.has-hospital-age>.home-age-number{display:block!important;grid-column:2;grid-row:1/3;font-size:30px!important;margin:0!important;color:var(--ink-1)}
.home-health-group .home-age-summary.has-hospital-age>.home-age-number span{font-size:var(--t-mini)!important}
.home-health-group .home-age-summary.has-hospital-age>.home-age-diff{display:block!important;grid-column:1;grid-row:2;text-align:left;color:var(--ink-2);font-size:var(--t-cap)}
.home-health-group .home-age-summary.has-hospital-age>.home-age-chevron{display:block!important;grid-column:3;grid-row:1/3;position:static;transform:none;font-size:20px;padding:0;color:var(--ink-3)}
.home-health-group .home-hospital-age{display:none!important}
`;
const compactSupportingCss = "\n/* Compact summaries with one supporting line */\n.home-health-group .home-insight-card.has-result{padding:16px 18px;min-height:80px}\n.home-score-result{grid-template-columns:minmax(0,1fr) auto 12px;row-gap:3px}\n.home-score-line{display:flex;flex-direction:column;align-items:flex-end;gap:2px;grid-column:2;grid-row:1/3}\n.home-score-change:empty{display:none!important}\n.home-score-period{font-size:12px;color:var(--ink-2);white-space:normal}\n.home-health-group .home-age-summary.has-hospital-age{grid-template-columns:minmax(0,1fr) auto 12px;min-height:80px;padding:16px 0;row-gap:3px}\n.home-health-group .home-age-summary.has-hospital-age>.home-age-number{grid-column:2;grid-row:1/3;align-self:center}\n.home-health-group .home-age-summary.has-hospital-age>.home-age-diff{grid-column:1;grid-row:2;text-align:left;padding-left:27px;font-size:12px;color:var(--ink-2)}\n.home-health-group .home-age-summary.has-hospital-age>.home-age-meta{display:none!important}\n";
const matchedSummaryCss = "\n/* Matched home summary rows */\n.home-health-group .home-insight-card.has-result{padding:16px 18px;min-height:88px}\n.home-score-result{grid-template-columns:minmax(0,1fr) 102px 12px;row-gap:4px}\n.home-score-line{display:contents}\n.home-score-value{grid-column:2;grid-row:1;text-align:right;font-size:30px}\n.home-score-change{display:block!important;grid-column:2;grid-row:2;text-align:right;font-size:11px;line-height:1.5;color:var(--ink-2);font-weight:400}\n.home-score-period{padding-left:27px;font-size:11px;white-space:nowrap}\n.home-health-group .home-age-summary.has-hospital-age{grid-template-columns:minmax(0,1fr) 102px 12px;min-height:88px;padding:16px 0;row-gap:4px}\n.home-health-group .home-age-summary.has-hospital-age>.home-age-number{grid-row:1;text-align:right;line-height:1.2!important}\n.home-health-group .home-age-summary.has-hospital-age>.home-age-diff{grid-column:2;grid-row:2;text-align:right;font-size:11px;line-height:1.5;white-space:nowrap}\n.home-health-group .home-age-summary.has-hospital-age>.home-age-meta{display:block!important;grid-column:1;grid-row:2;padding-left:27px;margin:0;font-size:11px;line-height:1.5;color:var(--ink-3)}\n";
html = html.replace('</head>', '<style>'+css+polishedCss+friendlyCss+groupedCheckupCss+typographyCss+hospitalAgeCss+insightReferenceCss+compactHomeCss+unifiedSummaryCss+matchedSummaryCss+compactSupportingCss+'</style></head>');
const script = `
<script>
(function(){
 const home=document.getElementById('home');
 const hero=home.querySelector('.home-hero');
 const question=document.getElementById('secQ');
 const coach=document.getElementById('coach').parentElement;
 const goals=document.getElementById('gList').parentElement;
 const condition=document.getElementById('cond').parentElement;
 const data=document.getElementById('dList').parentElement;
 const overview=document.createElement('section');overview.className='sec home-overview';
 overview.innerHTML='<div class="h-sec"><div class="h-t">검진으로 본 내 건강</div></div><section class="home-age-card"><div class="home-age-copy"><b>건강나이</b><div id="homeAgeDiff" class="home-age-diff"></div><div id="homeAgeMeta" class="home-age-meta"></div></div><div id="homeAgeValue" class="home-age-number"></div><button id="homeAgeOpen" class="home-age-chevron" aria-label="건강나이 분석 자세히 보기">›</button></section>';
 condition.after(overview);overview.after(data);
 const insight=document.createElement('section');insight.className='sec home-insight';condition.after(insight);
 insight.innerHTML='<button class="home-insight-card" id="gptHomeInsight"><span class="home-insight-top"><span class="home-insight-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19V12M12 19V8M19 19V4M4 5l4-2 4 2 7-3"/></svg></span><span class="home-insight-label">AI 인사이트</span><span class="home-insight-badge" id="gptInsightBadge"></span></span><strong class="home-insight-title" id="gptInsightTitle"></strong><span class="home-insight-desc" id="gptInsightDesc"></span><span class="home-insight-footer"><span id="gptInsightPeriod"></span><span class="home-insight-action" id="gptInsightAction"></span></span></button>';
 const scoreResult=document.createElement('span');scoreResult.className='home-score-result';scoreResult.hidden=true;scoreResult.innerHTML='<strong class="home-score-headline"></strong><span class="home-score-label">종합 점수</span><span class="home-score-line"><span class="home-score-value"></span><span class="home-score-change"></span></span><span class="home-score-track" role="progressbar" aria-label="AI 인사이트 종합 점수" aria-valuemin="0" aria-valuemax="100"><i></i></span><span class="home-score-meta"></span>';document.getElementById('gptHomeInsight').append(scoreResult);
 const scoreHeading=document.createElement('div');scoreHeading.className='home-insight-section-title';scoreHeading.innerHTML='<span>AI 건강 인사이트</span><button type="button" style="border:0;background:none;font:inherit;font-size:var(--t-mini);font-weight:400;color:var(--ink-2);cursor:pointer;padding:5px 0">자세히 ›</button>';scoreHeading.hidden=true;insight.prepend(scoreHeading);scoreHeading.querySelector('button').onclick=()=>document.getElementById('gptHomeInsight').click();
 if(new URLSearchParams(location.search).get('preview')==='insight'&&deviceLinked&&!aiThisWeekReport()){AI_REPORTS.push(aiCreateReport());}
 scoreResult.insertAdjacentHTML('afterbegin','<span class="home-score-name"><span class="home-score-symbol" aria-hidden="true">✨</span>AI 건강 인사이트</span><span class="home-score-period"></span>');
 function renderHomeInsight(){
  const report=aiThisWeekReport();const effective=report?aiEffectiveReport(report):null;
  document.getElementById('gptHomeInsight').classList.toggle('has-result',!!effective);scoreResult.hidden=!effective;scoreHeading.hidden=!effective;
  if(effective){
   scoreResult.querySelector('.home-score-headline').textContent=effective.headline;
   scoreResult.querySelector('.home-score-period').textContent=effective.range;
   scoreResult.querySelector('.home-score-value').innerHTML=effective.score+'<small>/ 100</small>';
   const priorDate=new Date(report.generatedAt+'T00:00:00');priorDate.setDate(priorDate.getDate()-7);const prior=aiReportForWeekOf(isoOf(priorDate));const previous=prior?aiEffectiveReport(prior):null;
   const delta=previous?effective.score-previous.score:null;
   scoreResult.querySelector('.home-score-change').textContent=delta===null?'':delta===0?'지난주와 같아요':'지난주보다 '+Math.abs(delta)+'점 '+(delta>0?'↑':'↓');
   const track=scoreResult.querySelector('.home-score-track');track.setAttribute('aria-valuenow',effective.score);track.querySelector('i').style.width=Math.max(0,Math.min(100,effective.score))+'%';scoreResult.querySelector('.home-score-meta').textContent=effective.range+' · 시연 데이터';
  }
  document.getElementById('gptInsightBadge').textContent=effective?'분석 완료':deviceLinked?'이번 주':'연동 필요';
  document.getElementById('gptHomeInsight').classList.toggle('is-empty',!effective);
  document.getElementById('gptInsightTitle').innerHTML=effective?effective.score+'<small>/ 100점</small>':deviceLinked?'이번 주는 분석 결과가 없어요':'생활 기록을 연결하면 분석할 수 있어요';
  document.getElementById('gptInsightDesc').textContent=effective?'생활 기록과 검진정보를 함께 살펴본 분석이에요.':deviceLinked?'수면·활동·심박의 변화를 모아 정리해 드려요.':'연결한 생활 기록을 바탕으로 변화를 정리해 드려요.';
  if(effective&&!imp.checkup)document.getElementById('gptInsightDesc').textContent='생활 기록을 함께 살펴본 분석이에요.';
  if(!effective)document.getElementById('gptInsightDesc').textContent=deviceLinked?'쌓인 기록을 함께 살펴봐요.':'건강 기록을 연결해 주세요.';
  document.getElementById('gptInsightPeriod').textContent=effective?effective.range:'이번 주 기록';
  document.getElementById('gptInsightAction').textContent=effective?'자세히 ›':deviceLinked?'분석하기':'생활 기록 연동하기';
 }
 document.getElementById('gptHomeInsight').onclick=()=>{navs.forEach((button,index)=>button.classList.toggle('on',index===1));show('life');document.querySelector('.l-tab[data-t="ai"]').click();};
 insight.querySelector('.home-insight-top').after(document.getElementById('gptInsightAction'));
 renderHomeInsight();
 const healthGroup=document.createElement('section');healthGroup.className='sec home-health-group';healthGroup.setAttribute('aria-label','나의 건강, 숫자로 한눈에');
 healthGroup.innerHTML='<div class="h-sec"><h2 class="h-t">나의 건강, 숫자로 한눈에</h2></div><p class="home-health-caption">생활 기록과 검진 결과를 함께 살펴보세요.</p>';
 data.after(healthGroup);healthGroup.append(insight,overview);
 overview.querySelector('.h-sec').remove();
 overview.querySelector('.home-age-copy>b').textContent='내 건강나이';
 const peer=document.createElement('div');peer.className='home-peer';
 const peerDemo=[{label:'키',rank:58,value:'164.2 cm'},{label:'체중',rank:78,value:'68.4 kg'},{label:'BMI',rank:81,value:'25.7'},{label:'허리둘레',rank:84,value:'86.0 cm'}];
 peer.innerHTML='<div class="home-peer-heading"><b>또래 100명 속 내 등수는?</b><small>시연 예시</small></div><p class="home-peer-caption">같은 성별·연령대의 항목별 분포 위치</p><div class="home-peer-grid">'+peerDemo.map(item=>'<div class="home-peer-item"><span>'+item.label+'</span><strong>'+item.rank+'<small>등</small></strong><em>'+item.value+'</em></div>').join('')+'</div><p class="home-peer-note">기존 또래 비교 화면의 시연값이에요.<br>항목별 위치이며, 숫자는 항목별 분포에서의 위치를 뜻해요.</p>';
 overview.querySelector('.home-age-card').appendChild(peer);
 const ageCard=overview.querySelector('.home-age-card');const ageSummary=document.createElement('div');ageSummary.className='home-age-summary';
 const ageCopy=overview.querySelector('.home-age-copy');const ageLabel=ageCopy.querySelector('b');ageLabel.className='home-age-label';
 ageLabel.innerHTML='<span class="home-age-symbol" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20.5 5.5a5 5 0 0 0-7 0L12 7l-1.5-1.5a5 5 0 0 0-7 7L12 21l8.5-8.5a5 5 0 0 0 0-7Z"/><path d="M4 12h4l2-3 3 6 2-3h5"/></svg></span>내 건강나이';
 ageSummary.append(ageLabel,document.getElementById('homeAgeValue'),document.getElementById('homeAgeDiff'),document.getElementById('homeAgeMeta'),document.getElementById('homeAgeOpen'));ageCopy.remove();ageCard.prepend(ageSummary);
 const peerIcons=['M12 3v18M8 7l4-4 4 4M8 17l4 4 4-4','M5 5h14v15H5zM9 5V3h6v2M9 10h6M12 10l2-2','M7 3h10v18H7zM10 7h4M10 11h4M10 15h4M10 18h4','M5 7c4-3 10-3 14 0v10c-4 3-10 3-14 0zM5 11c4 3 10 3 14 0M9 13v3M13 13v3'];
 peer.querySelectorAll('.home-peer-item').forEach((item,index)=>item.insertAdjacentHTML('afterbegin','<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="'+peerIcons[index]+'"/></svg>'));
 const friendlyIcons=['🧍','⚖️','📊','📏'];
 peer.querySelectorAll('.home-peer-item').forEach((item,index)=>{item.querySelector('svg').remove();item.insertAdjacentHTML('afterbegin','<span class="home-peer-emoji" aria-hidden="true">'+friendlyIcons[index]+'</span>');});
 insight.querySelector('.home-insight-icon').textContent='✨';
 overview.querySelector('.home-age-symbol').textContent='💗';
 peer.insertAdjacentHTML('beforeend','<details class="home-peer-help"><summary>비교 기준</summary><p>같은 성별·연령대의 항목별 분포 위치를 보여주는 시연값이에요. 숫자는 항목별 분포에서의 위치를 뜻해요.</p></details>');
 document.getElementById('homeAgeValue').setAttribute('aria-label','건강나이');
 insight.querySelector('.home-insight-label').textContent='AI 건강 인사이트';
 const note=document.createElement('div');note.className='home-preview-note';note.textContent='RSNA 시연용 예시 데이터 · 정보 중심 홈 구성안';home.appendChild(note);
 function refreshOverview(){
  renderHomeInsight();
  insight.hidden=false;
  overview.hidden=false;
  insight.style.gridColumn='1';
  ageSummary.style.gridColumn='2';
  connectNotice.hidden=imp.checkup;
  connectNotice.textContent='검진정보를 연동하고 건강나이·또래 비교를 확인해 보세요. ›';
  peer.hidden=!imp.checkup;
  document.getElementById('homeAgeValue').innerHTML=imp.checkup?USER.healthAge+'<span>세</span>':'—';
  const difference=USER.healthAge-USER.realAge;
  document.getElementById('homeAgeDiff').innerHTML=imp.checkup?'실제 '+USER.realAge+'세'+(difference===0?'와 같아요':'보다 '+(difference>0?'+':'−')+Math.abs(difference)+'세'):'검진정보 연결 필요';
  document.getElementById('homeAgeMeta').textContent=imp.checkup?'실제 나이 '+USER.realAge+'세':'검진정보 미연동';
  document.getElementById('homeAgeOpen').setAttribute('aria-label',imp.checkup?'건강나이 분석 자세히 보기':'검진정보 연결');
  document.getElementById('homeAgeOpen').textContent=imp.checkup?'›':'연동하기 ›';
  ageSummary.classList.toggle('has-hospital-age',imp.checkup);
  hospitalAge.hidden=!imp.checkup;
  if(imp.checkup){
   const sourceCard=document.querySelector('#pCk .age-card');
   hospitalAge.innerHTML=sourceCard?sourceCard.innerHTML:'<div class="ttl"><b>'+USER.name+'</b>님의 건강 나이는</div><div class="age-num">'+USER.healthAge+'세</div><div class="dt2">검진일자: '+USER.checkedAt+'</div><div class="age-gauge"><div class="age-track"><i style="left:50%;width:28%"></i></div><span class="age-badge" style="left:78%">+'+difference+'</span><span class="age-mark" style="left:50%">실제 '+USER.realAge+'세</span></div>';
  }
 }
 const ageDetail=document.createElement('div');ageDetail.className='sub';ageDetail.id='gptHealthAgeDetail';ageDetail.setAttribute('aria-label','나의 건강나이');
 ageDetail.innerHTML='<div class="rs-h"><button id="gptAgeBack" aria-label="뒤로">‹</button><h2>나의 건강나이</h2></div><div class="rs-b" id="gptAgeBody"></div>';
 document.querySelector('.app').appendChild(ageDetail);
 document.getElementById('gptAgeBack').onclick=()=>ageDetail.classList.remove('open');
 document.getElementById('homeAgeOpen').onclick=()=>{
  if(!imp.checkup){startImport('checkup');return;}
  const difference=USER.healthAge-USER.realAge;
  document.getElementById('gptAgeBody').innerHTML='<section class="card age-card"><div class="ttl"><b>'+USER.name+'</b>님의 건강나이</div><div class="age-num">'+USER.healthAge+'세</div><div class="dt2">'+USER.checkedAt+' 검진 기준</div><div style="margin-top:16px;font-size:var(--t-body);color:var(--ink-2)">실제 나이 '+USER.realAge+'세 대비 <b style="color:var(--brand)">'+(difference>0?'+':'')+difference+'세</b></div></section><section class="card" style="margin-top:14px"><div class="card-t">검진정보와 함께 살펴보세요</div><p style="font-size:var(--t-sm);color:var(--ink-2);margin-top:10px;line-height:1.7">검진요약에 표시된 건강나이예요. 검진일과 당시의 검사 수치를 함께 확인해 보세요.</p><button class="fd-all" id="gptAgeCheckup" style="margin-top:16px">검진 결과 보기 ›</button></section><p style="font-size:var(--t-mini);color:var(--ink-3);padding:16px 4px">RSNA 프로토타입의 예시 값입니다.</p>';
  document.getElementById('gptAgeCheckup').onclick=()=>{ageDetail.classList.remove('open');openLatestCheckup();};
  ageDetail.classList.add('open');
 };
 const connectNotice=document.createElement('button');connectNotice.className='home-connect-notice';connectNotice.style.cssText='grid-column:1/-1;margin-top:10px;padding:16px 18px;border:1px solid var(--line);border-radius:var(--r);background:#fff;color:var(--ink-2);font:inherit;font-size:var(--t-cap);text-align:left;cursor:pointer;line-height:1.6';healthGroup.append(connectNotice);connectNotice.onclick=()=>startImport('checkup');
 ageCard.append(connectNotice);
 const hospitalAge=document.createElement('div');hospitalAge.className='age-card home-hospital-age';ageSummary.append(hospitalAge);
 const originalRefresh=refreshHome;refreshHome=function(){originalRefresh();refreshOverview();};
 const originalShow=show;show=function(name){originalShow(name);if(name==='home')refreshOverview();};
 refreshOverview();
})();
</script>`;
html=html.replace('</body>',script+'</body>');
const target=path.join(__dirname,'gpt_maiReport_RSNA_home_information_v1.0.html');
fs.writeFileSync(target,html,'utf8');
for(const match of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g))new (require('vm').Script)(match[1]);
console.log(target+'\nInline JavaScript syntax: OK');









