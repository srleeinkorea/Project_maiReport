<#
  식이 엑셀을 SharePoint 파일에 "바뀐 칸만" 반영한다. 누가 파일을 열어 두고 있어도 된다.

  방식
    - PC용 엑셀로 SharePoint 파일을 주소로 연다(공동 편집으로 들어감 → 잠금에 막히지 않음).
    - 세 판을 비교한다.
        기준본  scripts\.sp-live\base\<이름>.xlsx  마지막으로 맞춘 판
        로컬    sharepoint-live-sync.json 의 local
        웹      sharepoint-live-sync.json 의 url
    - 로컬에서 바뀐 칸 · 새 행 · 지운 행만 웹 파일에 반영하고, 바뀐 칸은 빨간 글자로 표시한다.
    - 웹에서만 바뀐 곳은 덮어쓰지 않는다. 목록으로 알려 주고, -Pull 이면 로컬로 가져온다.
    - 같은 칸을 양쪽이 다르게 바꿨으면 건드리지 않고 "충돌"로 알린다.

  실행
    더블클릭: scripts\쉐어포인트_엑셀_반영.bat  (미리보기 → 확인 → 반영)
    powershell -ExecutionPolicy Bypass -File scripts\sharepoint-live-sync.ps1            미리보기만
    ... -Apply              웹에 반영
    ... -Pull               웹에서만 바뀐 곳을 로컬로 가져옴
    ... -Only 데이터계약     파일 하나만
    ... -TargetPath x.xlsx  웹 대신 이 파일을 대상으로(시험용, -Only 와 함께)
    ... -LocalPath / -BasePath  로컬 · 기준본 대신 이 파일(시험용)
    ... -NoRed              빨간 글자 표시 안 함
#>
param(
  [switch]$Apply,
  [switch]$Pull,
  [switch]$Interactive,
  [string]$Only,
  [string]$TargetPath,
  [string]$BasePath,
  [string]$LocalPath,
  [switch]$NoRed,
  [int]$Show = 15
)

$ErrorActionPreference = 'Stop'
$repo    = Split-Path $PSScriptRoot -Parent
$confP   = Join-Path $PSScriptRoot 'sharepoint-live-sync.json'
$baseDir = Join-Path $PSScriptRoot '.sp-live\base'
$logP    = Join-Path $PSScriptRoot 'live-sync.log'
$REDCOLOR = 255   # Excel BGR: 빨강
New-Item -ItemType Directory -Force $baseDir | Out-Null

function Log([string]$m) {
  $line = "{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
  Add-Content -Path $logP -Value $line -Encoding UTF8
}
function Say([string]$m, [string]$c = 'Gray') { Write-Host $m -ForegroundColor $c }

# ── 값 비교용 표기 ───────────────────────────────────────────
function Tag($v) {
  if ($null -eq $v) { return '' }
  if ($v -is [string]) { if ($v -eq '') { return '' } return 's:' + $v }
  if ($v -is [double]) { return 'n:' + $v.ToString('R', [Globalization.CultureInfo]::InvariantCulture) }
  if ($v -is [bool])   { return 'b:' + $v }
  return 'o:' + [string]$v
}

# 시트 전체 값을 한 번에 읽는다
function Read-GridOnce($ws) {
  $ur   = $ws.UsedRange
  $rows = $ur.Row + $ur.Rows.Count - 1
  $cols = $ur.Column + $ur.Columns.Count - 1
  $g = [ordered]@{ Rows = 0; Cols = $cols; V = $null; Keys = $null }
  if ($rows -lt 1 -or $cols -lt 1) { $g.Keys = [string[]]@(); return $g }
  $raw = $ws.Range($ws.Cells.Item(1, 1), $ws.Cells.Item($rows, $cols)).Value2
  $V = New-Object 'object[,]' ($rows + 1), ($cols + 1)
  if ($raw -is [Array]) {
    for ($r = 1; $r -le $rows; $r++) { for ($c = 1; $c -le $cols; $c++) { $V[$r, $c] = $raw[$r, $c] } }
  } else { $V[1, 1] = $raw }
  $keys = New-Object 'string[]' $rows
  for ($r = 1; $r -le $rows; $r++) {
    $sb = New-Object Text.StringBuilder
    for ($c = 1; $c -le $cols; $c++) { [void]$sb.Append((Tag $V[$r, $c])).Append([char]31) }
    $keys[$r - 1] = $sb.ToString().TrimEnd([char]31)
  }
  # 끝쪽 빈 행은 버린다
  $n = $rows
  while ($n -gt 0 -and ($keys[$n - 1] -replace [char]31, '') -eq '') { $n-- }
  $g.Rows = $n; $g.V = $V
  $g.Keys = if ($n -gt 0) { [string[]]$keys[0..($n - 1)] } else { [string[]]@() }
  return $g
}
# 엑셀이 파일을 연 직후 다시 계산하는 동안에는 값이 비어 읽힐 수 있다 → 준비될 때까지 기다린다
function Wait-Ready {
  for ($i = 0; $i -lt 300; $i++) {
    try { if ($xl.Ready -and $xl.CalculationState -eq 0) { return } } catch {}
    Start-Sleep -Milliseconds 100
  }
}
# 같은 결과가 두 번 연속 나올 때까지 읽는다(빈 값으로 잘못 읽는 일 방지)
function Get-Grid($ws) {
  $prev = $null
  for ($i = 0; $i -lt 6; $i++) {
    Wait-Ready
    $g = Read-GridOnce $ws
    $sig = "$($g.Rows)x$($g.Cols)|" + ($g.Keys -join [char]30)
    if ($null -ne $prev -and $sig -eq $prev) { return $g }
    $prev = $sig
  }
  throw "시트 [$($ws.Name)] 값을 안정적으로 읽지 못했습니다(엑셀이 계속 바쁨)"
}
function Get-SheetNames($wb) {
  $prev = $null
  for ($i = 0; $i -lt 6; $i++) {
    Wait-Ready
    $n = [int]$wb.Worksheets.Count
    $names = @(); for ($q = 1; $q -le $n; $q++) { $names += ,([string]$wb.Worksheets.Item($q).Name) }
    $sig = $names -join '|'
    if ($n -gt 0 -and -not ($names -contains '') -and $sig -eq $prev) { return ,$names }
    $prev = $sig
  }
  throw "시트 목록을 안정적으로 읽지 못했습니다: $($wb.FullName)"
}
function Open-Book([string]$path, [bool]$readOnly) {
  Wait-Ready
  $wb = $null
  try { $wb = $xl.Workbooks.Open($path, 0, $readOnly) } catch { Start-Sleep -Milliseconds 500; Wait-Ready; $wb = $xl.Workbooks.Open($path, 0, $readOnly) }
  $leaf = [IO.Path]::GetFileName(($path -replace '/', ''))
  for ($i = 0; $null -eq $wb -and $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    foreach ($w in @($xl.Workbooks)) { if ($w.FullName -eq $path -or $w.Name -eq $leaf) { $wb = $w } }
  }
  if ($null -eq $wb) { throw "파일을 열지 못했습니다: $path" }
  Wait-Ready
  return $wb
}
function Cell($g, [int]$r, [int]$c) {   # r, c 는 1부터
  if ($r -lt 1 -or $r -gt $g.Rows -or $c -gt $g.Cols -or $null -eq $g.V) { return $null }
  return $g.V[$r, $c]
}

# ── 행 단위 비교(LCS) ────────────────────────────────────────
# 반환: Map(a 행 → b 행, 0부터, 없으면 -1), Hunks(@{A0;A1;B0;B1}, 끝은 제외)
function Diff-Rows([string[]]$a, [string[]]$b) {
  $n = $a.Count; $m = $b.Count
  $map = New-Object 'int[]' $n; for ($i = 0; $i -lt $n; $i++) { $map[$i] = -1 }
  $p = 0; while ($p -lt $n -and $p -lt $m -and $a[$p] -eq $b[$p]) { $map[$p] = $p; $p++ }
  $s = 0; while ($s -lt ($n - $p) -and $s -lt ($m - $p) -and $a[$n - 1 - $s] -eq $b[$m - 1 - $s]) { $map[$n - 1 - $s] = $m - 1 - $s; $s++ }
  $an = $n - $p - $s; $bn = $m - $p - $s
  if ($an -gt 0 -and $bn -gt 0) {
    $L = New-Object 'int[,]' ($an + 1), ($bn + 1)
    for ($i = $an - 1; $i -ge 0; $i--) {
      for ($j = $bn - 1; $j -ge 0; $j--) {
        if ($a[$p + $i] -eq $b[$p + $j]) { $L[$i, $j] = $L[($i + 1), ($j + 1)] + 1 }
        elseif ($L[($i + 1), $j] -ge $L[$i, ($j + 1)]) { $L[$i, $j] = $L[($i + 1), $j] }
        else { $L[$i, $j] = $L[$i, ($j + 1)] }
      }
    }
    $i = 0; $j = 0
    while ($i -lt $an -and $j -lt $bn) {
      if ($a[$p + $i] -eq $b[$p + $j]) { $map[$p + $i] = $p + $j; $i++; $j++ }
      elseif ($L[($i + 1), $j] -ge $L[$i, ($j + 1)]) { $i++ } else { $j++ }
    }
  }
  # 맞은 행 사이의 빈틈이 바뀐 덩어리
  $hunks = New-Object Collections.ArrayList
  $pa = -1; $pb = -1
  for ($i = 0; $i -le $n; $i++) {
    if ($i -lt $n -and $map[$i] -lt 0) { continue }
    $nb = if ($i -lt $n) { $map[$i] } else { $m }
    if (($i - $pa - 1) -gt 0 -or ($nb - $pb - 1) -gt 0) {
      [void]$hunks.Add([pscustomobject]@{ A0 = $pa + 1; A1 = $i; B0 = $pb + 1; B1 = $nb })
    }
    $pa = $i; $pb = $nb
  }
  return [pscustomobject]@{ Map = $map; Hunks = $hunks }
}

# ── 바뀐 것 옮기기: base → src 의 변화를 dst 에 적용 ─────────────
# 반환: 바뀐 칸 목록, 충돌 목록
function Apply-Changes($srcWs, $src, $base, $dstWs, $dst, [bool]$doWrite, [bool]$red, [string]$sheet, $srcRedList) {
  $res = [pscustomobject]@{ Cells = New-Object Collections.ArrayList; Rows = New-Object Collections.ArrayList; Conflicts = New-Object Collections.ArrayList; Skipped = New-Object Collections.ArrayList }
  $ours = Diff-Rows $base.Keys $src.Keys
  if ($ours.Hunks.Count -eq 0) { return $res }
  $theirs = Diff-Rows $base.Keys $dst.Keys
  $tmap = $theirs.Map
  # 웹에서도 바뀐 행은, 같은 수만큼 바뀐 덩어리면 자리끼리 짝지어 칸 단위로 비교한다
  $pmap = [int[]]$tmap.Clone()
  # 받는 쪽에만 있는 행(이미 넣은 행 포함). 같은 내용을 두 번 넣지 않기 위해 쓴다
  $matched = New-Object 'Collections.Generic.HashSet[int]'; foreach ($x in $tmap) { if ($x -ge 0) { [void]$matched.Add($x) } }
  $dstOnly = New-Object 'Collections.Generic.HashSet[string]'
  for ($q = 0; $q -lt $dst.Rows; $q++) { if (-not $matched.Contains($q)) { [void]$dstOnly.Add($dst.Keys[$q]) } }
  foreach ($th in $theirs.Hunks) { if (($th.A1 - $th.A0) -eq ($th.B1 - $th.B0)) { for ($q = 0; $q -lt ($th.A1 - $th.A0); $q++) { $pmap[$th.A0 + $q] = $th.B0 + $q } } }
  $cols = [Math]::Max([Math]::Max($src.Cols, $base.Cols), $dst.Cols)
  # 아래쪽 덩어리부터 처리해야 위쪽 행 번호가 안 밀린다
  $hs = @($ours.Hunks) | Sort-Object A0 -Descending
  foreach ($h in $hs) {
    $bl = $h.A1 - $h.A0; $sl = $h.B1 - $h.B0; $k = [Math]::Min($bl, $sl)
    # 1) 새 행 넣기
    if ($sl -gt $bl) {
      $cnt = $sl - $bl
      $before = $h.A0 + $k - 1
      if ($before -ge 0) { $anchor = $tmap[$before]; $at = $anchor + 2 }   # dst 1부터
      elseif ($h.A0 + $k -lt $base.Rows) { $anchor = $tmap[$h.A0 + $k]; $at = $anchor + 1 }
      else { $anchor = 0; $at = 1 }
      $s0 = $h.B0 + $k + 1; $s1 = $s0 + $cnt - 1
      $already = $true; for ($r = $s0; $r -le $s1; $r++) { if (-not $dstOnly.Contains($src.Keys[$r - 1])) { $already = $false } }
      if ($anchor -lt 0 -and -not $already) {
        [void]$res.Conflicts.Add("$sheet  행 넣을 자리(로컬 $($h.B0 + $k + 1)행 위)를 웹에서 찾을 수 없음 — 웹에서 그 근처가 바뀜")
      } else {
        if ($already) { [void]$res.Skipped.Add("$sheet  로컬 $($s0)~$($s1)행은 받는 쪽에 이미 있음 — 건너뜀") } else {
        if ($doWrite) {
          $endsAfter = ($at -gt $dst.Rows)
          if (-not $endsAfter) { [void]$dstWs.Range("$($at):$($at + $cnt - 1)").EntireRow.Insert() }
          [void]$srcWs.Range("$($s0):$($s1)").EntireRow.Copy($dstWs.Range("$($at):$($at + $cnt - 1)").EntireRow)
          if ($red) {
            for ($r = 0; $r -lt $cnt; $r++) { for ($c = 1; $c -le $src.Cols; $c++) {
              if ((Tag (Cell $src ($s0 + $r) $c)) -ne '') { $dstWs.Cells.Item($at + $r, $c).Font.Color = $REDCOLOR; [void]$srcRedList.Add(@(($s0 + $r), $c)) }
            } }
          }
        }
        for ($r = $s0; $r -le $s1; $r++) { [void]$res.Rows.Add("$sheet  웹 $($at + $r - $s0)행에 새 행 넣음: " + (Preview-Row $src $r)) }
        }
      }
    }
    # 2) 행 지우기
    if ($bl -gt $sl) {
      for ($i = $h.A0 + $bl - 1; $i -ge $h.A0 + $k; $i--) {
        $t = $tmap[$i]
        if ($t -lt 0) {
          if ($pmap[$i] -ge 0) { [void]$res.Conflicts.Add("$sheet  로컬에서 지운 행(기준 $($i + 1)행)을 웹에서는 고쳐 두어 지우지 않음") }
          else { [void]$res.Skipped.Add("$sheet  기준 $($i + 1)행은 받는 쪽에서 이미 지워짐 — 건너뜀") }
          continue
        }
        if ($doWrite) { [void]$dstWs.Rows.Item($t + 1).EntireRow.Delete() }
        [void]$res.Rows.Add("$sheet  웹 $($t + 1)행 지움: " + (Preview-Row $base ($i + 1)))
      }
    }
    # 3) 같은 자리의 행은 칸 단위로 고침
    for ($i = 0; $i -lt $k; $i++) {
      $br = $h.A0 + $i; $sr = $h.B0 + $i; $t = $pmap[$br]
      if ($t -lt 0 -and $dstOnly.Contains($src.Keys[$sr])) { [void]$res.Skipped.Add("$sheet  로컬 $($sr + 1)행은 받는 쪽에 이미 같은 내용이 있음 — 건너뜀"); continue }
      if ($t -lt 0) {
        [void]$res.Conflicts.Add("$sheet  로컬 $($sr + 1)행: 웹에서도 같은 행이 바뀌어 건드리지 않음 — " + (Preview-Row $src ($sr + 1)))
        continue
      }
      for ($c = 1; $c -le $cols; $c++) {
        $sv = Tag (Cell $src ($sr + 1) $c); $bv = Tag (Cell $base ($br + 1) $c); $tv = Tag (Cell $dst ($t + 1) $c)
        if ($sv -eq $bv -or $tv -eq $sv) { continue }
        if ($tv -ne $bv) { [void]$res.Conflicts.Add("$sheet  $(ColName $c)$($t + 1): 웹과 로컬이 서로 다르게 바꿈 — 웹 「$(Short $tv)」 / 로컬 「$(Short $sv)」"); continue }
        if ($doWrite) {
          [void]$srcWs.Cells.Item($sr + 1, $c).Copy($dstWs.Cells.Item($t + 1, $c))
          if ($red) { $dstWs.Cells.Item($t + 1, $c).Font.Color = $REDCOLOR; [void]$srcRedList.Add(@(($sr + 1), $c)) }
        }
        [void]$res.Cells.Add("$sheet  $(ColName $c)$($t + 1): 「$(Short $bv)」 → 「$(Short $sv)」")
      }
    }
  }
  return $res
}
function ColName([int]$c) { $s = ''; while ($c -gt 0) { $m = ($c - 1) % 26; $s = [char](65 + $m) + $s; $c = [int](($c - $m) / 26) }; return $s }
function Short([string]$t) { $t = $t -replace '^[snbo]:', ''; if ($t.Length -gt 40) { $t.Substring(0, 40) + '…' } else { $t } }
function Preview-Row($g, [int]$r) { $p = @(); for ($c = 1; $c -le [Math]::Min($g.Cols, 4); $c++) { $p += (Short (Tag (Cell $g $r $c))) }; ($p | Where-Object { $_ }) -join ' | ' }

# ── 실행 ────────────────────────────────────────────────────
$conf = Get-Content $confP -Raw -Encoding UTF8 | ConvertFrom-Json
$targets = @($conf.files)
if ($Only) { $targets = @($targets | Where-Object { $_.name -eq $Only }) }
if (-not $targets) { Say "설정에 그런 파일이 없습니다: $Only" Red; exit 2 }
if ($TargetPath -and $targets.Count -ne 1) { Say "-TargetPath 는 -Only 와 함께 씁니다" Red; exit 2 }

$mode = if ($Pull) { '웹 → 로컬 가져오기' } elseif ($Apply) { '로컬 → 웹 반영' } else { '미리보기(아무것도 바꾸지 않음)' }
Say ("== SharePoint 엑셀 실시간 반영 · " + $mode) Cyan
Log "start mode=$mode only=$Only target=$TargetPath"

$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false; $xl.DisplayAlerts = $false; $xl.AskToUpdateLinks = $false
$summary = @(); $exit = 0
try {
  foreach ($f in $targets) {
    $localP = if ($LocalPath) { $LocalPath } else { Join-Path $repo $f.local }
    $url    = if ($TargetPath) { $TargetPath } else { $f.url }
    $baseP  = if ($BasePath) { $BasePath } else { Join-Path $baseDir ($f.name + '.xlsx') }
    Say ""
    Say ("■ " + $f.name) White
    Say ("  로컬  " + $f.local)
    Say ("  웹    " + $url)
    if (-not (Test-Path $localP)) { Say "  로컬 파일이 없습니다" Red; $exit = 2; continue }

    # 로컬 파일은 SharePoint 파일과 이름이 같아 함께 열 수 없다 → 임시 이름 사본으로 열고, 저장할 때만 되돌려 쓴다
    $localWork = Join-Path $env:TEMP ('sp-live-local-' + [guid]::NewGuid().ToString('N') + '.xlsx')
    Copy-Item -LiteralPath $localP -Destination $localWork -Force
    $localDirty = $false
    $wbL = Open-Book $localWork $false
    $wbT = Open-Book $url $false
    if ($wbT.ReadOnly -ne $false) { Say "  웹 파일이 읽기 전용으로 열렸습니다(편집 권한·로그인 확인 필요). 건너뜀" Red; $wbT.Close($false); $wbL.Close($false); $exit = 2; continue }
    $firstRun = -not (Test-Path $baseP)
    if ($firstRun) {
      Say "  기준본이 없어 이번에는 웹 파일을 기준으로 삼습니다(로컬과 다른 곳은 모두 '로컬 변경'으로 봄)" Yellow
      $tmpBase = Join-Path $env:TEMP ("sp-live-base-" + [guid]::NewGuid().ToString('N') + '.xlsx')
      $wbT.SaveCopyAs($tmpBase); $wbB = Open-Book $tmpBase $true
    } else { $wbB = Open-Book $baseP $true }

    # 로컬 → 웹 이면 src=로컬, dst=웹 / 가져오기면 반대
    if ($Pull) { $wbS = $wbT; $wbD = $wbL } else { $wbS = $wbL; $wbD = $wbT }
    $doWrite = [bool]($Apply -or $Pull)
    $allCells = 0; $allRows = 0; $allConf = 0; $webOnly = New-Object Collections.ArrayList
    $orderS = Get-SheetNames $wbS; $orderD = Get-SheetNames $wbD; $nS = $orderS.Count; $done = 0
    Log ("  sheets src=" + ($orderS -join '|') + " dst=" + ($orderD -join '|'))
    if (($orderS -join '|') -ne ($orderD -join '|')) { Say "  ! 시트 이름·순서가 다릅니다 — 직접 맞춰 주세요" Yellow; Say ("    보낼 쪽: " + ($orderS -join ', ')); Say ("    받을 쪽: " + ($orderD -join ', ')) }
    for ($q = 1; $q -le $nS; $q++) {
      $ws = $wbS.Worksheets.Item($orderS[$q - 1])
      $name = $ws.Name
      $wsD = $null; try { $wsD = $wbD.Worksheets.Item($name) } catch {}
      $wsB = $null; try { $wsB = $wbB.Worksheets.Item($name) } catch {}
      if (-not $wsD) { Say "  ! [$name] 받을 쪽에 시트가 없음 — 건너뜀" Yellow; continue }
      if (-not $wsB) { Say "  ! [$name] 기준본에 시트가 없음 — 건너뜀" Yellow; continue }
      $gS = Get-Grid $ws; $gB = Get-Grid $wsB; $gD = Get-Grid $wsD
      $done++
      $redList = New-Object Collections.ArrayList
      $r = Apply-Changes $ws $gS $gB $wsD $gD $doWrite (-not $NoRed -and -not $Pull) $name $redList
      if (-not $Pull -and $doWrite -and -not $NoRed -and $redList.Count) { foreach ($rc in $redList) { $ws.Cells.Item($rc[0], $rc[1]).Font.Color = $REDCOLOR } }
      foreach ($x in $r.Cells) { if ($allCells -lt $Show) { Say ("  · " + $x) Green }; $allCells++ }
      foreach ($x in $r.Rows) { if ($allRows -lt $Show) { Say ("  + " + $x) Green }; $allRows++ }
      foreach ($x in $r.Conflicts) { Say ("  ! 충돌 " + $x) Red; $allConf++ }
      foreach ($x in $r.Skipped) { Say ("  = " + $x) DarkGray }
      foreach ($x in $r.Cells + $r.Rows + $r.Conflicts) { Log ("  " + $f.name + "  " + $x) }
      # 받을 쪽에서만 바뀐 곳(웹에서 다른 사람이 고친 것 등)
      $back = Diff-Rows $gB.Keys $gD.Keys
      foreach ($h in $back.Hunks) {
        for ($i = $h.B0; $i -lt $h.B1; $i++) { [void]$webOnly.Add("$name  $($i + 1)행: " + (Preview-Row $gD ($i + 1))) }
        for ($i = $h.A0; $i -lt $h.A1; $i++) { if (($h.B1 - $h.B0) -lt ($h.A1 - $h.A0)) { [void]$webOnly.Add("$name  기준 $($i + 1)행이 없어짐: " + (Preview-Row $gB ($i + 1))) } }
      }
    }
    if ($allCells -gt $Show -or $allRows -gt $Show) { Say ("  … 전체는 " + $logP) }
    $who = if ($Pull) { '로컬' } else { '웹' }
    $otherSide = if ($Pull) { '로컬에서만' } else { '웹에서만' }
    Say ("  {0}에 반영할 것: 칸 {1} · 행 {2} · 충돌 {3}" -f $who, $allCells, $allRows, $allConf) Cyan
    if ($webOnly.Count) {
      Say ("  {0} 바뀐 곳 {1}줄 — 덮어쓰지 않았습니다" -f $otherSide, $webOnly.Count) Yellow
      $webOnly | Select-Object -First $Show | ForEach-Object { Say ("    " + $_) Yellow }
      if (-not $Pull) { Say "    → 로컬로 가져오려면: 실행 파일에서 '가져오기' 또는 -Pull" Yellow }
      $webOnly | ForEach-Object { Log ("  " + $f.name + "  side-only " + $_) }
    }
    if ($doWrite -and ($allCells + $allRows) -gt 0) {
      $wbD.Save(); if ($Pull) { $localDirty = $true } elseif (-not $NoRed) { $wbL.Save(); $localDirty = $true }
      Say "  저장했습니다" Green
    }
    # 기준본 갱신: 반영이 끝났으면 지금 로컬(가져오기면 웹)을 새 기준으로
    if ($doWrite -and $done -eq 0) { Say "  비교한 시트가 0개라 기준본을 갱신하지 않습니다" Red; $exit = 1 }
    elseif ($doWrite -and $allConf -eq 0) {
      if ($Pull) { $wbT.SaveCopyAs($baseP) } else { $wbL.SaveCopyAs($baseP) }
      Say "  기준본을 갱신했습니다" DarkGray
    } elseif ($doWrite) { Say "  충돌이 있어 기준본은 그대로 둡니다. 충돌을 정리한 뒤 다시 실행하세요" Yellow }
    $summary += [pscustomobject]@{ 파일 = $f.name; 시트 = $done; 칸 = $allCells; 행 = $allRows; 충돌 = $allConf; 상대쪽만 = $webOnly.Count }
    $wbB.Close($false); $wbT.Close($false); $wbL.Close($false)
    if ($localDirty) {
      try { Copy-Item -LiteralPath $localWork -Destination $localP -Force; Say "  로컬 파일에 저장했습니다" Green }
      catch { Say ("  로컬 파일이 열려 있어 저장하지 못했습니다. 엑셀에서 닫고 다시 실행하세요: " + $localP) Red; $exit = 1 }
    }
    Remove-Item -LiteralPath $localWork -ErrorAction SilentlyContinue
    if ($firstRun -and $tmpBase) { Remove-Item $tmpBase -ErrorAction SilentlyContinue }
  }
} catch {
  Say ("오류: " + $_.Exception.Message + " (" + $_.InvocationInfo.ScriptLineNumber + "행)") Red
  Log ("error " + $_.Exception.Message); $exit = 1
} finally {
  foreach ($wb in @($xl.Workbooks)) { try { $wb.Close($false) } catch {} }
  $xl.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($xl)
  $xl = $null; [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}
Say ""
$summary | Format-Table -AutoSize | Out-String | Write-Host
Log "end exit=$exit"
exit $exit
