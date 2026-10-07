<#
  식이 엑셀 4종을 가장 최신 파일로 SharePoint 폴더에 자동으로 맞춘다.
  내 컴퓨터 outputs\mai-report-policy\식이 의 파일이 정본이다.

  사용:
    powershell -ExecutionPolicy Bypass -File scripts\auto-sync-sharepoint.ps1 -Once    한 번만 확인하고 올림
    powershell -ExecutionPolicy Bypass -File scripts\auto-sync-sharepoint.ps1 -Watch   계속 지켜보다가 바뀌면 올림 (Ctrl+C로 끝)
    -DryRun   무엇을 올릴지 로그로만 보여 주고 실제로는 올리지 않는다
    -Git      올린 뒤 같은 엑셀을 깃허브(메인 저장소와 사이트 저장소)에도 올린다. 엑셀 파일만 커밋한다

  안전장치
    1. 파일이 깨졌거나(zip 오류), 시트 수가 줄었거나, 엑셀이 열어 둔 상태면 올리지 않는다.
    2. 올리기 직전에 SharePoint 쪽 파일의 문장 요약값을 마지막에 올린 값과 비교한다.
       다르면 누가 사이트에서 고친 것이므로 먼저 scripts\.sp-backup\ 에 백업하고 로그에 남긴 뒤 덮어쓴다.
    3. 파일이 멈춘 뒤(두 번 연속 같은 상태)에만 올려서, 저장 중인 파일을 올리지 않는다.
    4. 모든 일은 scripts\auto-sync.log 에 남는다.
#>
[CmdletBinding()]
param([switch]$Once, [switch]$Watch, [switch]$DryRun, [switch]$Git, [int]$IntervalSec = 60)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$repo   = Split-Path -Parent $PSScriptRoot
$src    = Join-Path $repo 'outputs\mai-report-policy\식이'
$conf   = Join-Path $PSScriptRoot 'sharepoint-path.txt'
$state  = Join-Path $PSScriptRoot '.auto-sync-state.json'
$logf   = Join-Path $PSScriptRoot 'auto-sync.log'
$files  = @('maiReport_식이_개발전달_데이터계약_v1.0.0.xlsx','maiReport_식이_참조설정데이터_v1.0.0.xlsx',
            'maiReport_식이_문구세트_의학검수_v1.0.0.xlsx','maiReport_식이_의학근거대조_v1.0.0.xlsx')

function Log([string]$m){ $line=('{0:yyyy-MM-dd HH:mm:ss}  {1}' -f (Get-Date),$m); Write-Host $line; Add-Content -Path $logf -Value $line -Encoding UTF8 }

# 엑셀 문서의 문장 요약값. 사이트가 파일을 다시 저장해도 문장이 같으면 같은 값이 나온다.
function Get-Digest([string]$path){
  $fs=[System.IO.File]::Open($path,'Open','Read','ReadWrite')
  try{
    $zip=New-Object System.IO.Compression.ZipArchive($fs,'Read')
    $wbE=$zip.GetEntry('xl/workbook.xml'); if(-not $wbE){ throw 'workbook.xml 없음' }
    $sr=New-Object IO.StreamReader($wbE.Open()); $wb=$sr.ReadToEnd(); $sr.Close()
    $sheets=([regex]::Matches($wb,'<sheet ')).Count
    $set=New-Object 'System.Collections.Generic.SortedSet[string]' ([StringComparer]::Ordinal)
    $e=$zip.GetEntry('xl/sharedStrings.xml')
    if($e){ $r=New-Object IO.StreamReader($e.Open()); $sst=$r.ReadToEnd(); $r.Close()
      foreach($m in [regex]::Matches($sst,'<si>([\s\S]*?)</si>')){ $t=''; foreach($x in [regex]::Matches($m.Groups[1].Value,'<t[^>]*>([^<]*)</t>')){ $t+=$x.Groups[1].Value }; [void]$set.Add($t) } }
    $sha=[System.Security.Cryptography.SHA256]::Create()
    $hash=([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes(($set -join "`n"))))).Replace('-','').Substring(0,20)
    $zip.Dispose(); return [pscustomobject]@{Sheets=$sheets;Strings=$set.Count;Hash=$hash}
  } finally { $fs.Dispose() }
}
function Get-FileSha([string]$p){ (Get-FileHash -Path $p -Algorithm SHA256).Hash }

function Resolve-Destination {
  if(Test-Path $conf){ $d=(Get-Content $conf -Raw -Encoding UTF8).Trim(); if($d -and (Test-Path $d)){ return $d } }
  throw 'SharePoint 동기화 폴더를 찾지 못했습니다. scripts\sync-to-sharepoint.ps1 을 한 번 실행해 폴더를 기억시키세요.'
}

$st=@{}
if(Test-Path $state){ try{ (Get-Content $state -Raw -Encoding UTF8 | ConvertFrom-Json).PSObject.Properties | ForEach-Object { $st[$_.Name]=$_.Value } }catch{ $st=@{} } }
function Save-State { ($st | ConvertTo-Json -Depth 5) | Set-Content $state -Encoding UTF8 }
$pending=@{}   # 파일별로 지난 확인 때 본 해시 (멈췄는지 보려고)

# 올린 엑셀을 깃허브에도 올린다 (엑셀 파일만 커밋. 다른 변경은 건드리지 않는다)
$siteRepo = Join-Path $repo '.tmp_artifact\rsna-deploy'
$siteMap  = @{ 'maiReport_식이_개발전달_데이터계약_v1.0.0.xlsx'='files\diet-data-contract-v1.0.1.xlsx'; 'maiReport_식이_참조설정데이터_v1.0.0.xlsx'='files\diet-reference-config-v1.0.0.xlsx' }
function Invoke-Git([string[]]$names){
  # 메인 저장소
  try{
    $paths=@(); foreach($n in $names){ $paths+=("outputs/mai-report-policy/식이/"+$n) }
    & git -C $repo add -- $paths 2>$null | Out-Null
    & git -C $repo diff --cached --quiet -- $paths 2>$null
    if($LASTEXITCODE -ne 0){
      & git -C $repo commit -m ("엑셀 자동 동기화: "+($names -join ', ')) --only -- $paths 2>$null | Out-Null
      & git -C $repo push 2>$null | Out-Null
      if($LASTEXITCODE -eq 0){ Log("깃허브  메인 저장소에 올림: "+($names -join ', ')) } else { Log("주의  메인 저장소 푸시 실패 — 다른 변경과 겹쳤을 수 있음. 직접 확인 필요") }
    } else { Log("깃허브  메인 저장소는 이미 같은 내용") }
  }catch{ Log("오류  메인 저장소 처리 실패: $($_.Exception.Message)") }
  # 사이트 저장소 (엑셀 2개)
  try{
    if(Test-Path $siteRepo){
      $changed=@(); foreach($n in $names){ if($siteMap.ContainsKey($n)){ Copy-Item (Join-Path $src $n) (Join-Path $siteRepo $siteMap[$n]) -Force; $changed+=($siteMap[$n].Replace([string][char]92,'/')) } }
      if($changed.Count){
        & git -C $siteRepo pull --rebase --autostash 2>$null | Out-Null
        & git -C $siteRepo add -- $changed 2>$null | Out-Null
        & git -C $siteRepo diff --cached --quiet -- $changed 2>$null
        if($LASTEXITCODE -ne 0){
          & git -C $siteRepo commit -m ("엑셀 자동 동기화: "+($changed -join ', ')) --only -- $changed 2>$null | Out-Null
          & git -C $siteRepo push 2>$null | Out-Null
          if($LASTEXITCODE -eq 0){ Log("깃허브  사이트 저장소에 올림: "+($changed -join ', ')) } else { Log("주의  사이트 저장소 푸시 실패 — 직접 확인 필요") }
        } else { Log("깃허브  사이트 저장소는 이미 같은 내용") }
      }
    }
  }catch{ Log("오류  사이트 저장소 처리 실패: $($_.Exception.Message)") }
}

function Invoke-Pass {
  $dest=Resolve-Destination
  $uploaded=@()
  foreach($name in $files){
    $from=Join-Path $src $name; $to=Join-Path $dest $name
    if(-not (Test-Path $from)){ continue }
    $lock=Join-Path $src ('~$'+$name)
    if(Test-Path $lock){ continue }                       # 엑셀이 열어 둔 파일
    try{ $sha=Get-FileSha $from }catch{ continue }        # 저장 중이라 못 읽음
    $known=$st[$name]
    if($known -and $known.localSha -eq $sha){ $pending.Remove($name); continue }   # 이미 올린 상태
    if($pending[$name] -ne $sha){ $pending[$name]=$sha; continue }                  # 처음 본 변화: 한 번 더 지켜봄
    # 여기까지 오면 바뀐 파일이 멈춘 상태
    try{ $dg=Get-Digest $from }catch{ Log("보류  $name  파일을 읽을 수 없음: $($_.Exception.Message)"); continue }
    if($known -and $dg.Sheets -lt ([int]$known.sheets - 2)){ Log("보류  $name  시트 수가 $($known.sheets)개에서 $($dg.Sheets)개로 줄었음 — 깨진 파일일 수 있어 올리지 않음"); continue }
    if($dg.Strings -lt 50){ Log("보류  $name  문장이 너무 적음($($dg.Strings)) — 올리지 않음"); continue }
    # 사이트 쪽을 누가 고쳤는지 확인
    if(Test-Path $to){
      try{ $cd=Get-Digest $to
        if($known -and $cd.Hash -ne $known.digest -and $cd.Hash -ne $dg.Hash){
          $bk=Join-Path $PSScriptRoot ('.sp-backup\'+(Get-Date -Format 'yyyyMMdd-HHmmss')); New-Item -ItemType Directory -Force $bk | Out-Null
          Copy-Item $to (Join-Path $bk $name) -Force
          Log("주의  $name  사이트의 파일이 마지막에 올린 것과 문장이 다름 — 누가 사이트에서 고친 것으로 보임. 백업: $bk")
        } }catch{ Log("참고  $name  사이트 파일을 읽지 못함($($_.Exception.Message)) — 그대로 덮어씀") }
    }
    if($DryRun){ Log("예행  $name  올릴 예정(지금은 올리지 않음)") } else {
      Copy-Item $from $to -Force
      $st[$name]=[pscustomobject]@{localSha=$sha;digest=$dg.Hash;sheets=$dg.Sheets;strings=$dg.Strings;at=(Get-Date -Format s)}
      Save-State; $pending.Remove($name)
      Log("올림  $name  (시트 $($dg.Sheets) · 문장 $($dg.Strings) · 요약 $($dg.Hash))")
      $uploaded+=$name
    }
  }
  if($Git -and -not $DryRun -and $uploaded.Count){ Invoke-Git $uploaded }
}

if(-not ($Once -or $Watch)){ Write-Host '-Once 또는 -Watch 를 지정하세요.'; exit 1 }
if($Once){ Invoke-Pass; Invoke-Pass; Log('한 번 확인 끝'); exit 0 }   # 두 번 돌려 "멈춘 상태"를 확인
Log("자동 동기화 시작 — ${IntervalSec}초마다 확인")
while($true){ try{ Invoke-Pass }catch{ Log("오류  $($_.Exception.Message)") }; Start-Sleep -Seconds $IntervalSec }
