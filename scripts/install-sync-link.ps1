<#
  관리자 페이지의 「SharePoint 엑셀 반영 실행」 버튼이 이 PC에서 반영 프로그램을 열 수 있게
  maireport-sync:// 주소를 이 사용자 계정에만 등록한다(관리자 권한 필요 없음).

  설치:   쉐어포인트_실행링크_설치.bat 더블클릭
  지우기: powershell -ExecutionPolicy Bypass -File scripts\install-sync-link.ps1 -Remove
  확인만: ... -WhatIf

  보안: 주소 뒤에 붙는 값은 프로그램에 넘기지 않는다. 버튼은 항상 같은 실행 파일만 연다.
#>
param([switch]$Remove, [switch]$WhatIf)
$ErrorActionPreference = 'Stop'
$key = 'HKCU:\Software\Classes\maireport-sync'
$bat = Join-Path $PSScriptRoot '쉐어포인트_엑셀_반영.bat'
$cmd = '"{0}\System32\cmd.exe" /c start "SharePoint 반영" "{1}"' -f $env:SystemRoot, $bat

if ($Remove) {
  if (Test-Path $key) { if (-not $WhatIf) { Remove-Item $key -Recurse -Force }; Write-Host "지웠습니다: maireport-sync://" -ForegroundColor Green }
  else { Write-Host "등록된 것이 없습니다" }
  exit 0
}
if (-not (Test-Path $bat)) { Write-Host "실행 파일이 없습니다: $bat" -ForegroundColor Red; exit 1 }
Write-Host "등록할 주소: maireport-sync://run"
Write-Host "여는 파일:   $bat"
if ($WhatIf) { Write-Host "(확인만 했습니다. 바꾸지 않음)"; Write-Host "명령: $cmd"; exit 0 }
New-Item -Path $key -Force | Out-Null
Set-ItemProperty -Path $key -Name '(default)' -Value 'URL:maiReport SharePoint 엑셀 반영'
Set-ItemProperty -Path $key -Name 'URL Protocol' -Value ''
New-Item -Path "$key\shell\open\command" -Force | Out-Null
Set-ItemProperty -Path "$key\shell\open\command" -Name '(default)' -Value $cmd
Write-Host ""
Write-Host "등록했습니다. 관리자 페이지의 실행 버튼을 누르면 브라우저가 열기를 묻고, 허용하면 반영 프로그램이 뜹니다." -ForegroundColor Green
Write-Host "저장소 폴더를 옮기면 이 설치를 다시 실행하세요."
