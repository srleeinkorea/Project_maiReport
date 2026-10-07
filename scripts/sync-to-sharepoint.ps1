<#
  식이 엑셀 2종을 회사 SharePoint(Teams 사이트)로 올린다.

  준비 (한 번만):
    1) 브라우저에서 팀 사이트 문서 라이브러리를 열고 [동기화]를 누른다
       https://maihub.sharepoint.com/sites/msteams_b7ec7d
    2) 탐색기에 폴더가 생길 때까지 기다린다
    3) 이 스크립트를 실행하면 그 폴더를 찾아 기억해 둔다

  실행:
    powershell -ExecutionPolicy Bypass -File scripts\sync-to-sharepoint.ps1
    -WhatIf  무엇을 올릴지만 보여 준다
    -Force   사이트 쪽이 더 최근이어도 덮어쓴다
#>
[CmdletBinding(SupportsShouldProcess=$true)]
param([string]$Destination, [switch]$Force)

$ErrorActionPreference = 'Stop'
$repo  = Split-Path $PSScriptRoot -Parent
$src   = Join-Path $repo 'outputs\mai-report-policy\식이'
$conf  = Join-Path $PSScriptRoot 'sharepoint-path.txt'
$SITE  = 'msteams_b7ec7d'
$files = @(
  'maiReport_식이_개발전달_데이터계약_v1.0.0.xlsx',
  'maiReport_식이_참조설정데이터_v1.0.0.xlsx',
  'maiReport_식이_문구세트_의학검수_v1.0.0.xlsx',
  'maiReport_식이_의학근거대조_v1.0.0.xlsx'
)

function Get-SyncedLibraries {
  $key = 'HKCU:\Software\SyncEngines\Providers\OneDrive'
  if (-not (Test-Path $key)) { return @() }
  Get-ChildItem $key | ForEach-Object {
    $i = Get-ItemProperty $_.PSPath
    if ($i.UrlNamespace -and $i.MountPoint) {
      [pscustomobject]@{ Url = [string]$i.UrlNamespace; Path = [string]$i.MountPoint }
    }
  }
}

if (-not $Destination -and (Test-Path $conf)) {
  $saved = (Get-Content $conf -Raw -Encoding UTF8).Trim()
  if ($saved -and (Test-Path $saved)) { $Destination = $saved }
}
if (-not $Destination) {
  $libs = Get-SyncedLibraries
  $hit  = $libs | Where-Object { $_.Url -like "*$SITE*" } | Select-Object -First 1
  if ($hit) {
    $Destination = $hit.Path
    # 파일이 라이브러리 최상위가 아니라 하위 폴더에 있으면 그쪽을 쓴다
    $found = Get-ChildItem $Destination -Recurse -Filter $files[0] -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { $Destination = $found.DirectoryName }
  }
  else {
    Write-Host "팀 사이트가 아직 동기화되지 않았습니다." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  1) 브라우저에서 아래 주소를 열고"
    Write-Host "     https://maihub.sharepoint.com/sites/$SITE"
    Write-Host "  2) 파일이 있는 문서 라이브러리로 들어가 위쪽 [동기화]를 누르세요."
    Write-Host "  3) 탐색기에 폴더가 생기면 이 스크립트를 다시 실행하세요."
    Write-Host ""
    if ($libs) {
      Write-Host "지금 동기화된 것:"
      $libs | ForEach-Object { Write-Host ("  {0}`n     -> {1}" -f $_.Url, $_.Path) }
    } else { Write-Host "지금 동기화된 라이브러리가 없습니다." }
    exit 1
  }
}
if (-not (Test-Path $Destination)) { Write-Host "폴더가 없습니다: $Destination" -ForegroundColor Red; exit 1 }
Set-Content -Path $conf -Value $Destination -Encoding UTF8
Write-Host "보낼 곳: $Destination"
Write-Host ""

function Get-Sha([string]$p){ (Get-FileHash -Path $p -Algorithm SHA256).Hash }

# SharePoint는 올라간 xlsx에 자체 메타데이터를 붙여 바이트가 달라진다.
# 그래서 사이트 파일과 비교하지 않고, 마지막으로 보낸 "내 파일"의 해시를 기억해 둔다.
$stateFile = Join-Path $PSScriptRoot '.sync-state.json'
$state = @{}
if (Test-Path $stateFile) {
  try { (Get-Content $stateFile -Raw -Encoding UTF8 | ConvertFrom-Json).PSObject.Properties |
          ForEach-Object { $state[$_.Name] = [string]$_.Value } } catch { $state = @{} }
}

$sent = 0; $same = 0; $held = 0
foreach ($name in $files) {
  $from = Join-Path $src $name
  if (-not (Test-Path $from)) { Write-Host "  없음(건너뜀)  $name" -ForegroundColor Yellow; continue }

  $to   = Join-Path $Destination $name
  $new  = -not (Test-Path $to)
  $hash = Get-Sha $from

  if (-not $new -and $state[$name] -eq $hash -and -not $Force) {
    Write-Host "  그대로  $name"; $same++; continue
  }
  if (-not $new -and ((Get-Item $to).LastWriteTime -gt (Get-Item $from).LastWriteTime) -and -not $Force) {
    Write-Host "  보류    $name" -ForegroundColor Red
    Write-Host ("          사이트 {0} 가 내 파일 {1} 보다 최근입니다" -f (Get-Item $to).LastWriteTime, (Get-Item $from).LastWriteTime)
    Write-Host  "          사이트에서 누가 고쳤을 수 있습니다. 확인 뒤 -Force 로 다시 실행하세요."
    $held++; continue
  }
  if ($PSCmdlet.ShouldProcess($name, '올리기')) {
    # 덮어쓰기 전에 사이트 쪽 파일을 백업해 둔다. 누가 사이트에서 고친 내용을 되살릴 수 있게.
    if (-not $new) {
      $bk = Join-Path $PSScriptRoot ('.sp-backup\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
      New-Item -ItemType Directory -Force $bk | Out-Null
      Copy-Item $to (Join-Path $bk $name) -Force
    }
    Copy-Item $from $to -Force
    $state[$name] = $hash
    Write-Host ("  {0}  {1}" -f $(if($new){'새로 올림'}else{'덮어씀  '}), $name) -ForegroundColor Green
    $sent++
  }
}
if ($sent -and -not $WhatIfPreference) {
  ($state.GetEnumerator() | ForEach-Object { [pscustomobject]@{k=$_.Key;v=$_.Value} } |
    ForEach-Object -Begin { $o=[ordered]@{} } -Process { $o[$_.k]=$_.v } -End { [pscustomobject]$o }) |
    ConvertTo-Json | Set-Content $stateFile -Encoding UTF8
}
Write-Host ""
Write-Host "올림 $sent · 그대로 $same · 보류 $held"
if ($sent) { Write-Host "OneDrive가 잠시 뒤 사이트에 반영합니다. 작업 표시줄 구름 아이콘에서 진행 상태를 볼 수 있습니다." }
