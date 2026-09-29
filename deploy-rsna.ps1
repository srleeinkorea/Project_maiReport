param([switch]$CheckOnly, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$repoUrl = 'https://github.com/srleeinkorea/maireport-rsna-demo-k7x9m2q8v4n6.git'
$siteUrl = 'https://srleeinkorea.github.io/maireport-rsna-demo-k7x9m2q8v4n6/'
$checkout = Join-Path $PSScriptRoot '.tmp_artifact/rsna-deploy'
$sourceDir = Join-Path $PSScriptRoot 'outputs/mai-report-rsna-demo'
function Invoke-Git {
    param([string[]]$GitArgs)
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "Git failed: $($GitArgs -join ' ')" }
}
try {
    Get-Command git -ErrorAction Stop | Out-Null
    $source = & (Join-Path $PSScriptRoot 'build-rsna.ps1')
    $html = [IO.File]::ReadAllText($source)
    if ($html -notmatch '(?i)<!doctype html' -or $html -notmatch '(?i)</html>') {
        throw 'The source is not a complete HTML document.'
    }
    Write-Host "Source: $source"
    Write-Host "Site:   $siteUrl"
    if ($CheckOnly) { Write-Host 'Source check passed. No files published.'; exit 0 }
    if (!(Test-Path -LiteralPath $checkout)) {
        New-Item -ItemType Directory -Path (Split-Path $checkout) -Force | Out-Null
        Invoke-Git -GitArgs @('clone', '--branch', 'main', '--single-branch', $repoUrl, $checkout)
    }
    $origin = Invoke-Git -GitArgs @('-C', $checkout, 'remote', 'get-url', 'origin')
    if ($origin.Trim() -ne $repoUrl) { throw 'Unexpected deployment repository. Stopping.' }
    $branch = Invoke-Git -GitArgs @('-C', $checkout, 'branch', '--show-current')
    if ($branch.Trim() -ne 'main') { throw 'Deployment checkout must be on main.' }
    $dirty = Invoke-Git -GitArgs @('-C', $checkout, 'status', '--porcelain')
    if ($dirty) { throw 'Deployment checkout has pending edits. Resolve them before publishing.' }
    Invoke-Git -GitArgs @('-C', $checkout, 'pull', '--ff-only', 'origin', 'main')
    $target = Join-Path $checkout 'index.html'
    $changed = !(Test-Path -LiteralPath $target)
    if (!$changed) { $changed = [IO.File]::ReadAllText($target).Replace("`r`n", "`n") -cne $html.Replace("`r`n", "`n") }
    if ($changed) {
        Copy-Item -LiteralPath $source -Destination $target
        Invoke-Git -GitArgs @('-C', $checkout, 'add', '--', 'index.html')
        Invoke-Git -GitArgs @('-C', $checkout, '-c', 'user.name=srleeinkorea', '-c', 'user.email=srleeinkorea@users.noreply.github.com', 'commit', '-m', ('Update RSNA demo ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')))
    }
    # Also retries a previously committed update if its push failed.
    $ahead = Invoke-Git -GitArgs @('-C', $checkout, 'rev-list', '--count', 'origin/main..HEAD')
    if ([int]$ahead -gt 0) {
        Invoke-Git -GitArgs @('-C', $checkout, 'push', 'origin', 'main')
    } else { Write-Host 'GitHub already has the current source; no upload needed.' }
    Write-Host 'Uploaded. Waiting for GitHub Pages to serve this exact version...'
    $ready = $false
    for ($attempt = 0; $attempt -lt 24; $attempt++) {
        try {
            $probe = $siteUrl + '?deploy=' + [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
            $response = Invoke-WebRequest -Uri $probe -UseBasicParsing -TimeoutSec 15 -Headers @{ 'Cache-Control' = 'no-cache' }
            if ($response.Content.Replace("`r`n", "`n") -ceq $html.Replace("`r`n", "`n")) { $ready = $true; break }
        } catch { Write-Host 'Deployment is still becoming available.' }
        Start-Sleep -Seconds 5
    }
    if (!$ready) { throw "Upload succeeded, but live deployment is not verified yet. Check: $repoUrl" }
    Write-Host 'DONE: The updated site is live.' -ForegroundColor Green
    Write-Host $siteUrl
    if (!$NoBrowser) { Start-Process $siteUrl }
    exit 0
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'If GitHub asks you to sign in, complete the first-time login and run again.'
    exit 1
}
