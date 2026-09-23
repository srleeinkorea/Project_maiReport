$ErrorActionPreference = 'Stop'
$sourceDir = Join-Path $PSScriptRoot 'outputs/mai-report-rsna-demo'
$originals = @(Get-ChildItem -LiteralPath $sourceDir -Filter '*v1.0.0.html' -File | Where-Object { $_.Name -notlike 'gpt_*' })
if ($originals.Count -ne 1) { throw 'Expected exactly one original RSNA HTML.' }
$gpt = Join-Path $sourceDir 'gpt_maiReport_RSNA_home_information_v1.0.0.html'
$template = Join-Path $sourceDir 'version-tabs.html'
$encoding = New-Object System.Text.UTF8Encoding($false)
$result = [IO.File]::ReadAllText($template)
$inputs = @{ '__ORIGINAL_PAYLOAD__' = $originals[0].FullName; '__GPT_PAYLOAD__' = $gpt }
foreach ($marker in $inputs.Keys) {
    $content = [IO.File]::ReadAllText($inputs[$marker])
    if ($content -notmatch '(?i)<!doctype html' -or $content -notmatch '(?i)</html>') { throw "Incomplete HTML: $($inputs[$marker])" }
    $result = $result.Replace($marker, [Convert]::ToBase64String($encoding.GetBytes($content)))
}
$outputDir = Join-Path $PSScriptRoot 'outputs/rsna-github-upload'
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$outputFile = Join-Path $outputDir 'index.html'
[IO.File]::WriteAllText($outputFile, $result, $encoding)
Write-Output $outputFile
