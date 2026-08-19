param(
    [switch]$SkipSync,
    [switch]$SkipSeed,
    [switch]$SkipFrontendBuild,
    [switch]$NoBrowser,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$FixedPort = 8000

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Invoke-Checked {
    param(
        [string]$Command,
        [string[]]$Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Command $($Arguments -join ' ')"
    }
}

function Test-PortInUse {
    param([int]$LocalPort)

    $listener = $null
    try {
        $address = [System.Net.IPAddress]::Parse("127.0.0.1")
        $listener = [System.Net.Sockets.TcpListener]::new($address, $LocalPort)
        $listener.Start()
        return $false
    } catch {
        return $true
    } finally {
        if ($null -ne $listener) {
            $listener.Stop()
        }
    }
}

function Stop-PreviousAipetServers {
    param([string]$RootPath)

    $escapedRoot = [regex]::Escape($RootPath)
    $protectedProcessIds = @()
    $cursor = Get-CimInstance Win32_Process -Filter "ProcessId = $PID" -ErrorAction SilentlyContinue
    while ($null -ne $cursor) {
        $protectedProcessIds += [int]$cursor.ProcessId
        if ($cursor.ParentProcessId -le 0) {
            break
        }
        $cursor = Get-CimInstance Win32_Process -Filter "ProcessId = $($cursor.ParentProcessId)" -ErrorAction SilentlyContinue
    }

    $processes = Get-CimInstance Win32_Process |
        Where-Object {
            $protectedProcessIds -notcontains [int]$_.ProcessId -and
            $_.CommandLine -and
            $_.CommandLine -match $escapedRoot -and
            ($_.CommandLine -match "uvicorn|vite|start\.bat|start\.ps1")
        }

    foreach ($process in $processes) {
        Write-Host "Stop previous AIPet launcher/server PID $($process.ProcessId): $($process.Name)" -ForegroundColor Yellow
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($null -eq $uvCommand) {
    throw "uv was not found. Install uv first: powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`""
}

Write-Host "AIPet one-click launcher" -ForegroundColor Green
Write-Host "Project root: $ProjectRoot"

Write-Step "Close previous AIPet launchers and dev servers"
Stop-PreviousAipetServers -RootPath $ProjectRoot

if (-not $SkipSync) {
    Write-Step "Sync Python dependencies"
    Invoke-Checked "uv" @("sync")
}

Write-Step "Initialize local database"
Invoke-Checked "uv" @("run", "python", "main.py", "init-db")

if (-not $SkipSeed) {
    Write-Step "Seed demo data (skips when data already exists)"
    Invoke-Checked "uv" @("run", "python", "main.py", "seed")
}

if (-not $SkipFrontendBuild) {
    Write-Step "Build Vue frontend for single-port serving"
    if (-not (Test-Path ".\frontend\node_modules")) {
        Push-Location ".\frontend"
        try {
            Invoke-Checked "npm" @("install")
        } finally {
            Pop-Location
        }
    }
    Push-Location ".\frontend"
    try {
        Invoke-Checked "npm" @("run", "build")
    } finally {
        Pop-Location
    }
}

if (Test-PortInUse $FixedPort) {
    throw "Port $FixedPort is still in use by another process. Close it before starting AIPet."
}

$Url = "http://127.0.0.1:$FixedPort"
$ServerArgs = @("run", "uvicorn", "web.app:app", "--host", "127.0.0.1", "--port", "8000")
if (-not $NoReload) {
    $ServerArgs += "--reload"
}

if (-not $NoBrowser) {
    Start-Job -ScriptBlock {
        param([string]$TargetUrl)

        for ($i = 0; $i -lt 30; $i++) {
            try {
                Invoke-WebRequest -Uri $TargetUrl -UseBasicParsing -TimeoutSec 1 | Out-Null
                Start-Process $TargetUrl
                return
            } catch {
                Start-Sleep -Seconds 1
            }
        }

        Start-Process $TargetUrl
    } -ArgumentList $Url | Out-Null
}

Write-Step "Start Web workspace"
Write-Host "URL: $Url" -ForegroundColor Green
Write-Host "Stop: press Ctrl+C in this window"
Write-Host ""

& uv @ServerArgs
