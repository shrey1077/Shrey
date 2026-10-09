<#
  Installs Andy for the current Windows user.

  From the folder where you cloned the repository, run:
    powershell -ExecutionPolicy Bypass -File andy\install-andy.ps1

  What it does:
  - Creates a private Python environment in %LOCALAPPDATA%\Andy\venv
  - Installs Andy's dependencies, refusing any package whose SHA-256 hash doesn't match
  - Adds "Andy" to the Start menu and the desktop
  Your vault is created on first launch, also in %LOCALAPPDATA%\Andy.
#>
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$AndyHome = Join-Path $env:LOCALAPPDATA "Andy"
$Venv = Join-Path $AndyHome "venv"

function Invoke-Checked([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Exe $($Arguments -join ' ')" }
}

Write-Host "Looking for 64-bit Python 3.11 or newer..."
$Python = $null
$PythonArgs = @()
foreach ($candidate in @("py -3.13", "py -3.12", "py -3.14", "py -3.11", "python")) {
    $parts = $candidate.Split(" ")
    $exe = $parts[0]
    if ($parts.Length -gt 1) { $rest = @($parts[1..($parts.Length - 1)]) } else { $rest = @() }
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    $check = & $exe @rest -c "import sys, struct; print(int(sys.version_info >= (3, 11) and struct.calcsize('P') == 8))" 2>$null
    if ($check -eq "1") { $Python = $exe; $PythonArgs = $rest; break }
}
if (-not $Python) {
    throw "Install 64-bit Python 3.12 or 3.13 from https://www.python.org/downloads/windows/ (tick 'Add python.exe to PATH'), then run this again."
}

$webview2 = @(
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
    "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
    "HKCU:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
) | Where-Object { Test-Path $_ }
if (-not $webview2) {
    Write-Warning "Microsoft Edge WebView2 Runtime was not found. Windows 11 includes it; on Windows 10 get it from https://developer.microsoft.com/microsoft-edge/webview2/"
}

New-Item -ItemType Directory -Force -Path $AndyHome | Out-Null
if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
    Write-Host "Creating Andy's private Python environment..."
    Invoke-Checked $Python ($PythonArgs + @("-m", "venv", $Venv))
}
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$VenvPythonw = Join-Path $Venv "Scripts\pythonw.exe"

Write-Host "Installing hash-verified dependencies..."
Invoke-Checked $VenvPython @("-m", "pip", "install", "--disable-pip-version-check", "--require-hashes", "--no-deps",
    "-r", (Join-Path $Repo "andy\requirements-build.txt"))
Invoke-Checked $VenvPython @("-m", "pip", "install", "--disable-pip-version-check", "--require-hashes", "--no-build-isolation",
    "-r", (Join-Path $Repo "andy\requirements.txt"))

Write-Host "Adding shortcuts..."
$shell = New-Object -ComObject WScript.Shell
$places = @(
    (Join-Path ([Environment]::GetFolderPath("Programs")) "Andy.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "Andy.lnk")
)
foreach ($place in $places) {
    $link = $shell.CreateShortcut($place)
    $link.TargetPath = $VenvPythonw
    $link.Arguments = "-m andy"
    $link.WorkingDirectory = $Repo
    $link.IconLocation = (Join-Path $Repo "andy\ui\andy.ico")
    $link.Description = "Andy - personal CA and expense guardian"
    $link.Save()
}

Write-Host ""
Write-Host "Andy is installed. Open it from the Start menu or the desktop shortcut."
Write-Host "Recommended: turn on BitLocker (Settings > Privacy & security > Device encryption) and keep Windows updated."
