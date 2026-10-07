# QA 에이전트 실행기 (Windows). Node가 PATH에 없어도 설치 위치를 찾아 실행한다.
# 사용: powershell -NoProfile -ExecutionPolicy Bypass -File qa-agent\qa.ps1 run qa-agent\plans\식이.qa-plan.json
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$OutputEncoding = [Text.Encoding]::UTF8

$node = $env:QA_NODE
if (-not $node) { $cmd = Get-Command node -ErrorAction SilentlyContinue; if ($cmd) { $node = $cmd.Source } }
if (-not $node) {
  $candidates = @(
    "$env:ProgramFiles\nodejs\node.exe",
    "$env:LOCALAPPDATA\Programs\nodejs\node.exe",
    "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
  )
  $node = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $node) {
  Write-Host "Node.js(20 이상)를 찾지 못했습니다. https://nodejs.org 에서 LTS를 설치하거나 QA_NODE 환경변수에 node.exe 경로를 넣어 주세요."
  exit 2
}
& $node (Join-Path $PSScriptRoot 'bin\qa.mjs') @args
exit $LASTEXITCODE