$ErrorActionPreference = 'Stop'
# 배포본 만들기 — 시연 프로토타입 한 벌을 그대로 index.html로 내보낸다.
# (버전 비교 탭은 두 화면이 같아진 뒤로 쓰지 않는다)
$sourceDir = Join-Path $PSScriptRoot 'outputs/mai-report-rsna-demo'
$originals = @(Get-ChildItem -LiteralPath $sourceDir -Filter '*v1.0.0.html' -File | Where-Object { $_.Name -notlike 'gpt_*' })
if ($originals.Count -ne 1) { throw 'Expected exactly one original RSNA HTML.' }
$content = [IO.File]::ReadAllText($originals[0].FullName)
if ($content -notmatch '(?i)<!doctype html' -or $content -notmatch '(?i)</html>') { throw "Incomplete HTML: $($originals[0].FullName)" }
$encoding = New-Object System.Text.UTF8Encoding($false)
$outputDir = Join-Path $PSScriptRoot 'outputs/rsna-github-upload'
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$outputFile = Join-Path $outputDir 'index.html'
[IO.File]::WriteAllText($outputFile, $content, $encoding)
Write-Output $outputFile
