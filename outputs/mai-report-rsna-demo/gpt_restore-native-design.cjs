const fs=require('fs'),path=require('path');
const file=path.join(__dirname,'gpt_build-home-preview.cjs');
let s=fs.readFileSync(file,'utf8');
const start=s.indexOf('const css = `');const end=s.indexOf('`;',start)+2;
s=s.slice(0,start)+`const css = \`
/* Existing prototype styles remain authoritative. Only new home content is styled. */
#home>.home-hero{background:var(--page);margin-bottom:12px;padding-bottom:0}
.home-overview .home-age-card{background:#fff;border-radius:var(--r);padding:20px;box-shadow:var(--sh)}
.home-overview .home-info-row{display:flex;align-items:center;justify-content:space-between;gap:10px}
.home-overview .home-info-row b{font-size:var(--t-h2);font-weight:700}
.home-overview .home-info-tag{font-size:var(--t-mini);color:var(--ink-2);background:var(--fill);border-radius:6px;padding:3px 7px}
.home-overview .home-age-number{font-size:40px;line-height:1.3;font-weight:700;color:var(--brand);margin:12px 0 5px;letter-spacing:-.04em}
.home-overview .home-age-number span{font-size:var(--t-h2);margin-left:4px}
.home-overview .home-age-diff{font-size:var(--t-cap);color:var(--ink-2)}
.home-overview .home-age-diff b{margin-left:7px;color:var(--warn)}
.home-overview .home-age-footer{display:flex;align-items:center;justify-content:space-between;border-top:1px solid var(--line);padding-top:12px;margin-top:15px;font-size:var(--t-mini);color:var(--ink-3)}
.home-overview .home-info-link{background:none;border:none;color:var(--brand);font-size:var(--t-cap);font-weight:600;padding:5px 0;cursor:pointer}
#home .home-question-section{padding:18px;margin-bottom:14px}
#pRead .reading-cover{display:block;width:calc(100% + 40px);max-width:none;aspect-ratio:3/2;object-fit:cover;margin:-20px -20px 20px;border-radius:var(--r) var(--r) 0 0}
#pRead>.card:first-child{overflow:hidden}
.home-preview-note{font-size:var(--t-mini);color:var(--ink-3);text-align:center;padding:4px 18px 16px}
\`;
`+s.slice(end);
s=s.replace("css+fs.readFileSync(path.join(__dirname,'gpt_ui-refinement.css'),'utf8')","css");
s=s.replace('<div class="hello">김마이님의 건강 리포트</div><h1>내 건강을 한눈에</h1>','');
s=s.replace("hero.after(overview);overview.after(data);data.after(question);question.classList.add('home-question-section');question.after(coach);coach.after(goals);goals.after(condition);","hero.after(overview);overview.after(question);question.classList.add('home-question-section','home-hero');question.after(coach);coach.after(goals);goals.after(condition);condition.after(data);");
fs.writeFileSync(file,s,'utf8');require(file);
