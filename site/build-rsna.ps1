$ErrorActionPreference = 'Stop'
# 배포본 만들기 — 최종 프로토타입(docs/화면/90_기타/maiReport_prototype_v1.0.0.html)을 그대로 prototype.html로 내보낸다.
# 공유 사이트의 「최종 프로토타입」 탭이 이 파일을 읽는다. (옛 RSNA 시연 원본은 site/_archive)
$source = Join-Path $PSScriptRoot '../docs/화면/90_기타/maiReport_prototype_v1.0.0.html'
if (!(Test-Path -LiteralPath $source)) { throw "Prototype not found: $source" }
$content = [IO.File]::ReadAllText($source)
if ($content -notmatch '(?i)<!doctype html' -or $content -notmatch '(?i)</html>') { throw "Incomplete HTML: $source" }
$encoding = New-Object System.Text.UTF8Encoding($false)
$outputDir = Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$outputFile = Join-Path $outputDir 'prototype.html'
[IO.File]::WriteAllText($outputFile, $content, $encoding)
Write-Output $outputFile
