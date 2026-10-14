$ErrorActionPreference='Stop'
$src='C:\Users\이사라\Documents\Project_maiReport\outputs\mai-report-ia\maiReport_기능정의서.html'
$dst='C:\Users\이사라\Documents\Project_maiReport\outputs\mai-report-ia\maiReport_기능정의서_보드용.html'
$raw=[System.IO.File]::ReadAllText($src,[System.Text.Encoding]::UTF8)
$lines=$raw -split "`r?`n"

$rxG=New-Object System.Text.RegularExpressions.Regex "\{key:'([^']*)',no:'([^']*)',title:'([^']*)',desc:'([^']*)'"
$rxF=New-Object System.Text.RegularExpressions.Regex "F\('([^']*)','([^']*)','([^']*)','([^']*)','([^']*)','([^']*)','([^']*)','([^']*)','([^']*)',\[([^\]]*)\](?:,'([^']*)')?\)"
$rxS=New-Object System.Text.RegularExpressions.Regex "'([^']*)':\{area:'([^']*)',name:'([^']*)',dom:'([^']*)'\}"

$screen=@{}
foreach($ln in $lines){ $m=$rxS.Match($ln); if($m.Success){ $screen[$m.Groups[1].Value]=$m.Groups[3].Value } }

$statusLabel=@{done='프로토타입 구현';review='정책 검토 필요';link='시스템 연계 필요'}
$statusPill=@{done='p-g';review='p-l';link='p-b'}

$groups=@(); $cur=$null
foreach($ln in $lines){
  $g=$rxG.Match($ln)
  if($g.Success){ $cur=[pscustomobject]@{no=$g.Groups[2].Value;title=$g.Groups[3].Value;desc=$g.Groups[4].Value;items=(New-Object System.Collections.Generic.List[object])}; $groups+=$cur; continue }
  if($cur -eq $null){ continue }
  $f=$rxF.Match($ln)
  if($f.Success){
    $st=$f.Groups[11].Value; if([string]::IsNullOrEmpty($st)){ $st='done' }
    $scr=($f.Groups[10].Value -replace "'",'' -split ',') | ForEach-Object{ $_.Trim() } | Where-Object{ $_ -ne '' }
    $cur.items.Add([pscustomobject]@{
      id=$f.Groups[1].Value; name=$f.Groups[2].Value; summary=$f.Groups[3].Value
      trigger=$f.Groups[4].Value; input=$f.Groups[5].Value; process=$f.Groups[6].Value
      output=$f.Groups[7].Value; pre=$f.Groups[8].Value; exc=$f.Groups[9].Value
      screens=$scr; status=$st })
  }
}
$total=($groups | ForEach-Object { $_.items.Count } | Measure-Object -Sum).Sum
if($total -lt 100){ throw "기능 파싱 실패: $total" }

function E($s){ $s -replace '&','&amp;' -replace '<','&lt;' -replace '>','&gt;' }

$sb=New-Object System.Text.StringBuilder
function A($t){ [void]$sb.AppendLine($t) }

A '<!doctype html>'
A '<html lang="ko">'
A '<head>'
A '<meta charset="utf-8">'
A '<meta name="viewport" content="width=device-width,initial-scale=1">'
A '<title>마이리포트 v2 · 기능정의서</title>'
A '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;800&display=swap" rel="stylesheet">'
A '<style>'
A '  :root{--brand:#2f66f5;--brand-soft:#eef3ff;--page:#f5f7fb;--ink-1:#1a2233;--ink-2:#4b5468;--ink-3:#8892a6;--line:#e6eaf2;--warn:#E5893A;--green:#12A150}'
A '  *{box-sizing:border-box;margin:0;padding:0}'
A '  body{font-family:"Noto Sans KR",-apple-system,sans-serif;background:var(--page);color:var(--ink-2);font-size:14px;line-height:1.7;letter-spacing:-.01em}'
A '  .wrap{max-width:1080px;margin:0 auto;padding:32px 20px 80px}'
A '  .hero{background:linear-gradient(135deg,#2f66f5 0%,#5170ff 55%,#7c5cfc 100%);border-radius:28px;padding:38px 40px;color:#fff;margin-bottom:22px}'
A '  .hero .tag{display:inline-block;background:rgba(255,255,255,.18);border-radius:999px;padding:4px 12px;font-size:12px;font-weight:700;margin-bottom:14px}'
A '  .hero h1{font-size:28px;font-weight:800;letter-spacing:-.03em;margin-bottom:10px}'
A '  .hero p{font-size:14.5px;color:rgba(255,255,255,.9);max-width:760px}'
A '  .hero .meta{margin-top:18px;font-size:12px;color:rgba(255,255,255,.82);display:flex;gap:18px;flex-wrap:wrap}'
A '  .hero .meta b{color:#fff}'
A '  .toc{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:22px}'
A '  .toc a{background:#fff;border:1px solid var(--line);border-radius:999px;padding:6px 13px;font-size:12px;color:var(--brand);font-weight:700;text-decoration:none}'
A '  section.card{background:#fff;border:1px solid var(--line);border-radius:22px;padding:30px 32px;margin-bottom:18px}'
A '  h2{font-size:19px;font-weight:800;color:var(--ink-1);display:flex;align-items:center;gap:10px;margin-bottom:6px;letter-spacing:-.02em}'
A '  h2 .n{width:26px;height:26px;border-radius:8px;background:var(--brand-soft);color:var(--brand);font-size:12.5px;font-weight:800;display:inline-flex;align-items:center;justify-content:center}'
A '  .sub{font-size:12.5px;color:var(--ink-3);margin-bottom:18px}'
A '  h3{font-size:14.5px;font-weight:800;color:var(--ink-1);margin:22px 0 8px}'
A '  table{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0 6px}'
A '  th{font-weight:600;color:var(--ink-3);text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);font-size:12px}'
A '  td{padding:10px 10px;border-bottom:1px solid var(--line);vertical-align:top;color:var(--ink-2)}'
A '  td.k{font-weight:700;color:var(--ink-1);white-space:nowrap}'
A '  .callout{border-left:3px solid var(--brand);background:var(--brand-soft);border-radius:0 12px 12px 0;padding:12px 16px;font-size:13px;color:#1d3a8a;margin:12px 0}'
A '  .pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11px;font-weight:800;margin-right:4px}'
A '  .p-g{background:#E7F7ED;color:var(--green)}.p-l{background:#FDF0E3;color:var(--warn)}.p-b{background:var(--brand-soft);color:var(--brand)}'
A '  .note{font-size:12px;color:var(--ink-3)}'
A '  @media(max-width:720px){.hero{padding:28px 22px}section.card{padding:22px 18px}}'
A '</style>'
A '</head>'
A '<body>'
A '<div class="wrap">'
A ''
A '<div class="hero">'
A '  <span class="tag">마이리포트 v2 · 기능정의서</span>'
A '  <h1>maiReport 기능정의서</h1>'
A '  <p>최신 HTML 프로토타입의 화면 구성과 홈 화면 · 목표 분석 화면정의서, 생활 지표 기획서, 하루 생성 순서도, 알림 정책, 식이 목표 생성 규칙을 반영해 시스템 처리 요구사항을 기능 단위로 정의한다. 문서 보드 생성기에서 읽을 수 있도록 같은 내용을 장 · 표 구조로 옮긴 판이다.</p>'
A ("  <div class=""meta""><span>기준일 <b>2026-09-16</b></span><span>버전 <b>2.0</b></span><span>기능 수 <b>$($total)개 · $($groups.Count)개 영역</b></span><span>연관 문서 <b>홈화면_화면정의서 · 목표분석_화면정의서 · 생활지표_기획서 · 하루생성_순서도 · 알림정책</b></span></div>")
A '</div>'
A ''
$toc='<div class="toc">'
foreach($g in $groups){ $toc += ('<a href="#s{0}">{1} {2}</a>' -f $g.no,$g.no,(E $g.title)) }
$toc += '</div>'
A $toc
A ''
foreach($g in $groups){
  A ('<section class="card" id="s{0}">' -f $g.no)
  A ('  <h2><span class="n">{0}</span>{1}</h2>' -f $g.no,(E $g.title))
  A ('  <div class="sub">{0} · 기능 {1}개</div>' -f (E $g.desc),$g.items.Count)
  A '  <table>'
  A '    <tr><th style="width:110px">기능 ID</th><th style="width:210px">기능명</th><th>기능 설명</th><th style="width:110px">상태</th></tr>'
  foreach($it in $g.items){
    A ('    <tr><td class="k">{0}</td><td class="k">{1}</td><td>{2}</td><td><span class="pill {3}">{4}</span></td></tr>' -f $it.id,(E $it.name),(E $it.summary),$statusPill[$it.status],$statusLabel[$it.status])
  }
  A '  </table>'
  foreach($it in $g.items){
    A ('  <h3>{0} · {1}</h3>' -f $it.id,(E $it.name))
    A '  <table>'
    A '    <tr><th style="width:110px">항목</th><th>내용</th></tr>'
    A ('    <tr><td class="k">트리거</td><td>{0}</td></tr>' -f (E $it.trigger))
    A ('    <tr><td class="k">입력값</td><td>{0}</td></tr>' -f (E $it.input))
    A ('    <tr><td class="k">처리 로직</td><td>{0}</td></tr>' -f (E $it.process))
    A ('    <tr><td class="k">출력값</td><td>{0}</td></tr>' -f (E $it.output))
    A ('    <tr><td class="k">선행조건</td><td>{0}</td></tr>' -f (E $it.pre))
    A ('    <tr><td class="k">예외 처리</td><td>{0}</td></tr>' -f (E $it.exc))
    $sc=@(); foreach($s in $it.screens){ $nm=$screen[$s]; if($nm){ $sc+=("$s · $nm") } else { $sc+=$s } }
    A ('    <tr><td class="k">연관 화면</td><td>{0}</td></tr>' -f (E ($sc -join ' / ')))
    A '  </table>'
  }
  A '</section>'
  A ''
}
A '<section class="card" id="s99">'
A '  <h2><span class="n">99</span>구현 전 공통 확인사항</h2>'
A '  <div class="sub">모든 기능에 공통으로 적용되며 상세 설계 단계에서 확정한다</div>'
A '  <div class="callout">외부 API 인증·인가, 중복 요청에 대한 멱등성, 비동기 처리 상태, 네트워크 오류 재시도, 민감정보 마스킹, 사용자 동의 및 철회, 데이터 보유·파기 정책은 상세 설계 단계에서 확정해야 한다.</div>'
A '  <p class="note">이 판은 문서 보드 생성기 입력용이다. 검색 · 필터가 필요한 열람에는 maiReport_기능정의서.html을 쓴다.</p>'
A '</section>'
A ''
A '<footer class="note">maiReport 기능정의서 · 내부 참고용</footer>'
A '</div>'
A '</body>'
A '</html>'

[System.IO.File]::WriteAllText($dst,$sb.ToString(),(New-Object System.Text.UTF8Encoding $false))
"generated: $total functions / $($groups.Count) groups"
