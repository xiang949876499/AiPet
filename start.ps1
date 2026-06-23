param(
    [int]$Port = 8000,
    [switch]$SkipSync,
    [switch]$SkipSeed,
    [switch]$NoBrowser,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

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

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if ($null -eq $uvCommand) {
    throw "uv was not found. Install uv first: powershell -ExecutionPolicy ByPass -c `"irm https://astral.sh/uv/install.ps1 | iex`""
}

Write-Host "AIPet one-click launcher" -ForegroundColor Green
Write-Host "Project root: $ProjectRoot"

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

$SelectedPort = $Port
while (Test-PortInUse $SelectedPort) {
    Write-Host "Port $SelectedPort is in use; trying the next port..." -ForegroundColor Yellow
    $SelectedPort += 1
    if ($SelectedPort -gt ($Port + 20)) {
        throw "No available port found near $Port. Close the conflicting process and retry."
    }
}

$Url = "http://127.0.0.1:$SelectedPort"
$ServerArgs = @("run", "uvicorn", "web.app:app", "--host", "127.0.0.1", "--port", "$SelectedPort")
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
